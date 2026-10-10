"""
VoiceStreamSession — manages a single streaming voice session lifecycle.

Created on first audio binary frame, disposed on end-of-utterance or cancel.
Relays partial/final transcriptions back to frontend via WebSocket text messages.
On final transcription, dispatches to the normal text chat pipeline.

Design ref: §2.3.3, TC-3, TC-10, PC-8.
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Optional

from starlette.websockets import WebSocket

from ...config.settings import settings
from .dashscope_realtime import DashscopeRealtimeClient, DashscopeRealtimeError

logger = logging.getLogger(__name__)

# Callback for dispatching final transcription as a ChatRequest
# Signature: (user_id, family_id, text) -> None
DispatchCallback = Callable[[str, str, str], Coroutine[Any, Any, None]]

# Guard limits — prevent unbounded resource consumption (S-001, S-005)
_MAX_AUDIO_CHUNK_SIZE = 65_536  # 64 KB per chunk
_MAX_AUDIO_BUFFER_SIZE = 2 * 1024 * 1024  # 2 MB total per session
_MAX_SESSION_DURATION_SECONDS = 65  # wall-clock timeout (slightly above client's 60s)
_FINAL_TRANSCRIPTION_TIMEOUT = 3.0  # max wait for Dashscope final callback


class VoiceStreamSession:
    """Manages a single streaming voice session for a user.

    Lifecycle:
        1. Created when first binary audio frame (0x01) arrives
        2. Audio chunks forwarded to DashscopeRealtimeClient
        3. Partial/final transcriptions relayed to frontend via WS
        4. On final transcription: dispatches ChatRequest through text pipeline
        5. Disposed on end-of-utterance (0x02), cancel (0x03), or disconnect

    One active session per user — creating a new session cancels the previous.
    All operations isolated via try/except — crashes must not propagate to WS.
    """

    def __init__(
        self,
        user_id: str,
        family_id: str,
        websocket: WebSocket,
        on_dispatch: Optional[DispatchCallback] = None,
    ) -> None:
        self._user_id = user_id
        self._family_id = family_id
        self._websocket = websocket
        self._on_dispatch = on_dispatch
        self._client: Optional[DashscopeRealtimeClient] = None
        self._stream_id: Optional[str] = None
        self._audio_buffer: bytearray = bytearray()
        self._final_text: Optional[str] = None
        self._final_received = asyncio.Event()
        self._closed = False
        self._cleanup_lock = asyncio.Lock()
        self._timeout_task: Optional[asyncio.Task[None]] = None
        self._ending_task: Optional[asyncio.Task[None]] = None

    @property
    def stream_id(self) -> Optional[str]:
        return self._stream_id

    @property
    def is_active(self) -> bool:
        return not self._closed and self._client is not None

    async def start(self) -> None:
        """Start the streaming ASR session.

        Creates a DashscopeRealtimeClient and opens the recognition stream.
        If streaming is disabled or connection fails, raises so the caller
        can fall back to batch ASR.
        """
        if not settings.voice_streaming_enabled:
            raise DashscopeRealtimeError("Voice streaming disabled by config")

        self._client = DashscopeRealtimeClient()
        self._client.on_partial(self._handle_partial)
        self._client.on_final(self._handle_final)
        self._client.on_error(self._handle_error)

        self._stream_id = await self._client.start()
        self._timeout_task = asyncio.create_task(self._session_timeout())
        logger.info(
            "voice_stream_started: user_id=%s stream_id=%s",
            self._user_id, self._stream_id,
        )

    async def send_audio(self, chunk: bytes) -> None:
        """Forward an audio chunk to the ASR client.

        Also accumulates chunks in buffer for batch ASR fallback.
        Enforces per-chunk and per-session size limits (S-001, S-005).
        """
        if self._closed or self._client is None or self._ending_task is not None:
            return
        if len(chunk) > _MAX_AUDIO_CHUNK_SIZE:
            logger.warning(
                "voice_stream_chunk_rejected: user_id=%s size=%d limit=%d",
                self._user_id, len(chunk), _MAX_AUDIO_CHUNK_SIZE,
            )
            return
        if len(self._audio_buffer) + len(chunk) > _MAX_AUDIO_BUFFER_SIZE:
            logger.warning(
                "voice_stream_buffer_full: user_id=%s buffer=%d limit=%d",
                self._user_id, len(self._audio_buffer), _MAX_AUDIO_BUFFER_SIZE,
            )
            # Track the task so subsequent send_audio calls are rejected (V-B-9).
            self._ending_task = asyncio.create_task(
                self.end_audio(),
                name=f"voice-buffer-full-{self._user_id[:8]}",
            )
            return
        self._audio_buffer.extend(chunk)
        try:
            await self._client.send_audio(chunk)
        except DashscopeRealtimeError as e:
            logger.warning(
                "voice_stream_send_failed: user_id=%s error=%s",
                self._user_id, e,
            )
            try:
                await self._websocket.send_json({
                    "type": "voice_error",
                    "error": "Voice stream send failed",
                })
            except Exception:
                pass
            await self._cleanup()

    async def end_audio(self) -> None:
        """Signal end of utterance. Triggers final transcription + dispatch.

        Uses _cleanup_lock at entry to prevent concurrent calls from timeout
        and 0x02 frame both running (V-B-2).
        """
        async with self._cleanup_lock:
            if self._closed or self._client is None:
                return
            self._closed = True  # Prevent re-entry from concurrent callers
            client = self._client  # Capture ref before releasing lock

        try:
            await client.end_audio()
            # Wait for final transcription callback with bounded timeout (V-004).
            # If Dashscope connection was lost, skip the wait (V-B-5).
            if not client._connection_lost.is_set():
                await asyncio.wait_for(
                    self._final_received.wait(),
                    timeout=_FINAL_TRANSCRIPTION_TIMEOUT,
                )
        except asyncio.TimeoutError:
            logger.warning(
                "voice_stream_final_timeout: user_id=%s stream_id=%s",
                self._user_id, self._stream_id,
            )
        except Exception as e:
            logger.warning(
                "voice_stream_end_failed: user_id=%s error=%s",
                self._user_id, e,
            )
        finally:
            await self._cleanup()

    async def cancel(self) -> None:
        """Cancel the voice stream session, discarding all buffered audio."""
        logger.info(
            "voice_stream_cancelled: user_id=%s stream_id=%s",
            self._user_id, self._stream_id,
        )
        await self._cleanup()
        try:
            await self._websocket.send_json({
                "type": "voice_transcription",
                "partial": False,
                "text": "",
                "is_final": True,
                "cancelled": True,
            })
        except Exception:
            pass

    async def close(self) -> None:
        """Clean up resources on disconnect. Idempotent."""
        await self._cleanup()

    async def _session_timeout(self) -> None:
        """Auto-cancel session after wall-clock timeout (S-005)."""
        try:
            await asyncio.sleep(_MAX_SESSION_DURATION_SECONDS)
            if not self._closed:
                logger.warning(
                    "voice_stream_timeout: user_id=%s stream_id=%s after %ds",
                    self._user_id, self._stream_id, _MAX_SESSION_DURATION_SECONDS,
                )
                await self.end_audio()
        except asyncio.CancelledError:
            pass

    async def _cleanup(self) -> None:
        """Internal cleanup — close ASR client and clear state.

        Idempotent. Sets _closed = True on first call; subsequent calls
        are no-ops (the lock + _client None-check prevent double-close).
        """
        async with self._cleanup_lock:
            self._closed = True  # Ensure closed even if called directly
            if self._timeout_task is not None:
                self._timeout_task.cancel()
                self._timeout_task = None
            if self._ending_task is not None and not self._ending_task.done():
                self._ending_task.cancel()
                self._ending_task = None
            if self._client is not None:
                try:
                    await self._client.close()
                except Exception as e:
                    logger.debug(
                        "voice_stream_cleanup_error: user_id=%s error=%s",
                        self._user_id, e,
                    )
                self._client = None
            self._audio_buffer.clear()

    async def _handle_partial(self, text: str, is_final: bool) -> None:
        """Called by DashscopeRealtimeClient with partial transcription."""
        if self._closed:
            return
        try:
            await self._websocket.send_json({
                "type": "voice_transcription",
                "partial": True,
                "text": text,
                "is_final": False,
            })
        except Exception as e:
            logger.warning(
                "voice_stream_partial_send_failed: user_id=%s error=%s",
                self._user_id, e,
            )

    async def _handle_final(self, text: str, is_final: bool) -> None:
        """Called by DashscopeRealtimeClient with final transcription.

        Sends the final text to the frontend and dispatches as a ChatRequest.
        The dispatch is fire-and-forget to avoid blocking the Dashscope
        receive loop (H-1).

        NOTE: Must NOT check self._closed here. end_audio() sets _closed=True
        before waiting for _final_received — blocking on _closed would prevent
        the final callback from ever firing, deadlocking end_audio(). The
        _closed flag guards send_audio() and end_audio() re-entry, not
        callbacks from DashScope.
        """
        self._final_text = text
        self._final_received.set()
        try:
            await self._websocket.send_json({
                "type": "voice_transcription",
                "partial": False,
                "text": text,
                "is_final": True,
            })
        except Exception as e:
            logger.warning(
                "voice_stream_final_send_failed: user_id=%s error=%s",
                self._user_id, e,
            )

        # Dispatch final transcription through the text chat pipeline.
        # Fire-and-forget so the Dashscope receive loop is not blocked.
        if text.strip() and self._on_dispatch:
            asyncio.create_task(
                self._safe_dispatch(text.strip()),
                name=f"voice-dispatch-{self._user_id[:8]}",
            )

    async def _safe_dispatch(self, text: str) -> None:
        """Dispatch wrapper that catches exceptions for fire-and-forget use."""
        try:
            await self._on_dispatch(self._user_id, self._family_id, text)
        except Exception as e:
            logger.error(
                "voice_stream_dispatch_failed: user_id=%s text=%r error=%s",
                self._user_id, text[:50], e,
            )

    async def _handle_error(self, error_msg: str) -> None:
        """Called by DashscopeRealtimeClient on task-failed (V-B-4).

        Notifies the frontend and signals final received so end_audio()
        doesn't hang waiting for a transcription that will never arrive.
        """
        logger.warning(
            "voice_stream_asr_error: user_id=%s stream_id=%s error=%s",
            self._user_id, self._stream_id, error_msg,
        )
        self._final_received.set()
        try:
            await self._websocket.send_json({
                "type": "voice_error",
                "error": error_msg,
            })
        except Exception:
            pass

    def get_audio_buffer(self) -> bytes:
        """Return accumulated audio for batch ASR fallback."""
        return bytes(self._audio_buffer)
