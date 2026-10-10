"""
SDK Client Pool - Manages persistent ClaudeSDKClient connections.

Keeps CLI processes running across multiple requests for the same session,
avoiding the ~80s delay caused by CLI startup + session file loading.

Design:
    - One ClaudeSDKClient per session_id
    - Clients are kept alive until idle timeout or explicit close
    - Session Affinity ensures same session routes to same worker process
    - If CLI process crashes, client is automatically recreated on next request
"""

import asyncio
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ...core.utils.timezone import utc_now
from typing import Any, Dict, Optional

try:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
except ImportError as _import_err:
    raise ImportError(
        "claude-agent-sdk is required for SDKClientPool. "
        "Install it with: pip install claude-agent-sdk>=0.1.0"
    ) from _import_err

logger = logging.getLogger(__name__)


@dataclass
class PooledClient:
    """A pooled ClaudeSDKClient with metadata for lifecycle management."""

    client: ClaudeSDKClient
    session_id: str
    created_at: datetime = field(default_factory=utc_now)
    last_used_at: datetime = field(default_factory=utc_now)
    request_count: int = 0
    is_connected: bool = False
    # Store options hash to detect when we need a new client
    options_hash: str = ""
    # Mutable context for pool-reused closures (MCP handlers, hooks)
    tool_context: Any = None
    # Sandbox directory for CLI filesystem isolation
    sandbox_dir: Optional[str] = None


class SDKClientPool:
    """
    Pool of persistent ClaudeSDKClient connections.

    Maintains one client per session_id. Clients are reused across requests
    until they time out or encounter errors.

    Cross-process visibility:
        When a client is created/used, a Redis marker is set so that the
        FastAPI process can detect warm clients and upgrade FAST→SLOW routes
        for context continuity.

    Usage:
        pool = SDKClientPool()

        # Get or create client for a session
        pooled = await pool.get_or_create(
            session_id="abc123",
            options=ClaudeAgentOptions(...),
        )

        # Use the client
        await pooled.client.query("Hello")
        async for msg in pooled.client.receive_response():
            ...

        # Mark as used (extends idle timeout)
        await pool.mark_used(session_id)
    """

    DEFAULT_IDLE_TIMEOUT_SECONDS = 1800  # 30 minutes (matches session affinity TTL)
    DEFAULT_MAX_CLIENTS = 50  # Max concurrent clients per worker
    POOL_ACTIVE_KEY_PREFIX = "sdk_pool:active"  # Redis key prefix for cross-process visibility

    def __init__(
        self,
        idle_timeout_seconds: int = DEFAULT_IDLE_TIMEOUT_SECONDS,
        max_clients: int = DEFAULT_MAX_CLIENTS,
    ):
        self._clients: Dict[str, PooledClient] = {}
        self._lock = asyncio.Lock()
        self._idle_timeout = idle_timeout_seconds
        # Marker TTL must outlive idle timeout + cleanup interval (60s) to
        # avoid false negatives where the marker expires before cleanup runs.
        self._marker_ttl = idle_timeout_seconds + 120
        self._max_clients = max_clients
        self._cleanup_task: Optional[asyncio.Task] = None
        self._disconnect_tasks: set[asyncio.Task] = set()
        # Unique identity for this worker process, embedded in Redis markers
        # so that cleanup_stale_markers() can distinguish live vs dead workers.
        #
        # Design note: markers track which *worker process* owns a session,
        # not individual CLI subprocesses.  When a worker dies, its entire
        # SDKClientPool (and all CLI children it manages) become unreachable,
        # so all markers with that worker's identity are stale.  In a
        # multi-worker deployment on the same host, each worker has a
        # distinct PID, so cleanup correctly preserves other live workers'
        # markers while removing dead ones.
        self._worker_id = f"{socket.gethostname()}:{os.getpid()}"

    async def start(self) -> None:
        """Start the pool and background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info(
                "SDKClientPool started (idle_timeout=%ds, max_clients=%d)",
                self._idle_timeout,
                self._max_clients,
            )

    async def stop(self) -> None:
        """Stop the pool and close all clients."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        async with self._lock:
            for session_id in list(self._clients.keys()):
                await self._close_client(session_id, wait_disconnect=False)
            logger.info("SDKClientPool stopped, all clients closed")
        await self._drain_disconnect_tasks(timeout_seconds=10.0)

    async def get_or_create(
        self,
        session_id: str,
        options: ClaudeAgentOptions,
    ) -> PooledClient:
        """
        Get an existing client or create a new one.

        If options have changed significantly, the old client is closed
        and a new one is created.

        Args:
            session_id: The chat session ID
            options: ClaudeAgentOptions for the client

        Returns:
            PooledClient with an active connection
        """
        options_hash = self._hash_options(options)

        async with self._lock:
            pooled = self._clients.get(session_id)

            if pooled is not None:
                # Check if client is still usable
                if pooled.is_connected and pooled.options_hash == options_hash:
                    logger.debug(
                        "Reusing pooled client for session=%s (requests=%d)",
                        session_id,
                        pooled.request_count,
                    )
                    return pooled

                # Options changed or client disconnected, close old one
                logger.info(
                    "Closing stale client for session=%s (options_changed=%s, connected=%s)",
                    session_id,
                    pooled.options_hash != options_hash,
                    pooled.is_connected,
                )
                await self._close_client(session_id)

            # Evict oldest if at capacity
            if len(self._clients) >= self._max_clients:
                await self._evict_oldest()

            # Create new client
            pooled = await self._create_client(session_id, options, options_hash)
            self._clients[session_id] = pooled
            return pooled

    def peek(self, session_id: str) -> Optional[PooledClient]:
        """Get existing connected client without creating a new one.

        Used by the pool-reuse path to check whether a client with a
        ``PooledToolContext`` is available before deciding to create vs reuse.
        """
        pooled = self._clients.get(session_id)
        if pooled and pooled.is_connected:
            return pooled
        return None

    async def mark_used(self, session_id: str) -> None:
        """Mark a client as recently used (extends idle timeout + refreshes Redis marker)."""
        pooled = self._clients.get(session_id)
        if pooled:
            pooled.last_used_at = utc_now()
            pooled.request_count += 1
        await self._set_active_marker(session_id)

    async def close(self, session_id: str) -> None:
        """Explicitly close and remove a client."""
        async with self._lock:
            await self._close_client(session_id, wait_disconnect=False)

    async def mark_disconnected(self, session_id: str) -> None:
        """Close and mark a client as disconnected.

        This actively disconnects the pooled SDK client to stop any stale
        in-flight stream/tool callbacks after timeout or fatal errors.

        Disconnect runs in a background task to avoid anyio cancel-scope
        cross-task violations when called from a task that did NOT enter
        the SDK's cancel scope.  For callers that DID enter the scope
        (e.g. ReactiveSessionActor), use ``disconnect_inline`` instead.
        """
        async with self._lock:
            pooled = self._clients.get(session_id)
            if pooled:
                await self._close_client(session_id, wait_disconnect=False)
                logger.warning(
                    "Client closed and marked disconnected: session=%s",
                    session_id,
                )
        await self._clear_active_marker(session_id)

    async def disconnect_inline(self, session_id: str) -> None:
        """Remove client from pool and disconnect in the caller's task.

        Unlike ``mark_disconnected`` (which spawns a background task),
        this method disconnects **inline** in the caller's asyncio task.
        This is required when the caller is the same task that entered
        the SDK's anyio cancel scope (e.g. ReactiveSessionActor._run),
        because anyio forbids exiting a cancel scope from a different task.

        IMPORTANT: This method calls ``client.disconnect()`` **directly**,
        without ``asyncio.shield()``.  ``asyncio.shield()`` wraps the
        coroutine in an internal Task, which would violate the cancel-scope
        same-task constraint and trigger ``RuntimeError: Attempted to exit
        cancel scope in a different task``.

        Safe to call even if the session has already been removed.
        """
        async with self._lock:
            pooled = self._clients.pop(session_id, None)
        if pooled is None:
            await self._clear_active_marker(session_id)
            return
        await self._clear_active_marker(session_id)
        # Call disconnect() directly — NOT via _disconnect_client() which
        # wraps in asyncio.shield() and creates a new Task.
        try:
            await pooled.client.disconnect()
            logger.debug(
                "Closed pooled client inline for session=%s (requests=%d, age=%ds)",
                session_id,
                pooled.request_count,
                (utc_now() - pooled.created_at).total_seconds(),
            )
        except BaseException as e:
            logger.warning(
                "Error closing client inline for session=%s: %s",
                session_id,
                e,
            )
        # Clean up sandbox after CLI process is terminated
        if pooled.sandbox_dir:
            _cleanup_sandbox(pooled.sandbox_dir)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "total_clients": len(self._clients),
            "max_clients": self._max_clients,
            "idle_timeout_seconds": self._idle_timeout,
            "clients": {
                sid: {
                    "connected": p.is_connected,
                    "request_count": p.request_count,
                    "age_seconds": (
                        utc_now() - p.created_at
                    ).total_seconds(),
                    "idle_seconds": (
                        utc_now() - p.last_used_at
                    ).total_seconds(),
                }
                for sid, p in self._clients.items()
            },
        }

    # ── Redis Markers (cross-process visibility) ─────────────────────────

    async def _set_active_marker(self, session_id: str) -> None:
        """Set Redis marker so other processes know a warm client exists.

        The value stores the worker identity (``hostname:pid``) so that
        ``cleanup_stale_markers`` can distinguish live workers from dead ones.
        """
        try:
            from ...core.cache import redis_client
            key = f"{self.POOL_ACTIVE_KEY_PREFIX}:{session_id}"
            await redis_client.set(key, self._worker_id, ttl=self._marker_ttl)
        except Exception as e:
            logger.debug("Failed to set pool active marker: %s", e)

    async def _clear_active_marker(self, session_id: str) -> None:
        """Clear Redis marker when client is closed or disconnected."""
        try:
            from ...core.cache import redis_client
            key = f"{self.POOL_ACTIVE_KEY_PREFIX}:{session_id}"
            await redis_client.delete(key)
        except Exception as e:
            logger.debug("Failed to clear pool active marker: %s", e)

    # ── Stale Marker Cleanup ───────────────────────────────────────────

    async def cleanup_stale_markers(self) -> int:
        """Remove Redis markers left by dead worker processes.

        Each marker stores ``hostname:pid`` as its value.  This method
        SCANs all ``sdk_pool:active:*`` keys and for each one:

        * If the marker belongs to a **different host** — skip (can't
          verify liveness across hosts; rely on TTL expiry).
        * If the marker belongs to **this host** — check whether the PID
          is still alive via ``os.kill(pid, 0)``.  If the process is
          dead, the marker is stale and gets deleted.

        This is safe in multi-worker deployments: we never touch markers
        belonging to other live workers.

        Returns:
            Number of stale markers removed.
        """
        try:
            from ...core.cache import redis_client
            raw = redis_client.client
            if raw is None:
                return 0

            current_hostname = socket.gethostname()
            pattern = f"{self.POOL_ACTIVE_KEY_PREFIX}:*"

            stale_keys: list[str] = []
            cursor: int = 0
            while True:
                cursor, keys = await raw.scan(cursor, match=pattern, count=100)
                for key in keys:
                    key_str = key if isinstance(key, str) else key.decode()
                    value = await raw.get(key_str)
                    if not value:
                        stale_keys.append(key_str)
                        continue

                    val_str = value if isinstance(value, str) else value.decode()
                    parts = val_str.rsplit(":", 1)
                    if len(parts) != 2:
                        # Malformed value (e.g. legacy "1"), treat as stale
                        stale_keys.append(key_str)
                        continue

                    marker_host, pid_str = parts
                    if marker_host != current_hostname:
                        # Different host — can't verify, let TTL handle it
                        continue

                    try:
                        pid = int(pid_str)
                        os.kill(pid, 0)  # signal 0 = existence check
                    except (ValueError, TypeError):
                        stale_keys.append(key_str)
                    except OSError:
                        # Process doesn't exist → stale marker
                        stale_keys.append(key_str)

                if cursor == 0:
                    break

            if stale_keys:
                await raw.delete(*stale_keys)
                logger.info(
                    "Cleaned up %d stale Redis pool markers from dead workers",
                    len(stale_keys),
                )
            return len(stale_keys)
        except Exception as e:
            logger.warning("Failed to clean up stale pool markers: %s", e)
            return 0

    # ── Internal Methods ────────────────────────────────────────────────

    async def _create_client(
        self,
        session_id: str,
        options: ClaudeAgentOptions,
        options_hash: str,
    ) -> PooledClient:
        """Create and connect a new client.

        This is where the ~68s CLI startup overhead occurs. The SDK spawns
        a Claude CLI subprocess and waits for it to be ready. With DashScope
        proxy, this includes an initial API handshake that adds latency.
        """
        t0 = time.monotonic()
        client = ClaudeSDKClient(options=options)
        t_init = time.monotonic()

        try:
            await client.connect()
            t_connected = time.monotonic()
            logger.info(
                "Created new pooled client for session=%s "
                "(init_ms=%.0f, connect_ms=%.0f, total_ms=%.0f)",
                session_id,
                (t_init - t0) * 1000,
                (t_connected - t_init) * 1000,
                (t_connected - t0) * 1000,
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.error(
                "Failed to connect client for session=%s: %s (elapsed_ms=%.0f)",
                session_id,
                e,
                elapsed_ms,
            )
            raise

        await self._set_active_marker(session_id)

        return PooledClient(
            client=client,
            session_id=session_id,
            options_hash=options_hash,
            is_connected=True,
        )

    async def _close_client(
        self,
        session_id: str,
        *,
        wait_disconnect: bool = False,
    ) -> None:
        """Close and remove a client (must hold lock).

        Uses asyncio.shield + BaseException catch to prevent the SDK's internal
        anyio cancel-scope from propagating CancelledError to unrelated tasks
        (e.g. the Agent Worker loop).

        Sandbox cleanup runs AFTER disconnect to avoid racing with in-flight
        CLI operations that may still be writing to the sandbox directory.
        """
        pooled = self._clients.pop(session_id, None)
        if pooled is None:
            return

        await self._clear_active_marker(session_id)
        if wait_disconnect:
            await self._disconnect_client(pooled)
            if pooled.sandbox_dir:
                _cleanup_sandbox(pooled.sandbox_dir)
            return
        self._spawn_disconnect_task(session_id, pooled)

    async def _disconnect_client(self, pooled: PooledClient) -> None:
        """Best-effort client disconnect with cancellation containment."""
        session_id = pooled.session_id

        try:
            # Shield prevents external cancellation from aborting disconnect
            # midway, and we catch BaseException so that any CancelledError
            # raised by cross-task cancel-scope violations stays contained.
            await asyncio.shield(pooled.client.disconnect())
            logger.debug(
                "Closed pooled client for session=%s (requests=%d, age=%ds)",
                session_id,
                pooled.request_count,
                (utc_now() - pooled.created_at).total_seconds(),
            )
        except BaseException as e:
            # anyio cancel-scope cross-task violation is expected during
            # pool shutdown — the scope was entered in the session actor's
            # task, not ours.  Harmless: the CLI process exits with us.
            logger.debug(
                "Error closing client for session=%s: %s",
                session_id,
                e,
            )

    def _spawn_disconnect_task(self, session_id: str, pooled: PooledClient) -> None:
        """Disconnect client asynchronously so caller task is never interrupted."""

        async def _runner() -> None:
            await self._disconnect_client(pooled)
            if pooled.sandbox_dir:
                _cleanup_sandbox(pooled.sandbox_dir)

        task = asyncio.create_task(
            _runner(),
            name=f"sdk-pool-disconnect:{session_id}",
        )
        self._disconnect_tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            self._disconnect_tasks.discard(t)
            if t.cancelled():
                return
            exc = t.exception()
            if exc is not None:
                logger.debug(
                    "Disconnect background task failed for session=%s: %s",
                    session_id,
                    exc,
                )

        task.add_done_callback(_done)

    async def _drain_disconnect_tasks(self, timeout_seconds: float) -> None:
        """Wait briefly for background disconnect tasks during shutdown."""
        if not self._disconnect_tasks:
            return
        pending = list(self._disconnect_tasks)
        try:
            await asyncio.wait_for(
                asyncio.gather(*pending, return_exceptions=True),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Timeout draining %d disconnect task(s) during pool stop",
                len(pending),
            )

    async def _evict_oldest(self) -> None:
        """Evict the oldest (least recently used) client (must hold lock)."""
        if not self._clients:
            return

        oldest_session = min(
            self._clients.keys(),
            key=lambda sid: self._clients[sid].last_used_at,
        )
        logger.info(
            "Evicting oldest client: session=%s (pool at capacity)",
            oldest_session,
        )
        await self._close_client(oldest_session, wait_disconnect=False)

    async def _cleanup_loop(self) -> None:
        """Background task to close idle clients."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_idle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup loop: %s", e)

    async def _cleanup_idle(self) -> None:
        """Close clients that have been idle too long."""
        now = utc_now()
        to_close = []

        async with self._lock:
            for session_id, pooled in self._clients.items():
                idle_seconds = (now - pooled.last_used_at).total_seconds()
                if idle_seconds > self._idle_timeout:
                    to_close.append(session_id)

            for session_id in to_close:
                logger.info(
                    "Closing idle client: session=%s (idle for %ds)",
                    session_id,
                    self._idle_timeout,
                )
                await self._close_client(session_id, wait_disconnect=False)

    @staticmethod
    def _hash_options(options: ClaudeAgentOptions) -> str:
        """
        Create a hash of options that affect client reusability.

        We only hash fields that would require a new CLI process if changed.
        Fields like system_prompt can change between queries.
        """
        # For now, hash model and permission_mode as they affect CLI behavior
        parts = [
            getattr(options, "model", "") or "",
            getattr(options, "permission_mode", "") or "",
        ]
        return ":".join(parts)


def _cleanup_sandbox(sandbox_dir: str) -> None:
    """Remove a session sandbox directory (best-effort)."""
    import shutil
    try:
        if os.path.isdir(sandbox_dir):
            shutil.rmtree(sandbox_dir, ignore_errors=True)
            logger.debug("Cleaned up sandbox: %s", sandbox_dir)
    except Exception:
        logger.warning("Failed to clean sandbox: %s", sandbox_dir, exc_info=True)


# ── Global Pool Instance ────────────────────────────────────────────────

_pool: Optional[SDKClientPool] = None
_pool_lock = asyncio.Lock()


async def get_sdk_client_pool() -> SDKClientPool:
    """Get or create the global SDKClientPool instance."""
    global _pool
    async with _pool_lock:
        if _pool is None:
            from ...config.settings import settings
            _pool = SDKClientPool(
                idle_timeout_seconds=settings.sdk_client_pool_idle_timeout_seconds,
                max_clients=settings.sdk_client_pool_max_clients,
            )
            await _pool.start()
        return _pool


async def shutdown_sdk_client_pool() -> None:
    """Shutdown the global SDKClientPool."""
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.stop()
            _pool = None


async def has_active_client(session_id: str) -> bool:
    """Check if a warm pooled SDK client exists for the given session.

    Reads a Redis marker set by the Celery worker process, allowing the
    FastAPI process to make routing decisions based on pool state.
    Returns False on any error (conservative — avoids false upgrades).
    """
    if not session_id:
        return False
    try:
        from ...core.cache import redis_client
        key = f"{SDKClientPool.POOL_ACTIVE_KEY_PREFIX}:{session_id}"
        return await redis_client.exists(key)
    except Exception:
        return False
