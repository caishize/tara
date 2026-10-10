"""
Mutable execution context for pooled CLI client reuse.

MCP tool handlers, SDK hooks, and publish callbacks close over a
PooledToolContext instance.  When the pool reuses a CLI client for a
new request, ``update()`` replaces all internal references so every
closure transparently sees the fresh DB session, task metadata, etc.
"""

import asyncio
import hashlib
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PooledToolContext:
    """Mutable indirection for pool-reused CLI clients.

    All closures (MCP handlers, hooks, callbacks) capture *this* object
    and read ``ctx.persistence``, ``ctx.task``, etc. at call time — not
    at closure-creation time.  Calling ``update()`` swaps the internals
    without rebuilding the MCP server or SDK hooks.

    The dynamic MCP server also reads ``ctx.tool_map`` for ``list_tools``
    and ``call_tool`` so that tool renames/additions are reflected without
    recreating the CLI process (~80s cold start).
    """

    __slots__ = (
        "bridge",
        "persistence",
        "task",
        "pubsub",
        "sdk_stream_handler",
        "worker",
        "keepalive",
        "tool_names_hash",
        "tool_map",
        "_mcp_session",
    )

    def __init__(self) -> None:
        self.bridge: Any = None               # ToolBridge
        self.persistence: Any = None          # ToolPersistenceHandler
        self.task: Any = None                 # TaskPayload
        self.pubsub: Any = None               # RedisPubSubManager
        self.sdk_stream_handler: Any = None   # SDKStreamHandler
        self.worker: Any = None               # AgentWorker (for _create_pending_action)
        self.keepalive: Optional[asyncio.Event] = None  # Idle timeout keepalive signal
        self.tool_names_hash: str = ""        # Hash of tool names currently in tool_map
        self.tool_map: Dict[str, Dict[str, Any]] = {}  # {name: tool_def} — kept in sync with bridge
        self._mcp_session: Any = None         # ServerSession, captured on first list_tools call

    def update(
        self,
        *,
        bridge: Any,
        persistence: Any,
        task: Any,
        pubsub: Any,
        sdk_stream_handler: Any,
        worker: Any,
    ) -> None:
        """Replace all references in-place for a new request."""
        self.bridge = bridge
        self.persistence = persistence
        self.task = task
        self.pubsub = pubsub
        self.sdk_stream_handler = sdk_stream_handler
        self.worker = worker

    # ------------------------------------------------------------------
    # Tool-map helpers
    # ------------------------------------------------------------------

    @staticmethod
    def compute_tool_names_hash(bridge: Any) -> str:
        """Compute a stable hash of tool names from the bridge's registry."""
        tool_defs = bridge.get_tool_definitions()
        names = sorted(td["name"] for td in tool_defs)
        raw = ",".join(names)
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def refresh_tool_map(self) -> None:
        """Rebuild ``tool_map`` from the current bridge and update the hash."""
        tool_defs = self.bridge.get_tool_definitions()
        self.tool_map = {td["name"]: td for td in tool_defs}
        self.tool_names_hash = self.compute_tool_names_hash(self.bridge)

    def tools_changed(self, bridge: Any) -> bool:
        """Return True if *bridge*'s tools differ from the current tool_map."""
        if not self.tool_names_hash:
            return False  # No hash recorded yet (first request)
        return self.compute_tool_names_hash(bridge) != self.tool_names_hash

    async def notify_tools_changed(self) -> bool:
        """Refresh tool_map and send MCP ``tools/list_changed`` notification.

        Returns True if the notification was sent successfully, False otherwise.
        The caller should fall back to client invalidation on False.
        """
        self.refresh_tool_map()
        session = self._mcp_session
        if session is None:
            logger.warning("Cannot send tools/list_changed: no MCP session captured")
            return False
        try:
            await session.send_tool_list_changed()
            logger.info(
                "Sent tools/list_changed notification (hash=%s, %d tools)",
                self.tool_names_hash, len(self.tool_map),
            )
            return True
        except Exception:
            logger.warning(
                "Failed to send tools/list_changed notification",
                exc_info=True,
            )
            return False
