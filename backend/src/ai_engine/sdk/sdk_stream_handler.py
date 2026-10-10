"""
SDK Stream Handler - Handles Claude Agent SDK message types for PubSub dispatch.

Replaces stream_handler.py (which handles raw Anthropic API events).
Processes SDK message types (AssistantMessage, ResultMessage, etc.)
and maps them to Redis PubSub events for WebSocket delivery.

SDK Message Type → PubSub Event mapping:
    AssistantMessage + TextBlock      →  content
    AssistantMessage + ToolUseBlock   →  tool_call
    AssistantMessage + ThinkingBlock  →  thinking
    ResultMessage                     →  done
    StreamEvent (partial)             →  content (streaming chunks)
"""

import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SDKStreamHandler:
    """
    Processes messages yielded by SDK query()/ClaudeSDKClient and
    dispatches them via a publish callback (typically Redis PubSub).

    Usage:
        handler = SDKStreamHandler(
            publish_fn=pubsub.publish,
            channel=f"agent:result:{job_id}",
        )
        async for message in client.receive_response():
            await handler.handle_sdk_message(message)
        await handler.emit_done(session_id=..., message_id=...)
    """

    # Events whose loss would leave the client in a broken state.
    _CRITICAL_EVENTS = frozenset({"done", "error"})

    def __init__(
        self,
        publish_fn: Callable[[str, Dict[str, Any]], Awaitable[None]],
        channel: str,
        job_id: Optional[str] = None,
    ):
        self._publish = publish_fn
        self._channel = channel
        self._job_id = job_id

        self._text_chunks: List[str] = []
        self._thinking_chunks: List[str] = []
        self._thinking_streamed: bool = False
        self._thinking_emitted: bool = False
        self._content_streamed: bool = False
        self._content_emitted: bool = False
        self._content_emit_count: int = 0
        self._content_publish_failed: bool = False
        self._tool_publish_failed: bool = False
        self._failed_events: List[Dict[str, Any]] = []
        self._in_thinking_block: bool = False
        self._tool_calls: List[Dict[str, Any]] = []

        # Buffer for detecting and suppressing "(no content)" in text_delta
        self._text_buffer: str = ""
        self._NO_CONTENT_PATTERNS: tuple = ("(no content)", "(No content)")
        # Thinking delta batch buffer — reduces Redis publish frequency
        # by merging high-frequency small thinking chunks into fewer larger ones.
        self._thinking_emit_buffer: str = ""
        self._THINKING_BATCH_SIZE: int = 200  # flush when buffer >= this many chars
        # Content delta batch buffer — reduces Redis/WebSocket message flood
        # by merging high-frequency small text_delta tokens (2-9 chars each)
        # into fewer, larger publishes.  Sits AFTER the "(no content)" filter.
        self._content_emit_buffer: str = ""
        self._CONTENT_BATCH_SIZE: int = 80  # ~10-15 tokens, ~100-200ms at LLM speed
        self._stop_reason: Optional[str] = None
        self._usage: Optional[Dict[str, Any]] = None
        self._total_cost_usd: Optional[float] = None
        self._num_turns: int = 0
        self._session_id: Optional[str] = None
        self._generation_context: Optional[Dict[str, Any]] = None
        # Timing instrumentation for stream latency
        self._created_at = time.monotonic()
        self._first_stream_event_at: Optional[float] = None
        self._first_assistant_block_at: Optional[float] = None
        self._first_content_text_at: Optional[float] = None

    def _log_latency(self, label: str) -> None:
        elapsed = time.monotonic() - self._created_at
        logger.info(
            "SDK stream latency %s: %.2fs (job_id=%s)",
            label,
            elapsed,
            self._job_id,
        )

    async def handle_sdk_message(self, message: Any) -> None:
        """Handle a message yielded by SDK query()/ClaudeSDKClient.

        Dispatches based on message type to specialized handlers.
        """
        from claude_agent_sdk import (
            AssistantMessage,
            ResultMessage,
            SystemMessage,
        )

        if isinstance(message, AssistantMessage):
            await self._handle_assistant_message(message)
        elif isinstance(message, ResultMessage):
            await self._handle_result_message(message)
        elif isinstance(message, SystemMessage):
            content = getattr(message, "content", None) or getattr(message, "text", None)
            if content:
                logger.info(
                    "SDK SystemMessage: %s (job_id=%s)",
                    str(content)[:200], self._job_id,
                )
        else:
            # StreamEvent or unknown type - try to handle partial
            await self._handle_stream_event(message)

    async def _handle_assistant_message(self, message: Any) -> None:
        """Process an AssistantMessage with its content blocks.

        The ``_content_streamed`` / ``_thinking_streamed`` flags are checked
        per-block to skip content already delivered via streaming deltas, but
        reset only **after** all blocks have been processed.  This prevents a
        flag reset from the first TextBlock causing a second TextBlock in the
        same message to re-emit content that was already streamed.
        """
        from claude_agent_sdk import TextBlock, ToolUseBlock, ThinkingBlock

        # Flush any pending content buffer BEFORE processing blocks so that
        # buffered streaming content is emitted cleanly and the dedup flags
        # reflect the true "already-emitted" state.
        await self._flush_content_emit_buffer()

        for block in message.content:
            if isinstance(block, ThinkingBlock):
                if self._first_assistant_block_at is None:
                    self._first_assistant_block_at = time.monotonic()
                    if self._first_stream_event_at is None:
                        self._log_latency("first_assistant_block_no_stream")
                    else:
                        self._log_latency("first_assistant_block")
                await self._flush_content_emit_buffer()
                if not self._in_thinking_block:
                    self._in_thinking_block = True
                    await self._emit("thinking_start", {"text": ""})
                self._thinking_chunks.append(block.thinking)
                # Skip emitting if already streamed via thinking_delta events
                # to avoid duplicate thinking content on the client.
                if not self._thinking_streamed:
                    await self._emit("thinking", {"text": block.thinking})

            elif isinstance(block, TextBlock):
                if self._first_assistant_block_at is None:
                    self._first_assistant_block_at = time.monotonic()
                    if self._first_stream_event_at is None:
                        self._log_latency("first_assistant_block_no_stream")
                    else:
                        self._log_latency("first_assistant_block")
                await self._flush_thinking_emit_buffer()
                if self._in_thinking_block:
                    self._in_thinking_block = False
                    await self._emit("thinking_end", {"text": ""})
                if (
                    block.text
                    and not self._content_streamed
                    and block.text.strip() not in ("(no content)", "(No content)", "")
                ):
                    self._text_chunks.append(block.text)
                    if self._first_content_text_at is None:
                        self._first_content_text_at = time.monotonic()
                        self._log_latency("first_content_text")
                    await self._emit("content", {"text": block.text})

            elif isinstance(block, ToolUseBlock):
                await self._flush_thinking_emit_buffer()
                await self._flush_text_buffer()
                await self._flush_content_emit_buffer()
                if self._in_thinking_block:
                    self._in_thinking_block = False
                    await self._emit("thinking_end", {"text": ""})
                tool_call = {
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                }
                self._tool_calls.append(tool_call)
                await self._emit("tool_call", {
                    "tool_use_id": block.id,
                    "tool_name": block.name,
                    "arguments": block.input,
                })

        # Reset streaming flags AFTER all blocks so the next turn's
        # AssistantMessage can detect whether its content was streamed.
        self._content_streamed = False
        self._thinking_streamed = False

    async def _handle_result_message(self, message: Any) -> None:
        """Process a ResultMessage (final result from SDK)."""
        await self._flush_thinking_emit_buffer()
        await self._flush_text_buffer()
        await self._flush_content_emit_buffer()
        if self._in_thinking_block:
            self._in_thinking_block = False
            await self._emit("thinking_end", {"text": ""})
        self._stop_reason = message.subtype
        self._num_turns = getattr(message, "num_turns", 0)
        self._total_cost_usd = getattr(message, "total_cost_usd", None)
        self._usage = getattr(message, "usage", None)
        self._session_id = getattr(message, "session_id", None)

        if message.is_error:
            error_text = getattr(message, "result", "Unknown error")
            await self._emit("error", {"message": error_text or "SDK execution error"})
        # If we never saw any stream deltas, log for diagnosis.
        if self._first_stream_event_at is None:
            self._log_latency("result_no_stream_events")
        # Log turn consumption summary for diagnosing max_turns issues.
        logger.info(
            "SDK result summary: stop_reason=%s, turns=%d, "
            "tool_calls=%d, text_chunks=%d, content_emitted=%s (job_id=%s)",
            self._stop_reason,
            self._num_turns,
            len(self._tool_calls),
            len(self._text_chunks),
            self._content_emitted,
            self._job_id,
        )

    async def _handle_stream_event(self, message: Any) -> None:
        """Process a StreamEvent for partial updates."""
        event = getattr(message, "event", None)
        if not event or not isinstance(event, dict):
            return

        event_type = event.get("type", "")

        if event_type == "content_block_start":
            await self._flush_text_buffer()
            await self._flush_content_emit_buffer()
            block = event.get("content_block", {}) or {}
            block_type = block.get("type", "")
            if block_type == "thinking":
                if not self._in_thinking_block:
                    self._in_thinking_block = True
                    await self._emit("thinking_start", {"text": ""})
                initial_thinking = block.get("thinking") or block.get("text") or ""
                if initial_thinking:
                    # Flush any pending buffer before emitting initial_thinking
                    # to preserve chronological order of thinking text.
                    await self._flush_thinking_emit_buffer()
                    self._thinking_chunks.append(initial_thinking)
                    self._thinking_streamed = True
                    await self._emit("thinking", {"text": initial_thinking})
            return

        if event_type == "content_block_stop":
            await self._flush_thinking_emit_buffer()
            await self._flush_text_buffer()
            await self._flush_content_emit_buffer()
            if self._in_thinking_block:
                self._in_thinking_block = False
                await self._emit("thinking_end", {"text": ""})
            return

        if event_type in ("thinking_delta", "text_delta"):
            delta = event
        else:
            delta = event.get("delta", {})

        if not isinstance(delta, dict):
            return

        delta_type = delta.get("type", event_type)
        text = delta.get("text", "")
        thinking = delta.get("thinking", "")

        if delta_type == "text_delta" and text:
            if self._first_stream_event_at is None:
                self._first_stream_event_at = time.monotonic()
                self._log_latency("first_text_delta")
            # Flush any pending thinking before switching to content
            await self._flush_thinking_emit_buffer()
            await self._buffer_text_delta(text)

        if delta_type == "thinking_delta" and thinking:
            if self._first_stream_event_at is None:
                self._first_stream_event_at = time.monotonic()
                self._log_latency("first_thinking_delta")
            # Flush any pending content before switching to thinking
            await self._flush_text_buffer()
            await self._flush_content_emit_buffer()
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "thinking_delta: len=%d, total_chunks=%d, job_id=%s",
                    len(thinking),
                    len(self._thinking_chunks) + 1,
                    self._job_id,
                )
            if not self._in_thinking_block:
                self._in_thinking_block = True
                await self._emit("thinking_start", {"text": ""})
            self._thinking_chunks.append(thinking)
            self._thinking_streamed = True
            await self._buffer_thinking_delta(thinking)

    async def _buffer_text_delta(self, text: str) -> None:
        """Buffer text_delta chunks and filter out "(no content)" patterns.

        Accumulates text into a buffer. If the buffer matches a no-content
        pattern, it is discarded. If the buffer cannot possibly match any
        pattern, it is flushed as real content. If it is still a prefix of
        a pattern, we keep buffering.

        Uses ``.strip()`` on the buffer so leading/trailing whitespace does
        not defeat the pattern match (e.g. ``"(no content)\\n"``).
        """
        self._text_buffer += text
        stripped = self._text_buffer.strip()

        # Check if stripped buffer exactly matches a no-content pattern → discard
        if stripped in self._NO_CONTENT_PATTERNS:
            self._text_buffer = ""
            return

        # Check if stripped buffer is a prefix of any no-content pattern → keep buffering
        # An empty stripped (whitespace only) is kept buffering as it could precede a pattern.
        is_prefix = (not stripped) or any(
            p.startswith(stripped) for p in self._NO_CONTENT_PATTERNS
        )
        if is_prefix:
            return

        # Buffer is not a prefix of any pattern → flush as content
        await self._flush_text_buffer()

    async def _flush_text_buffer(self) -> None:
        """Flush any buffered text_delta content into the content emit buffer.

        After passing the "(no content)" pattern filter, text is accumulated
        in ``_content_emit_buffer`` and only published when the batch size
        threshold is reached (or at an explicit flush point).
        """
        if not self._text_buffer:
            return
        buffered = self._text_buffer
        self._text_buffer = ""
        self._text_chunks.append(buffered)
        self._content_streamed = True
        if self._first_content_text_at is None:
            self._first_content_text_at = time.monotonic()
            self._log_latency("first_content_text")
        self._content_emit_buffer += buffered
        if len(self._content_emit_buffer) >= self._CONTENT_BATCH_SIZE:
            await self._flush_content_emit_buffer()

    async def _flush_content_emit_buffer(self) -> None:
        """Emit accumulated content buffer as a single publish call."""
        if not self._content_emit_buffer:
            return
        buffered = self._content_emit_buffer
        self._content_emit_buffer = ""
        await self._emit("content", {"text": buffered})

    async def _buffer_thinking_delta(self, text: str) -> None:
        """Buffer a thinking delta and flush when batch size is reached.

        Merges high-frequency small thinking deltas (often a few chars each)
        into fewer, larger publish calls.  The buffer is also flushed on any
        event-type transition (thinking_end, content_block_stop, text_delta,
        result) so data integrity is preserved.
        """
        self._thinking_emit_buffer += text
        if len(self._thinking_emit_buffer) >= self._THINKING_BATCH_SIZE:
            await self._flush_thinking_emit_buffer()

    async def _flush_thinking_emit_buffer(self) -> None:
        """Emit accumulated thinking buffer as a single publish call."""
        if not self._thinking_emit_buffer:
            return
        buffered = self._thinking_emit_buffer
        self._thinking_emit_buffer = ""
        await self._emit("thinking", {"text": buffered})

    async def emit_done(
        self,
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> None:
        """Emit the final done event.

        Includes full thinking content so the client can reconcile any
        thinking deltas that were lost during streaming.
        """
        await self._flush_content_emit_buffer()
        done_data: Dict[str, Any] = {
            "session_id": session_id or self._session_id,
            "message_id": message_id,
            "job_id": self._job_id,
            "stop_reason": self._stop_reason,
            "usage": self._usage or {},
            "total_cost_usd": self._total_cost_usd,
            "num_turns": self._num_turns,
        }
        # Attach full thinking for client reconciliation
        full_thinking = self.final_thinking
        if full_thinking:
            done_data["thinking"] = full_thinking
        if self._failed_events:
            done_data["failed_events"] = list(self._failed_events)
        await self._emit("done", done_data)

    async def emit_error(self, error: str) -> None:
        """Emit an error event."""
        await self._flush_content_emit_buffer()
        await self._emit("error", {"message": error})

    async def emit_content_final(self) -> None:
        """Signal that all content has been emitted."""
        await self._emit("content_final", {})

    async def emit_missing_thinking(self, chunk_size: int = 400) -> None:
        """Emit buffered thinking if no streaming thinking was sent."""
        await self._flush_content_emit_buffer()
        thinking = self.final_thinking
        if not thinking or self._thinking_emitted:
            return
        await self._emit("thinking_start", {"text": ""})
        for idx in range(0, len(thinking), chunk_size):
            await self._emit("thinking", {"text": thinking[idx:idx + chunk_size]})
        await self._emit("thinking_end", {"text": ""})
        self._thinking_emitted = True

    async def _emit(
        self,
        event_type: str,
        data: Dict[str, Any],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish an event via the configured publish function.

        Args:
            event_type: The event type string (e.g. "content", "done").
            data: Event payload data.
            meta: Optional metadata dict with full-duplex fields such as
                is_partial, generation_id, turn_index, signal_source,
                continues_from. When provided, merged into the message
                under the "meta" key.
        """
        message = {
            "type": event_type,
            "job_id": self._job_id,
            **data,
        }
        if meta:
            message["meta"] = meta
        if self._generation_context and event_type in ("content", "thinking", "partial_content"):
            message["meta"] = {**(meta or {}), **self._generation_context}
        try:
            await self._publish(self._channel, message)
            # Mark thinking as emitted AFTER successful publish so that
            # emit_missing_thinking can re-send if all publishes failed.
            if event_type == "thinking" and data.get("text"):
                self._thinking_emitted = True
            if event_type == "content" and data.get("text") is not None:
                self._content_emitted = True
                self._content_emit_count += 1
                text_len = len(data["text"]) if data["text"] else 0
                if self._content_emit_count <= 3 or self._content_emit_count % 10 == 0:
                    logger.info(
                        "SDK content emit #%d: text_len=%d, total_chunks=%d, "
                        "streamed=%s (job_id=%s)",
                        self._content_emit_count,
                        text_len,
                        len(self._text_chunks),
                        self._content_streamed,
                        self._job_id,
                    )
        except Exception as e:
            if event_type == "content":
                self._content_publish_failed = True
            if event_type == "tool_execution":
                self._tool_publish_failed = True
            self._failed_events.append({"type": event_type, "error": str(e)})
            logger.error(
                "Failed to publish event %s for job %s on channel %s: %s",
                event_type, self._job_id, self._channel, e,
            )
            if event_type in self._CRITICAL_EVENTS:
                raise

    @property
    def final_text(self) -> str:
        """Get the complete text response."""
        return "".join(self._text_chunks)

    @property
    def content_emitted(self) -> bool:
        """Whether at least one content chunk was published successfully."""
        return self._content_emitted

    @property
    def content_publish_failed(self) -> bool:
        """Whether any content publish attempt failed during streaming."""
        return self._content_publish_failed

    @property
    def tool_publish_failed(self) -> bool:
        """Whether any tool_execution publish attempt failed during streaming."""
        return self._tool_publish_failed

    @property
    def failed_events(self) -> List[Dict[str, Any]]:
        """List of events that failed to publish, with type and error."""
        return list(self._failed_events)

    @property
    def final_thinking(self) -> str:
        """Get the complete thinking content."""
        return "".join(self._thinking_chunks)

    @property
    def stop_reason(self) -> Optional[str]:
        return self._stop_reason

    @property
    def usage(self) -> Optional[Dict[str, Any]]:
        return self._usage

    @property
    def num_turns(self) -> int:
        return self._num_turns

    @property
    def total_cost_usd(self) -> Optional[float]:
        return self._total_cost_usd

    async def handle_sub_agent_message(self, message: Any) -> None:
        """Process a message from a sub-agent execution.

        Public API for sub-agents to dispatch streaming events through the
        parent handler.  Handles AssistantMessage (thinking/content/tool_use
        blocks) and StreamEvent (partial deltas) but deliberately skips
        ResultMessage to avoid corrupting parent state (_stop_reason, etc.).
        """
        from claude_agent_sdk import AssistantMessage, ResultMessage

        if isinstance(message, ResultMessage):
            # Flush any buffered deltas before closing the block
            await self._flush_thinking_emit_buffer()
            await self._flush_content_emit_buffer()
            # Close any open thinking block, but don't touch parent state
            if self._in_thinking_block:
                self._in_thinking_block = False
                await self._emit("thinking_end", {"text": ""})
            return

        if isinstance(message, AssistantMessage):
            await self._handle_assistant_message(message)
        else:
            await self._handle_stream_event(message)

    def set_generation_context(
        self,
        generation_id: str,
        signal_source: Optional[str] = None,
        continues_from: Optional[str] = None,
    ) -> None:
        self._generation_context = {
            "generation_id": generation_id,
            "signal_source": signal_source,
            "continues_from": continues_from,
        }

    def clear_generation_context(self) -> None:
        self._generation_context = None

    def reset(self) -> None:
        """Reset collected state."""
        self._text_chunks.clear()
        self._thinking_chunks.clear()
        self._thinking_streamed = False
        self._thinking_emitted = False
        self._content_streamed = False
        self._content_emit_count = 0
        self._content_publish_failed = False
        self._tool_publish_failed = False
        self._failed_events.clear()
        self._in_thinking_block = False
        self._tool_calls.clear()
        self._stop_reason = None
        self._usage = None
        self._total_cost_usd = None
        self._num_turns = 0
        self._session_id = None
        self._text_buffer = ""
        self._thinking_emit_buffer = ""
        self._content_emit_buffer = ""
        self._generation_context = None
