"""
WebSocket Connection Manager with Redis Pub/Sub integration.

Bridges Agent Worker results to connected WebSocket clients.
Supports multiple concurrent connections per user (multi-device).
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from ..pubsub import RedisPubSubManager, PubSubMessage, get_pubsub_manager
from ..utils.timezone import utc_now

if TYPE_CHECKING:
    from ...ai_engine.voice.stream_session import VoiceStreamSession


logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_USER = 5


class ConnectionState(str, Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SUBSCRIBED = "subscribed"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    user_id: str
    family_id: str
    websocket: WebSocket
    state: ConnectionState = ConnectionState.CONNECTING
    connected_at: str = field(default_factory=lambda: utc_now().isoformat())
    subscription_task: Optional[asyncio.Task] = None
    last_ping: Optional[str] = None
    message_count: int = 0
    voice_stream: Optional[VoiceStreamSession] = None


class WebSocketManager:
    """
    Manages WebSocket connections with Redis Pub/Sub integration.

    Supports multiple concurrent connections per user (multi-device).
    Each user can have up to MAX_CONNECTIONS_PER_USER connections;
    the oldest connection is closed when the limit is exceeded.

    Usage:
        manager = WebSocketManager()

        @app.websocket("/ws/{user_id}")
        async def websocket_endpoint(websocket: WebSocket, user_id: str):
            await manager.connect(websocket, user_id, family_id)
            try:
                await manager.run_with_keepalive(user_id, websocket)
            except WebSocketDisconnect:
                await manager.disconnect_one(user_id, websocket)
    """

    def __init__(self, pubsub: Optional[RedisPubSubManager] = None):
        self._connections: Dict[str, List[ConnectionInfo]] = {}
        self._pubsub = pubsub
        self._lock = asyncio.Lock()
        # One Pub/Sub subscription task per user (shared across devices)
        self._subscription_tasks: Dict[str, asyncio.Task] = {}

    @property
    def pubsub(self) -> RedisPubSubManager:
        """Get Pub/Sub manager (lazy initialization)."""
        if self._pubsub is None:
            self._pubsub = get_pubsub_manager()
        return self._pubsub

    async def connect(
        self, websocket: WebSocket, user_id: str, family_id: str = "",
    ) -> bool:
        """
        Accept and register a WebSocket connection.

        Supports multiple connections per user. When the per-user limit
        is exceeded, the oldest connection is closed automatically.

        Args:
            websocket: FastAPI WebSocket instance
            user_id: User ID for the connection
            family_id: Family ID for the connection (needed for voice dispatch)

        Returns:
            True if connection was established
        """
        try:
            await websocket.accept()

            conn = ConnectionInfo(
                user_id=user_id,
                family_id=family_id,
                websocket=websocket,
                state=ConnectionState.CONNECTED,
            )

            async with self._lock:
                conns = self._connections.setdefault(user_id, [])

                # Enforce per-user connection limit — close oldest first
                while len(conns) >= MAX_CONNECTIONS_PER_USER:
                    oldest = conns.pop(0)
                    await self._close_single_connection(oldest, "Connection limit exceeded")

                conns.append(conn)

            logger.info(
                "WebSocket connected: user_id=%s, total_for_user=%d",
                user_id, len(self._connections.get(user_id, [])),
            )
            return True

        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection: {e}")
            return False

    async def disconnect(self, user_id: str) -> None:
        """
        Disconnect ALL connections for a user.

        Args:
            user_id: User ID to disconnect
        """
        async with self._lock:
            await self._close_all_connections(user_id, "Client disconnected")

    async def disconnect_one(self, user_id: str, websocket: WebSocket) -> None:
        """
        Disconnect a single WebSocket connection for a user.

        Other connections for the same user remain open.

        Args:
            user_id: User ID
            websocket: The specific WebSocket instance to remove
        """
        async with self._lock:
            conns = self._connections.get(user_id)
            if not conns:
                return

            remaining = []
            for conn in conns:
                if conn.websocket is websocket:
                    await self._close_single_connection(conn, "Device disconnected")
                else:
                    remaining.append(conn)

            if remaining:
                self._connections[user_id] = remaining
            else:
                self._connections.pop(user_id, None)
                # Cancel shared subscription when last device disconnects
                await self._cancel_subscription(user_id)

            logger.info(
                "WebSocket device disconnected: user_id=%s, remaining=%d",
                user_id, len(remaining),
            )

    async def _close_single_connection(self, conn: ConnectionInfo, reason: str) -> None:
        """Close a single connection without touching the list."""
        conn.state = ConnectionState.DISCONNECTING
        # Clean up any active voice stream before closing WS
        await self._cleanup_voice_stream(conn)
        try:
            await conn.websocket.close()
        except Exception:
            pass
        logger.debug("Closed WS connection: user_id=%s, reason=%s", conn.user_id, reason)

    async def _close_all_connections(self, user_id: str, reason: str) -> None:
        """Close all connections for a user (must hold lock)."""
        conns = self._connections.pop(user_id, [])
        for conn in conns:
            await self._close_single_connection(conn, reason)
        await self._cancel_subscription(user_id)
        if conns:
            logger.info("WebSocket all disconnected: user_id=%s, reason=%s", user_id, reason)

    async def _cancel_subscription(self, user_id: str) -> None:
        """Cancel the shared Pub/Sub subscription for a user."""
        task = self._subscription_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def start_listening(self, user_id: str) -> None:
        """
        Start a shared Pub/Sub listener for the user.

        Messages are forwarded to ALL connected devices.
        Only one subscription task runs per user.

        Args:
            user_id: User ID to listen for
        """
        # Ensure Pub/Sub is connected
        await self.pubsub.connect()

        try:
            async for message in self.pubsub.subscribe(user_id):
                await self._forward_message(user_id, message)
        except asyncio.CancelledError:
            logger.debug("Subscription cancelled for user_id=%s", user_id)
        except Exception as e:
            logger.error("Error in Pub/Sub subscription: %s", e)
            raise

    async def _forward_message(self, user_id: str, message: PubSubMessage) -> None:
        """Forward a Pub/Sub message to ALL connected devices for a user.

        Sends to all devices in parallel with a per-device timeout to prevent
        a single slow connection from blocking delivery to other devices.
        """
        # Snapshot connection list to avoid races with concurrent connect/disconnect
        conns = list(self._connections.get(user_id, []))
        if not conns:
            return

        data = message.to_dict()
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        msg_type = data.get("message_type")
        job_id = data.get("job_id")
        seq = data.get("seq")
        should_trace = msg_type in {
            "complete",
            "error",
            "background_job",
            "confirm_card",
            "ask_user_question",
            "generation_state",
            "partial_content",
            "bridging",
        }
        if should_trace:
            logger.info(
                "WS forward start: user_id=%s type=%s job_id=%s seq=%s conns=%d "
                "content_len=%d",
                user_id,
                msg_type,
                job_id,
                seq,
                len(conns),
                len(payload.get("content", ""))
                if isinstance(payload.get("content"), str)
                else 0,
            )

        results = await asyncio.gather(
            *(self._send_to_one(conn, data, user_id, msg_type) for conn in conns)
        )
        failed = [ws for ws in results if ws is not None]
        sent_count = len(conns) - len(failed)

        # Clean up failed connections outside the iteration
        for ws in failed:
            await self.disconnect_one(user_id, ws)

        if should_trace:
            logger.info(
                "WS forward done: user_id=%s type=%s job_id=%s seq=%s "
                "sent=%d failed=%d",
                user_id,
                msg_type,
                job_id,
                seq,
                sent_count,
                len(failed),
            )

    async def _send_to_one(
        self,
        conn: ConnectionInfo,
        data: Dict[str, Any],
        user_id: str,
        msg_type: Optional[str] = None,
    ) -> Optional[WebSocket]:
        """Send data to a single connection with timeout.

        Returns None on success, or the WebSocket on failure (for cleanup).
        """
        try:
            await asyncio.wait_for(
                conn.websocket.send_json(data),
                timeout=5.0,
            )
            conn.message_count += 1
            return None
        except asyncio.TimeoutError:
            logger.warning(
                "WS send timeout (5s) for user_id=%s type=%s",
                user_id, msg_type,
            )
            return conn.websocket
        except Exception as e:
            logger.warning("Failed to send to device for user_id=%s: %s", user_id, e)
            return conn.websocket

    async def send_direct(self, user_id: str, data: Dict[str, Any]) -> bool:
        """
        Send a message directly to ALL connected WebSockets (bypassing Pub/Sub).

        Sends in parallel with per-device timeout, consistent with
        _forward_message behavior.

        Args:
            user_id: Target user
            data: Data to send

        Returns:
            True if message was sent to at least one device
        """
        conns = list(self._connections.get(user_id, []))
        if not conns:
            return False

        results = await asyncio.gather(
            *(self._send_to_one(conn, data, user_id) for conn in conns)
        )
        failed = [ws for ws in results if ws is not None]

        for ws in failed:
            await self.disconnect_one(user_id, ws)

        return len(failed) < len(conns)

    async def broadcast_to_all(self, data: Dict[str, Any]) -> int:
        """
        Broadcast a message to all connected users.

        Args:
            data: Data to broadcast

        Returns:
            Number of users who received the message
        """
        count = 0
        for user_id in list(self._connections.keys()):
            if await self.send_direct(user_id, data):
                count += 1
        return count

    def is_connected(self, user_id: str) -> bool:
        """Check if a user has at least one active connection."""
        conns = self._connections.get(user_id)
        if not conns:
            return False
        return any(
            c.state in (ConnectionState.CONNECTED, ConnectionState.SUBSCRIBED)
            for c in conns
        )

    def get_connection_count(self) -> int:
        """Get total number of active connections (across all users)."""
        return sum(len(conns) for conns in self._connections.values())

    def get_user_connection_count(self, user_id: str) -> int:
        """Get number of active connections for a specific user."""
        return len(self._connections.get(user_id, []))

    def get_connection_info(self, user_id: str) -> Optional[ConnectionInfo]:
        """Get connection info for a user (returns the most recent connection)."""
        conns = self._connections.get(user_id)
        if not conns:
            return None
        return conns[-1]

    async def handle_client_message(
        self,
        user_id: str,
        websocket: WebSocket,
        data: str,
        handlers: Optional[Dict[str, Callable]] = None,
    ) -> None:
        """
        Handle a message received from a specific WebSocket client.

        Default handlers:
        - ping: Update last_ping timestamp

        Args:
            user_id: Sender user ID
            websocket: The specific WebSocket that sent the message
            data: Raw message data (JSON string)
            handlers: Optional custom message handlers
        """
        conn = self._find_connection(user_id, websocket)
        if conn is None:
            return

        try:
            message = json.loads(data)
            message_type = message.get("type", "unknown")

            if message_type == "ping":
                conn.last_ping = utc_now().isoformat()
                await conn.websocket.send_json({"type": "pong"})
                return

            if message_type == "resume":
                logger.info(
                    "WS resume requested: user_id=%s job_id=%s last_seq=%s",
                    user_id,
                    message.get("job_id"),
                    message.get("last_seq"),
                )
                await self._handle_resume(user_id, websocket, message)
                return

            if handlers and message_type in handlers:
                await handlers[message_type](user_id, message)

        except json.JSONDecodeError:
            logger.warning("Invalid JSON from user_id=%s", user_id)
        except Exception as e:
            logger.error("Error handling client message: %s", e)

    async def handle_binary_message(
        self,
        user_id: str,
        websocket: WebSocket,
        data: bytes,
    ) -> None:
        """Handle a binary frame received from a WebSocket client.

        Binary frames carry audio data for voice streaming.
        Protocol: first byte is the message type header:
          0x01 = audio chunk (PCM 16kHz mono)
          0x02 = end of utterance
          0x03 = cancel voice stream
        Remaining bytes are the payload.
        """
        if len(data) < 1:
            return

        conn = self._find_connection(user_id, websocket)
        if conn is None:
            return

        header = data[0]
        payload = data[1:]

        try:
            if header == 0x01:
                await self._handle_audio_chunk(conn, payload)
            elif header == 0x02:
                await self._handle_audio_end(conn)
            elif header == 0x03:
                await self._handle_audio_cancel(conn)
            else:
                logger.warning(
                    "WS binary unknown header: user_id=%s header=0x%02x",
                    user_id, header,
                )
        except Exception as e:
            logger.error(
                "WS binary handler error: user_id=%s header=0x%02x error=%s",
                user_id, header, e,
            )
            # Clean up voice stream on error but keep WS alive
            await self._cleanup_voice_stream(conn)
            try:
                await websocket.send_json({
                    "type": "voice_error",
                    "error": "Voice stream error, please try again",
                })
            except Exception:
                pass

    async def _handle_audio_chunk(self, conn: ConnectionInfo, payload: bytes) -> None:
        """Forward audio chunk to voice stream, creating session if needed."""
        if conn.voice_stream is None:
            # Check feature flag early before creating a session (V-B-14)
            from ...config.settings import settings as app_settings
            if not app_settings.voice_streaming_enabled:
                try:
                    await conn.websocket.send_json({
                        "type": "voice_error",
                        "error": "Voice streaming is not enabled",
                    })
                except Exception:
                    pass
                return
            await self._create_voice_stream(conn)
        if conn.voice_stream is not None:
            await conn.voice_stream.send_audio(payload)

    async def _handle_audio_end(self, conn: ConnectionInfo) -> None:
        """Signal end of utterance to voice stream.

        Does NOT null voice_stream immediately — the session's _closed flag
        prevents new audio, and the dispatch task may still be running (V-B-10).
        """
        logger.info("WS binary audio_end: user_id=%s", conn.user_id)
        if conn.voice_stream is not None:
            await conn.voice_stream.end_audio()

    async def _handle_audio_cancel(self, conn: ConnectionInfo) -> None:
        """Cancel active voice stream."""
        logger.info("WS binary audio_cancel: user_id=%s", conn.user_id)
        if conn.voice_stream is not None:
            await conn.voice_stream.cancel()
            conn.voice_stream = None

    async def _create_voice_stream(self, conn: ConnectionInfo) -> None:
        """Create a new VoiceStreamSession for the connection."""
        from ...ai_engine.voice.stream_session import VoiceStreamSession

        # Cancel any existing stream first (one active per user)
        await self._cleanup_voice_stream(conn)

        session = VoiceStreamSession(
            user_id=conn.user_id,
            family_id=conn.family_id,
            websocket=conn.websocket,
            on_dispatch=self._dispatch_voice_text,
        )
        try:
            await session.start()
            conn.voice_stream = session
        except Exception as e:
            logger.warning(
                "voice_stream_create_failed: user_id=%s error=%s",
                conn.user_id, e,
            )
            await session.close()
            try:
                await conn.websocket.send_json({
                    "type": "voice_error",
                    "error": "Voice streaming unavailable",
                })
            except Exception:
                pass

    async def _cleanup_voice_stream(self, conn: ConnectionInfo) -> None:
        """Clean up any active voice stream on a connection."""
        if conn.voice_stream is not None:
            try:
                await conn.voice_stream.close()
            except Exception:
                pass
            conn.voice_stream = None

    async def _dispatch_voice_text(
        self, user_id: str, family_id: str, text: str,
    ) -> None:
        """Dispatch final transcription through the chat pipeline.

        Called by VoiceStreamSession when final transcription is ready.
        Accepts family_id directly from the session to avoid a lookup
        that may fail if the user disconnects before dispatch (V-B-1).

        Uses the same ``_dispatch_ws_chat_job`` path as the HTTP chat
        endpoint so the message is properly classified, persisted, and
        routed to the agent worker.
        """
        _MAX_VOICE_TEXT_LENGTH = 10000
        sanitized = text.strip()[:_MAX_VOICE_TEXT_LENGTH]
        if not sanitized:
            return

        if not family_id:
            logger.warning(
                "voice_dispatch_no_family_id: user_id=%s text=%r",
                user_id, sanitized[:50],
            )
            return

        try:
            from ...api.v1.chat import ChatRequest, _dispatch_ws_chat_job
            from ...db.session import get_db_session
            from uuid import UUID

            request = ChatRequest(message=sanitized)
            async with get_db_session() as db:
                response = await _dispatch_ws_chat_job(
                    request=request,
                    db=db,
                    user_id=UUID(user_id),
                    family_id=UUID(family_id),
                )

            # Notify the mobile client about the new job_id so it can
            # correlate incoming AI response events (otherwise the stale
            # job filter drops them).
            job_event = {
                "type": "voice_chat_started",
                "job_id": response.job_id,
                "session_id": response.session_id,
                "route_type": response.route_type,
            }

            # Direct WS send to all active connections
            direct_sent = False
            conns = self._connections.get(user_id)
            if conns:
                for c in conns:
                    if c.state in (
                        ConnectionState.SUBSCRIBED,
                        ConnectionState.CONNECTED,
                    ):
                        try:
                            await c.websocket.send_json(job_event)
                            direct_sent = True
                        except Exception:
                            pass

            # PubSub fallback — ensures delivery even if all direct
            # sends failed (V-B-3).
            if not direct_sent:
                try:
                    await self.pubsub.publish(
                        user_id,
                        PubSubMessage(
                            user_id=user_id,
                            message_type="voice_chat_started",
                            payload=job_event,
                            trace_id=response.job_id or "",
                            job_id=response.job_id,
                        ),
                    )
                except Exception:
                    logger.error(
                        "voice_chat_started pubsub fallback failed: user_id=%s",
                        user_id,
                    )

            logger.info(
                "voice_dispatch_ok: user_id=%s job_id=%s route=%s text=%r",
                user_id, response.job_id, response.route_type,
                sanitized[:50],
            )
        except Exception as e:
            logger.error(
                "voice_dispatch_failed: user_id=%s text=%r error=%s",
                user_id, sanitized[:50], e,
            )

    def _find_connection(self, user_id: str, websocket: WebSocket) -> Optional[ConnectionInfo]:
        """Find the ConnectionInfo for a specific websocket."""
        conns = self._connections.get(user_id)
        if not conns:
            return None
        for conn in conns:
            if conn.websocket is websocket:
                return conn
        return None

    async def _handle_resume(
        self, user_id: str, websocket: WebSocket, message: Dict[str, Any]
    ) -> None:
        """Handle a ``resume`` message from the client.

        The client sends ``{"type": "resume", "job_id": "...", "last_seq": N}``
        after reconnecting to recover messages missed during the gap.

        Recovery strategy (ordered by reliability):
        1. JobMessageLog (per-job ZSET) - precise seq-based recovery
        2. OfflineMessageQueue (per-user list) - fallback for older messages
        """
        job_id = message.get("job_id")
        last_seq = message.get("last_seq", 0)

        if not job_id or not isinstance(last_seq, int):
            logger.warning(
                "WS resume invalid request: user_id=%s job_id=%s last_seq=%s",
                user_id,
                job_id,
                last_seq,
            )
            await websocket.send_json({
                "type": "resume_error",
                "message": "Missing job_id or invalid last_seq",
            })
            return

        try:
            recovered: List[Dict[str, Any]] = []

            # Primary: recover from JobMessageLog (per-job ordered ZSET)
            try:
                from ..pubsub.job_message_log import get_job_message_log
                job_log = get_job_message_log()
                recovered = await job_log.get_after(job_id, last_seq)
            except Exception as jl_err:
                logger.warning(
                    "JobMessageLog recovery failed for job %s, "
                    "falling back to offline queue: %s",
                    job_id, jl_err,
                )

            # Fallback: if job log returned nothing, try offline queue
            if not recovered:
                try:
                    from ..pubsub.offline_queue import get_offline_queue
                    queue = get_offline_queue()
                    recovered = await queue.drain_for_job(user_id, job_id, last_seq)
                except Exception as oq_err:
                    logger.warning(
                        "Offline queue recovery also failed for job %s: %s",
                        job_id, oq_err,
                    )

            for msg_dict in recovered:
                try:
                    await websocket.send_json(msg_dict)
                except Exception:
                    break

            await websocket.send_json({
                "type": "resume_complete",
                "job_id": job_id,
                "recovered_count": len(recovered),
            })
            logger.info(
                "WS resume complete: user_id=%s job_id=%s last_seq=%d recovered=%d",
                user_id,
                job_id,
                last_seq,
                len(recovered),
            )
        except Exception as e:
            logger.warning("Resume failed for user %s job %s: %s", user_id, job_id, e)
            await websocket.send_json({
                "type": "resume_error",
                "message": "Failed to recover messages",
            })

    async def graceful_shutdown(self) -> None:
        """Broadcast server_shutdown to all clients and close connections.

        Called from the application lifespan shutdown sequence to give clients
        a chance to prepare for reconnection.
        """
        logger.info("WebSocket graceful shutdown: notifying %d users", len(self._connections))

        # Broadcast shutdown notice
        await self.broadcast_to_all({"type": "server_shutdown"})

        # Close all connections
        for user_id in list(self._connections.keys()):
            await self.disconnect(user_id)

    async def run_with_keepalive(
        self,
        user_id: str,
        websocket: WebSocket,
        keepalive_interval: int = 30,
        resume_job_id: Optional[str] = None,
        last_seq: Optional[int] = None,
    ) -> None:
        """
        Run a single WebSocket connection with keepalive and message handling.

        Implements a reconnect gap recovery sequence:
        1. First drain offline queue (messages buffered while disconnected)
        2. Subscribe to PubSub (live messages start flowing)
        3. Second drain offline queue (covers the gap between step 1-2)
        4. If resume params provided, recover from JobMessageLog

        Args:
            user_id: User ID for the connection
            websocket: The specific WebSocket instance
            keepalive_interval: Seconds between keepalive pings
            resume_job_id: Optional job_id from query params for gap recovery
            last_seq: Optional last received seq from query params
        """
        conn = self._find_connection(user_id, websocket)
        if conn is None:
            return

        logger.info(
            "WS run_with_keepalive start: user_id=%s keepalive_interval=%s "
            "resume_job_id=%s last_seq=%s",
            user_id,
            keepalive_interval,
            resume_job_id,
            last_seq,
        )

        # Step 1: First drain offline queue
        await self._drain_offline_queue(user_id, websocket)

        # Step 2: Start shared Pub/Sub subscription if not already running
        async with self._lock:
            existing_task = self._subscription_tasks.get(user_id)
            if existing_task is None or existing_task.done():
                task = asyncio.create_task(self.start_listening(user_id))
                self._subscription_tasks[user_id] = task

        # Mark connection as subscribed
        conn.state = ConnectionState.SUBSCRIBED

        # Step 3: Second drain offline queue (covers gap between step 1-2)
        await self._drain_offline_queue(user_id, websocket)

        # Step 4: If client sent resume params, recover from JobMessageLog
        if resume_job_id and last_seq is not None:
            await self._recover_from_job_log(
                user_id, websocket, resume_job_id, last_seq
            )

        # Per-device keepalive
        async def keepalive():
            while True:
                c = self._find_connection(user_id, websocket)
                if c is None:
                    break
                try:
                    await websocket.send_json({"type": "keepalive"})
                except Exception:
                    break
                await asyncio.sleep(keepalive_interval)

        keepalive_task = asyncio.create_task(keepalive())

        try:
            while True:
                message = await websocket.receive()
                if "text" in message:
                    await self.handle_client_message(
                        user_id, websocket, message["text"],
                    )
                elif "bytes" in message:
                    await self.handle_binary_message(
                        user_id, websocket, message["bytes"],
                    )
                elif message.get("type") == "websocket.disconnect":
                    logger.info(
                        "WS graceful close: user_id=%s code=%s",
                        user_id, message.get("code"),
                    )
                    break
                else:
                    logger.warning(
                        "WS unknown frame type: user_id=%s keys=%s",
                        user_id, list(message.keys()),
                    )

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: user_id=%s", user_id)
        except Exception as e:
            logger.error("WebSocket error: %s", e)
        finally:
            keepalive_task.cancel()
            await self.disconnect_one(user_id, websocket)

    async def _drain_offline_queue(self, user_id: str, websocket: WebSocket) -> None:
        """Drain the offline message queue and send buffered messages to the client."""
        try:
            from ..pubsub.offline_queue import get_offline_queue

            queue = get_offline_queue()
            messages = await queue.drain(user_id)
            if messages:
                logger.info(
                    "WS offline_queue drain: user_id=%s count=%d",
                    user_id,
                    len(messages),
                )
            for msg_dict in messages:
                try:
                    await websocket.send_json(msg_dict)
                except Exception as e:
                    logger.warning(
                        "Failed to send offline message to user %s: %s",
                        user_id, e,
                    )
                    break
        except Exception as e:
            logger.warning("Failed to drain offline queue for %s: %s", user_id, e)

    async def _recover_from_job_log(
        self,
        user_id: str,
        websocket: WebSocket,
        job_id: str,
        last_seq: int,
    ) -> None:
        """Recover missed messages for a specific job from the JobMessageLog."""
        try:
            from ..pubsub.job_message_log import get_job_message_log

            job_log = get_job_message_log()
            messages = await job_log.get_after(job_id, last_seq)
            for msg_dict in messages:
                try:
                    await websocket.send_json(msg_dict)
                except Exception:
                    break

            if messages:
                logger.info(
                    "Job log recovery: user=%s job=%s after_seq=%d recovered=%d",
                    user_id, job_id, last_seq, len(messages),
                )
            await websocket.send_json({
                "type": "resume_complete",
                "job_id": job_id,
                "recovered_count": len(messages),
            })
        except Exception as e:
            logger.warning(
                "Job log recovery failed for user %s job %s: %s",
                user_id, job_id, e,
            )


# Global instance
_ws_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the global WebSocket manager."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager
