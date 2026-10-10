"""
Redis Pub/Sub Manager for distributed messaging.

Enables Agent Workers to push results to API Gateway for WebSocket delivery.
"""
import asyncio
import json
import logging
from typing import AsyncIterator, Callable, Dict, Optional, Set

import redis.asyncio as redis

from ...config.settings import settings
from .types import PubSubMessage, MessageType


logger = logging.getLogger(__name__)

# Message types critical enough to warrant job-log persistence
_CRITICAL_TYPES = frozenset({
    MessageType.CONTENT,
    MessageType.COMPLETE,
    MessageType.ERROR,
    MessageType.CONFIRM_CARD,
    MessageType.TOOL_EXECUTION,
    MessageType.ASK_USER_QUESTION,
})


class RedisPubSubManager:
    """
    Manages Redis Pub/Sub for cross-process messaging.

    Usage:
        # Publisher (Agent Worker)
        manager = RedisPubSubManager()
        await manager.connect()
        await manager.publish(
            user_id="user_123",
            message=PubSubMessage(
                user_id="user_123",
                message_type=MessageType.CONTENT,
                payload={"content": "Hello!"},
                trace_id="trace_abc",
            )
        )

        # Subscriber (API Gateway)
        async for message in manager.subscribe("user_123"):
            await websocket.send_json(message.to_dict())
    """

    # Channel prefix for user-specific channels
    CHANNEL_PREFIX = "ws"

    def __init__(self):
        self._publisher: Optional[redis.Redis] = None
        self._subscriber: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._active_subscriptions: Set[str] = set()
        self._lock = asyncio.Lock()
        self._job_log = None  # lazy-initialized JobMessageLog

    async def connect(self) -> None:
        """Initialize Redis connections for publishing and subscribing."""
        if self._publisher is None:
            self._publisher = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
            )

        if self._subscriber is None:
            self._subscriber = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
            )
            self._pubsub = self._subscriber.pubsub()

        logger.info("Redis Pub/Sub manager connected")

    async def disconnect(self) -> None:
        """Close Redis connections."""
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
            self._pubsub = None

        if self._subscriber:
            await self._subscriber.close()
            self._subscriber = None

        if self._publisher:
            await self._publisher.close()
            self._publisher = None

        self._active_subscriptions.clear()
        logger.info("Redis Pub/Sub manager disconnected")

    def get_user_channel(self, user_id: str) -> str:
        """
        Get the channel name for a specific user.

        Format: ws:{user_id}
        """
        return f"{self.CHANNEL_PREFIX}:{user_id}"

    async def publish(self, user_id: str, message: PubSubMessage) -> int:
        """
        Publish a message to a user's channel.

        When no subscribers are connected (receivers == 0), eligible messages
        are buffered in the offline queue for gap recovery on reconnect.

        Args:
            user_id: Target user ID
            message: Message to publish

        Returns:
            Number of subscribers that received the message
        """
        if self._publisher is None:
            await self.connect()

        channel = self.get_user_channel(user_id)
        message_json = json.dumps(message.to_dict(), ensure_ascii=False)
        msg_type = (
            message.message_type
            if isinstance(message.message_type, MessageType)
            else MessageType(str(message.message_type))
            if str(message.message_type) in MessageType._value2member_map_
            else None
        )
        msg_type_value = (
            msg_type.value if msg_type is not None else str(message.message_type)
        )
        payload = message.payload if isinstance(message.payload, dict) else {}
        content_value = payload.get("content")
        content_len = len(content_value) if isinstance(content_value, str) else 0

        try:
            # A2: Dual-write critical messages to per-job log BEFORE PubSub publish
            # so the log is guaranteed to exist even if publish crashes mid-way.
            if (
                message.job_id
                and message.seq is not None
                and message.message_type in _CRITICAL_TYPES
            ):
                try:
                    if self._job_log is None:
                        from .job_message_log import get_job_message_log
                        self._job_log = get_job_message_log()
                    await self._job_log.append(
                        message.job_id, message.seq, message.to_dict()
                    )
                except Exception as jl_err:
                    logger.warning(
                        "Failed to write to job message log for job %s: %s",
                        message.job_id, jl_err,
                    )

            try:
                receivers = await asyncio.wait_for(
                    self._publisher.publish(channel, message_json),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Redis publish timeout (5s): channel=%s type=%s "
                    "job_id=%s seq=%s",
                    channel,
                    msg_type_value,
                    message.job_id,
                    message.seq,
                )
                # Set receivers=0 so offline queue captures the message
                # as a fallback. For _CRITICAL_TYPES the job_log already
                # has the message (written synchronously above).
                receivers = 0
            logger.debug(
                f"Published message to {channel}, "
                f"type={message.message_type}, receivers={receivers}"
            )
            should_trace_publish = (
                msg_type in {
                    MessageType.COMPLETE,
                    MessageType.ERROR,
                    MessageType.BACKGROUND_JOB,
                    MessageType.CONFIRM_CARD,
                    MessageType.ASK_USER_QUESTION,
                }
                or (msg_type == MessageType.CONTENT and message.seq in {1, 2, 3})
            )
            if should_trace_publish:
                logger.info(
                    "PubSub publish trace: channel=%s type=%s user=%s trace_id=%s "
                    "job_id=%s seq=%s receivers=%d content_len=%d is_final=%s",
                    channel,
                    msg_type_value,
                    user_id,
                    message.trace_id,
                    message.job_id,
                    message.seq,
                    receivers,
                    content_len,
                    payload.get("is_final"),
                )

            # Buffer in offline queue when no WebSocket subscribers are connected
            if receivers == 0:
                try:
                    from .offline_queue import get_offline_queue
                    queue = get_offline_queue()
                    await queue.push(user_id, message.to_dict())
                    logger.info(
                        "PubSub offline_queue push: channel=%s type=%s user=%s "
                        "job_id=%s seq=%s",
                        channel,
                        msg_type_value,
                        user_id,
                        message.job_id,
                        message.seq,
                    )
                except Exception as oq_err:
                    logger.warning(
                        "Failed to push to offline queue for %s: %s",
                        user_id, oq_err,
                    )

            return receivers
        except Exception as e:
            logger.error(f"Failed to publish message to {channel}: {e}")
            raise

    async def subscribe(self, user_id: str) -> AsyncIterator[PubSubMessage]:
        """
        Subscribe to a user's channel and yield messages.

        Args:
            user_id: User ID to subscribe to

        Yields:
            PubSubMessage objects as they arrive
        """
        if self._pubsub is None:
            await self.connect()

        channel = self.get_user_channel(user_id)

        async with self._lock:
            if channel not in self._active_subscriptions:
                await self._pubsub.subscribe(channel)
                self._active_subscriptions.add(channel)
                logger.info(f"Subscribed to channel: {channel}")

        try:
            async for raw_message in self._pubsub.listen():
                if raw_message["type"] == "message":
                    try:
                        data = json.loads(raw_message["data"])
                        yield PubSubMessage.from_dict(data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid message format: {e}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
        finally:
            async with self._lock:
                if channel in self._active_subscriptions:
                    await self._pubsub.unsubscribe(channel)
                    self._active_subscriptions.discard(channel)
                    logger.info(f"Unsubscribed from channel: {channel}")

    async def subscribe_with_callback(
        self,
        user_id: str,
        callback: Callable[[PubSubMessage], None],
        stop_event: Optional[asyncio.Event] = None,
    ) -> None:
        """
        Subscribe to a user's channel with a callback function.

        Useful when you need non-blocking subscription handling.

        Args:
            user_id: User ID to subscribe to
            callback: Function to call for each message
            stop_event: Optional event to stop the subscription
        """
        async for message in self.subscribe(user_id):
            if stop_event and stop_event.is_set():
                break
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def publish_content(
        self,
        user_id: str,
        content: str,
        trace_id: str,
        is_final: bool = False,
        session_id: Optional[str] = None,
        card_enrichment: Optional[Dict] = None,
        job_id: Optional[str] = None,
        seq: Optional[int] = None,
        failed_events: Optional[list] = None,
    ) -> int:
        """
        Convenience method for publishing content messages.

        Args:
            user_id: Target user
            content: Text content to send
            trace_id: Trace ID for logging
            is_final: Whether this is the final content chunk
            session_id: Chat session ID for mobile client correlation
            card_enrichment: Optional dict with intent, data, quick_actions
                for card-producing tool results (Slow Path enrichment)
            job_id: Optional job ID for dual-write to job message log
            seq: Optional sequence number within the job
            failed_events: Optional list of events that failed during streaming
        """
        payload = {"content": content, "is_final": is_final}
        if session_id:
            payload["session_id"] = session_id
        if card_enrichment:
            payload.update(card_enrichment)
        if failed_events:
            payload["failed_events"] = failed_events
        message_type = MessageType.COMPLETE if is_final else MessageType.CONTENT
        return await self.publish(
            user_id=user_id,
            message=PubSubMessage(
                user_id=user_id,
                message_type=message_type,
                payload=payload,
                trace_id=trace_id,
                job_id=job_id,
                seq=seq,
            )
        )

    async def publish_confirm_card(
        self,
        user_id: str,
        action_id: str,
        action_type: str,
        display_data: Dict,
        trace_id: str,
        job_id: Optional[str] = None,
        seq: Optional[int] = None,
    ) -> int:
        """
        Convenience method for publishing action confirmation cards.

        If no WebSocket subscribers are connected, falls back to FCM push.

        Args:
            user_id: Target user
            action_id: PendingAction ID
            action_type: Type of action (purchase, book_ticket, etc.)
            display_data: Human-readable action details
            trace_id: Trace ID for logging
            job_id: Optional job ID for dual-write to job message log
            seq: Optional sequence number within the job
        """
        receivers = await self.publish(
            user_id=user_id,
            message=PubSubMessage(
                user_id=user_id,
                message_type=MessageType.CONFIRM_CARD,
                payload={
                    "action_id": action_id,
                    "action_type": action_type,
                    "display": display_data,
                },
                trace_id=trace_id,
                job_id=job_id,
                seq=seq,
            )
        )

        if receivers == 0:
            await self._send_push_fallback(
                user_id=user_id,
                action_id=action_id,
                action_type=action_type,
                display_data=display_data,
            )

        return receivers

    async def publish_ask_user_question(
        self,
        user_id: str,
        question_id: str,
        questions: list,
        trace_id: str,
        job_id: Optional[str] = None,
        seq: Optional[int] = None,
    ) -> int:
        """Publish an ask-user-question event via WebSocket.

        Args:
            user_id: Target user
            question_id: Unique question ID (used to match answer)
            questions: List of question dicts from AskUserQuestion tool_input
            trace_id: Trace ID for logging
            job_id: Optional job ID for dual-write to job message log
            seq: Optional sequence number within the job
        """
        return await self.publish(
            user_id=user_id,
            message=PubSubMessage(
                user_id=user_id,
                message_type=MessageType.ASK_USER_QUESTION,
                payload={
                    "question_id": question_id,
                    "questions": questions,
                },
                trace_id=trace_id,
                job_id=job_id,
                seq=seq,
            ),
        )

    async def _send_push_fallback(
        self,
        user_id: str,
        action_id: str,
        action_type: str,
        display_data: Dict,
    ) -> None:
        """
        Send FCM push notification when user has no active WebSocket.

        Queries device tokens from DB, sends push, and deactivates invalid tokens.
        """
        if not settings.fcm_enabled:
            logger.debug(
                f"User {user_id} offline, FCM disabled — "
                f"confirm card {action_id} will be picked up on reconnect"
            )
            return

        try:
            from ...db.session import async_session_maker
            from ...modules.member.device_token_service import DeviceTokenService
            from ..push.fcm_service import send_to_user
            from uuid import UUID

            async with async_session_maker() as session:
                await self._do_push_send(
                    session=session,
                    user_id=UUID(user_id),
                    action_id=action_id,
                    action_type=action_type,
                    display_data=display_data,
                )
        except Exception as e:
            logger.error(f"Push fallback failed for user {user_id}: {e}")

    @staticmethod
    async def _do_push_send(
        session,
        user_id,
        action_id: str,
        action_type: str,
        display_data: Dict,
    ) -> None:
        """Execute the actual FCM push send with a provided DB session.

        Enforces push budget (V8-Brain S7.2) — pending action pushes
        are treated as P1 so they respect the daily limit while P0
        bypasses it.
        """
        from ...modules.member.device_token_service import DeviceTokenService
        from ..push.fcm_service import send_to_user
        from ..push.push_budget import can_push as budget_can_push, record_push

        # Pending action confirmations are important (P1) but not P0-urgent.
        priority_level = "P1"
        allowed = await budget_can_push(user_id, priority_level=priority_level)
        if not allowed:
            logger.info(
                "Push budget exhausted for user %s, "
                "FCM push for action %s suppressed",
                user_id, action_id,
            )
            return

        token_service = DeviceTokenService(session)
        device_tokens = await token_service.get_active_tokens(user_id)

        if not device_tokens:
            logger.debug(
                "User %s has no registered devices — "
                "confirm card %s awaits reconnect",
                user_id, action_id,
            )
            return

        fcm_tokens = [dt.fcm_token for dt in device_tokens]
        title = display_data.get("title", "需要您确认")
        body_parts = [
            f"{d['label']}: {d['value']}"
            for d in display_data.get("details", [])[:2]
        ]
        body = "；".join(body_parts) if body_parts else "请打开应用查看详情"

        invalid_tokens = await send_to_user(
            tokens=fcm_tokens,
            title=title,
            body=body,
            data={
                "type": "pending_action",
                "action_id": action_id,
                "action_type": action_type,
            },
        )

        await record_push(user_id)

        if invalid_tokens:
            await token_service.deactivate_tokens(invalid_tokens)

    async def publish_tool_execution(
        self,
        user_id: str,
        tool_name: str,
        status: str,
        trace_id: str,
        session_id: Optional[str] = None,
        arguments: Optional[Dict] = None,
        result: Optional[Dict] = None,
        summary: Optional[str] = None,
        key_results: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
        execution_id: Optional[str] = None,
        job_id: Optional[str] = None,
        seq: Optional[int] = None,
    ) -> int:
        """
        Publish a tool execution event (start, success, error).

        Args:
            user_id: Target user
            tool_name: Name of the tool being executed
            status: Execution status — "start", "progress", "success", or "error"
            trace_id: Trace ID for logging
            session_id: Chat session ID for mobile client correlation
            arguments: Tool call arguments (sent with start)
            result: Tool execution result (sent with success/error)
            summary: Human-readable summary of the result
            key_results: Structured key results for expandable display
            duration_ms: Execution duration in milliseconds
            execution_id: Unique ID for this execution
            job_id: Optional job ID for dual-write to job message log
            seq: Optional sequence number within the job
        """
        payload: Dict = {
            "tool_name": tool_name,
            "status": status,
        }
        if session_id:
            payload["session_id"] = session_id
        if arguments is not None:
            payload["arguments"] = arguments
        if result is not None:
            payload["result"] = result
        if summary is not None:
            payload["summary"] = summary
            # Also set "message" for progress events so the mobile client
            # can access it via streamEvent.message (mapped from json['message'])
            if status == "progress":
                payload["message"] = summary
        if key_results is not None:
            payload["key_results"] = key_results
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if execution_id is not None:
            payload["execution_id"] = execution_id

        return await self.publish(
            user_id=user_id,
            message=PubSubMessage(
                user_id=user_id,
                message_type=MessageType.TOOL_EXECUTION,
                payload=payload,
                trace_id=trace_id,
                job_id=job_id,
                seq=seq,
            )
        )

    async def publish_thinking(
        self,
        user_id: str,
        content: str,
        trace_id: str,
        session_id: Optional[str] = None,
        phase: str = "chunk",
        job_id: Optional[str] = None,
        seq: Optional[int] = None,
    ) -> int:
        """
        Publish a thinking/reasoning event.

        Args:
            user_id: Target user
            content: Thinking content text
            trace_id: Trace ID for logging
            session_id: Chat session ID for mobile client correlation
            phase: One of "start", "chunk", or "end"
            job_id: Optional job ID for dual-write to job message log
            seq: Optional sequence number within the job
        """
        payload: Dict = {
            "content": content,
            "phase": phase,
        }
        if session_id:
            payload["session_id"] = session_id

        return await self.publish(
            user_id=user_id,
            message=PubSubMessage(
                user_id=user_id,
                message_type=MessageType.THINKING,
                payload=payload,
                trace_id=trace_id,
                job_id=job_id,
                seq=seq,
            )
        )

    async def publish_error(
        self,
        user_id: str,
        error_message: str,
        error_code: Optional[str],
        trace_id: str,
        session_id: Optional[str] = None,
        job_id: Optional[str] = None,
        seq: Optional[int] = None,
    ) -> int:
        """
        Convenience method for publishing error messages.
        """
        payload: Dict = {
            "message": error_message,
            "code": error_code,
        }
        if session_id:
            payload["session_id"] = session_id
        return await self.publish(
            user_id=user_id,
            message=PubSubMessage(
                user_id=user_id,
                message_type=MessageType.ERROR,
                payload=payload,
                trace_id=trace_id,
                job_id=job_id,
                seq=seq,
            )
        )

    async def health_check(self) -> bool:
        """Check if Redis Pub/Sub is healthy."""
        try:
            if self._publisher is None:
                return False
            await self._publisher.ping()
            return True
        except Exception as e:
            logger.error(f"Redis Pub/Sub health check failed: {e}")
            return False


# Global instance for convenience
_pubsub_manager: Optional[RedisPubSubManager] = None


def get_pubsub_manager() -> RedisPubSubManager:
    """Get or create the global Pub/Sub manager."""
    global _pubsub_manager
    if _pubsub_manager is None:
        _pubsub_manager = RedisPubSubManager()
    return _pubsub_manager
