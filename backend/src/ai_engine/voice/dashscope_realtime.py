"""
Dashscope Real-Time ASR Client — thin async wrapper around Dashscope's
streaming speech recognition WebSocket API.

Provides a clean async interface for streaming audio → receiving partial/final
transcriptions. Falls back cleanly on connection failure so callers can use
batch ASR instead.

Design ref: AD-1 (Dashscope RT ASR for native Mandarin streaming).
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Coroutine, Dict, Optional

import websockets
from websockets.asyncio.client import ClientConnection

from ...config.settings import settings

logger = logging.getLogger(__name__)

# Dashscope real-time ASR WebSocket endpoint
_DASHSCOPE_RT_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/"

# Callback type: async function receiving transcription text + is_final flag
TranscriptionCallback = Callable[[str, bool], Coroutine[Any, Any, None]]


class DashscopeRealtimeError(Exception):
    """Raised when Dashscope real-time ASR encounters an error."""


class DashscopeRealtimeClient:
    """Async wrapper around Dashscope's real-time ASR WebSocket API.

    Usage::

        client = DashscopeRealtimeClient()
        client.on_partial(handle_partial)
        client.on_final(handle_final)
        stream_id = await client.start()
        await client.send_audio(chunk)
        await client.end_audio()
        await client.close()
    """

    # Callback type for error notifications
    ErrorCallback = Callable[[str], Coroutine[Any, Any, None]]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        sample_rate: int = 16000,
    ) -> None:
        self._api_key = api_key or settings.dashscope_api_key
        self._model = model or settings.voice_streaming_model
        self._sample_rate = sample_rate
        self._ws: Optional[ClientConnection] = None
        self._stream_id: Optional[str] = None
        self._on_partial: Optional[TranscriptionCallback] = None
        self._on_final: Optional[TranscriptionCallback] = None
        self._on_error: Optional[DashscopeRealtimeClient.ErrorCallback] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._task_started = asyncio.Event()
        self._connection_lost = asyncio.Event()
        self._closed = False

    def on_partial(self, callback: TranscriptionCallback) -> None:
        """Register callback for partial (intermediate) transcription results."""
        self._on_partial = callback

    def on_final(self, callback: TranscriptionCallback) -> None:
        """Register callback for final transcription results."""
        self._on_final = callback

    def on_error(self, callback: "DashscopeRealtimeClient.ErrorCallback") -> None:
        """Register callback for task-failed errors from Dashscope."""
        self._on_error = callback

    async def start(self, config: Optional[Dict[str, Any]] = None) -> str:
        """Open WebSocket connection and start recognition task.

        Returns:
            stream_id for this recognition session.

        Raises:
            DashscopeRealtimeError: If connection or task start fails.
        """
        if not self._api_key:
            raise DashscopeRealtimeError(
                "Dashscope API key not configured (DASHSCOPE_API_KEY)"
            )

        self._stream_id = str(uuid.uuid4())
        headers = {
            "Authorization": f"bearer {self._api_key}",
            "X-DashScope-DataInspection": "enable",
        }

        try:
            self._ws = await websockets.connect(
                _DASHSCOPE_RT_URL,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
        except Exception as e:
            raise DashscopeRealtimeError(
                f"Failed to connect to Dashscope RT ASR: {e}"
            ) from e

        # Send recognition task start message
        task_config = {
            "header": {
                "action": "run-task",
                "task_id": self._stream_id,
                "streaming": "duplex",
            },
            "payload": {
                "task_group": "audio",
                "task": "asr",
                "function": "recognition",
                "model": self._model,
                "parameters": {
                    "sample_rate": self._sample_rate,
                    "format": "pcm",
                    "language_hints": ["zh", "en"],
                    **(config or {}),
                },
                "input": {},
            },
        }

        try:
            await self._ws.send(json.dumps(task_config))
        except Exception as e:
            await self._safe_close()
            raise DashscopeRealtimeError(
                f"Failed to send task start: {e}"
            ) from e

        # Start background receive loop
        self._receive_task = asyncio.create_task(
            self._receive_loop(),
            name=f"dashscope-rt-recv-{self._stream_id[:8]}",
        )

        # Wait for Dashscope to ACK the task before sending audio
        try:
            await asyncio.wait_for(self._task_started.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            await self.close()
            raise DashscopeRealtimeError(
                f"Dashscope task-started ACK timeout: stream_id={self._stream_id}"
            )

        logger.info(
            "dashscope_rt_started: stream_id=%s model=%s sample_rate=%d",
            self._stream_id, self._model, self._sample_rate,
        )
        return self._stream_id

    async def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk to the recognition stream.

        Raises:
            DashscopeRealtimeError: If the send fails for any reason.
        """
        ws = self._ws
        if ws is None or self._closed:
            return
        try:
            await ws.send(chunk)
        except Exception as e:
            logger.warning(
                "dashscope_rt_send_failed: stream_id=%s error=%s",
                self._stream_id, e,
            )
            raise DashscopeRealtimeError(
                f"Failed to send audio: {e}"
            ) from e

    async def end_audio(self) -> None:
        """Signal end of audio input. Triggers final transcription."""
        if self._ws is None or self._closed:
            return
        stop_msg = {
            "header": {
                "action": "finish-task",
                "task_id": self._stream_id,
                "streaming": "duplex",
            },
            "payload": {"input": {}},
        }
        try:
            await self._ws.send(json.dumps(stop_msg))
        except Exception as e:
            logger.warning(
                "dashscope_rt_end_failed: stream_id=%s error=%s",
                self._stream_id, e,
            )

    async def close(self) -> None:
        """Close the WebSocket connection and clean up resources."""
        self._closed = True
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except (asyncio.CancelledError, Exception):
                pass
            self._receive_task = None
        await self._safe_close()
        logger.info("dashscope_rt_closed: stream_id=%s", self._stream_id)

    async def _safe_close(self) -> None:
        """Close WebSocket without raising."""
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def _receive_loop(self) -> None:
        """Background loop receiving transcription results from Dashscope."""
        if self._ws is None:
            return
        try:
            async for raw_message in self._ws:
                if self._closed:
                    break
                if isinstance(raw_message, bytes):
                    continue  # Binary frames not expected from server

                try:
                    msg = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning(
                        "dashscope_rt_invalid_json: stream_id=%s",
                        self._stream_id,
                    )
                    continue

                await self._handle_server_message(msg)
        except asyncio.CancelledError:
            return
        except websockets.exceptions.ConnectionClosed:
            logger.info(
                "dashscope_rt_connection_closed: stream_id=%s",
                self._stream_id,
            )
        except Exception as e:
            logger.error(
                "dashscope_rt_receive_error: stream_id=%s error=%s",
                self._stream_id, e,
            )
        finally:
            # Signal that the connection is gone so callers waiting for
            # final transcription don't hang (V-B-5).
            self._closed = True
            self._task_started.set()
            self._connection_lost.set()

    async def _handle_server_message(self, msg: Dict[str, Any]) -> None:
        """Parse and dispatch a single server message."""
        header = msg.get("header", {})
        event = header.get("event", "")
        payload = msg.get("payload", {})

        if event == "task-started":
            logger.debug("dashscope_rt_task_started: stream_id=%s", self._stream_id)
            self._task_started.set()
            return

        if event == "result-generated":
            output = payload.get("output", {})
            sentence = output.get("sentence", {})
            text = sentence.get("text", "")
            # end_time > 0 indicates final; Dashscope may return None for partials
            end_time = sentence.get("end_time")
            is_final = (end_time or 0) > 0
            if not text:
                return

            if is_final and self._on_final:
                await self._on_final(text, True)
            elif not is_final and self._on_partial:
                await self._on_partial(text, False)
            return

        if event == "task-finished":
            logger.info(
                "dashscope_rt_task_finished: stream_id=%s",
                self._stream_id,
            )
            return

        if event == "task-failed":
            error_msg = header.get("error_message", "unknown")
            error_code = header.get("error_code", "")
            logger.error(
                "dashscope_rt_task_failed: stream_id=%s code=%s msg=%s",
                self._stream_id, error_code, error_msg,
            )
            # Unblock start() if it's still waiting for task-started ACK
            self._task_started.set()
            # Notify VoiceStreamSession so it can inform the user (V-B-4)
            if self._on_error:
                await self._on_error(f"ASR failed: {error_code} {error_msg}")
            return

        logger.debug(
            "dashscope_rt_unhandled_event: stream_id=%s event=%s",
            self._stream_id, event,
        )
