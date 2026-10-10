"""
Fast Worker - Handles simple queries without full agent reasoning.

Processes ~80% of traffic that doesn't require complex reasoning:
- Weather queries (external API)
- Time/date queries
- Simple data lookups (schedule, tasks)
- Casual conversation (greetings, acknowledgments)
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from uuid import UUID
from uuid import uuid4

from anthropic import AsyncAnthropic

from ...config.settings import settings
from ...core.llm.haiku_client import get_haiku_client
from ...db.session import get_db_session
from ...modules.briefing.weather_service import WeatherService, WeatherUnavailableError
from ..tools.registry import ToolExecutionContext
from ..tools.tool_bridge import create_tool_bridge
from ..sdk.tool_persistence import ToolPersistenceHandler
from ..router.types import ActionType, IntentClassification, LookupTarget
from .data_lookup_classifier import (
    DataLookupType,
    lookup_target_to_type,
)
from .data_lookup_service import DataLookupService


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FastWorkerResult:
    """Result of a FastWorker agentic run.

    Attributes:
        status: "complete" when the task finished normally,
                "upgrade_to_slow" when max_turns exhausted and the task
                exceeds Fast Path capability.
        text: Final response text (for "complete" status).
        partial_context: Accumulated messages so far, passed to AgentWorker
                         when upgrading to Slow Path.
        reason: Human-readable reason for upgrade (e.g. "tool_limit_exceeded").
    """
    status: str  # "complete" | "upgrade_to_slow"
    text: str = ""
    partial_context: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    UPGRADE_UNIQUE_TOOLS_THRESHOLD = 3


class FastWorker:
    """
    Stateless worker for handling simple queries.

    Routes by intent.action (two-axis system) instead of legacy intent_category.
    Conversation history can be injected per-request for multi-turn context.
    """

    LLM_TIMEOUT_SECONDS = 30
    DB_TIMEOUT_SECONDS = 5
    AGENTIC_SYSTEM_PROMPT = """你是家庭秘书的 Fast Agent（轻量版）。

目标：
1) 优先快速、直接回答用户当前问题。
2) 如需数据，主动调用工具，不要凭空猜测。
3) Fast 模式只做轻量查询和即时响应，不执行创建/删除/修改类操作。

规则：
- 如用户明确提供城市/地区名，优先按该地点查询；仅在未提供地点时使用上下文 latitude/longitude。
- 无法确定地点且无坐标时，再向用户追问。
- 工具结果返回后请基于结果作答，语言简洁自然。
"""
    FAST_READ_TOOL_NAMES = (
        "query_tasks",
        "query_trips",
        "query_members",
        "query_upcoming_dates",
        "query_trip_bookings",
        "query_external_calendar",
    )

    def __init__(
        self,
        client: Optional[AsyncAnthropic] = None,
        model: Optional[str] = None,
    ):
        self._client = client
        self._conversation_history: List[Dict[str, str]] = []
        self._weather_service: Optional[WeatherService] = None
        self._context_assembler = None
        self._context_metadata = None
        self._fast_agentic_enabled = bool(settings.fast_agentic_enabled)
        self._fast_agentic_max_turns = max(1, int(settings.fast_agentic_max_turns))
        self._fast_agentic_max_tool_calls = max(
            1, int(settings.fast_agentic_max_tool_calls)
        )
        self._fast_agentic_tool_timeout_seconds = max(
            1, int(settings.fast_agentic_tool_timeout_seconds)
        )
        self._fast_weather_tool_timeout_seconds = max(
            self._fast_agentic_tool_timeout_seconds,
            int(settings.fast_weather_tool_timeout_seconds),
        )
        self._fast_persistence_tool_timeout_seconds = max(
            int(settings.agentic_tool_timeout_seconds),
            self._fast_weather_tool_timeout_seconds,
        )
        if model:
            self._model = model
        else:
            self._model = settings.fast_worker_model
        if not self._model:
            raise ValueError(
                "FastWorker model not configured — "
                "set fast_worker_model or effective_anthropic_model in settings"
            )

    def set_conversation_history(
        self,
        history: List[Dict[str, str]],
    ) -> None:
        """Inject conversation history for multi-turn context.

        Args:
            history: List of {"role": "user"|"assistant", "content": "..."} dicts.
        """
        self._conversation_history = list(history)

    @property
    def client(self):
        """Get or create Anthropic client via shared factory."""
        if self._client is None:
            self._client = get_haiku_client()
        return self._client

    async def handle(
        self,
        user_input: str,
        intent: IntentClassification,
        user_id: str,
        family_id: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        path_type: str = "fast",
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Handle a fast-path query, routing by intent.action.

        Yields:
            Response chunks for streaming
        """
        logger.info(
            "FastWorker handling: action=%s, difficulty=%s, user_id=%s",
            intent.action, intent.difficulty, user_id,
        )

        try:
            if self._fast_agentic_enabled:
                async for chunk in self._handle_agentic(
                    user_input=user_input,
                    intent=intent,
                    user_id=user_id,
                    family_id=family_id,
                    context=context,
                    session_id=session_id,
                    path_type=path_type,
                ):
                    yield chunk
                return

            if intent.action == ActionType.WEATHER:
                async for chunk in self._handle_weather(user_input, intent, context):
                    yield chunk

            elif intent.action == ActionType.TIME:
                async for chunk in self._handle_time(user_input, context):
                    yield chunk

            elif intent.action in (ActionType.GREET, ActionType.CHAT):
                async for chunk in self._handle_chat(user_input, intent):
                    yield chunk

            elif intent.action == ActionType.LOOKUP:
                async for chunk in self._handle_data_lookup(
                    user_input, intent, user_id, family_id
                ):
                    yield chunk

            else:
                async for chunk in self._handle_fallback(user_input, intent):
                    yield chunk

        except Exception as e:
            logger.error("FastWorker error: %s", e)
            yield {
                "type": "error",
                "content": "处理请求时出现错误，请稍后重试",
            }

    async def _handle_agentic(
        self,
        user_input: str,
        intent: IntentClassification,
        user_id: str,
        family_id: str,
        context: Optional[Dict[str, Any]],
        session_id: Optional[str],
        path_type: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Lightweight agentic loop for fast path (without Claude Agent SDK)."""
        t_agentic_start = time.monotonic()

        messages = self._build_history_messages(user_input)
        assembled_context = await self._try_assemble_context(
            user_id=user_id,
            family_id=family_id,
            session_id=session_id,
            user_message=user_input,
            action_type=intent.action.value if intent.action else None,
        )
        t_context = time.monotonic()

        system_prompt = self._build_agentic_system_prompt(
            intent, context, assembled_context=assembled_context,
        )
        thinking_open = False

        async with get_db_session() as tool_db:
            bridge = await create_tool_bridge(tool_db)
            t_bridge = time.monotonic()

            bridge_tool_defs = bridge.get_tool_definitions(
                tool_names=list(self.FAST_READ_TOOL_NAMES)
            )
            tool_definitions = [*bridge_tool_defs, self._weather_tool_definition()]
            tool_progress_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

            logger.info(
                "FastWorker agentic setup: context_ms=%.0f, bridge_ms=%.0f, "
                "model=%s, action=%s, user_input=%.60s",
                (t_context - t_agentic_start) * 1000,
                (t_bridge - t_context) * 1000,
                self._model,
                intent.action.value if intent.action else "?",
                user_input,
            )

            tool_ctx = ToolExecutionContext(
                family_id=self._safe_uuid(family_id),
                user_id=self._safe_uuid(user_id),
                session_id=session_id or "",
            )

            async def _on_tool_progress(
                execution_id: str,
                tool_name: str,
                stage: str,
                message: str,
                **_: Any,
            ) -> None:
                await tool_progress_queue.put(
                    {
                        "execution_id": execution_id,
                        "tool_name": tool_name,
                        "stage": stage,
                        "message": message,
                    }
                )

            persistence = ToolPersistenceHandler(
                db=tool_db,
                user_id=user_id,
                family_id=family_id,
                session_id=session_id or "",
                path_type=path_type,
                max_tool_calls=self._fast_agentic_max_tool_calls,
                tool_timeout_seconds=self._fast_persistence_tool_timeout_seconds,
                on_tool_progress=_on_tool_progress,
            )

            tool_call_count = 0

            for _ in range(self._fast_agentic_max_turns):
                if not thinking_open:
                    # Emit immediate feedback before the first non-streaming LLM
                    # round-trip so mobile users don't perceive a frozen state.
                    yield {
                        "type": "thinking_start",
                        "content": "正在分析您的问题...",
                    }
                    thinking_open = True

                text_parts: List[str] = []
                text_streamed = False
                t_llm_start = time.monotonic()
                t_first_text: Optional[float] = None

                # Stream textual deltas so users can see progress during the
                # first agentic LLM turn, then read final snapshot for tool_use.
                async with self.client.messages.stream(
                    model=self._model,
                    max_tokens=768,
                    system=system_prompt,
                    messages=messages,
                    tools=tool_definitions,
                    timeout=self.LLM_TIMEOUT_SECONDS,
                ) as stream:
                    async for text in stream.text_stream:
                        if not text:
                            continue
                        if t_first_text is None:
                            t_first_text = time.monotonic()
                            logger.info(
                                "FastWorker first text delta: ttft_ms=%.0f, "
                                "total_ms=%.0f, user_input=%.60s",
                                (t_first_text - t_llm_start) * 1000,
                                (t_first_text - t_agentic_start) * 1000,
                                user_input,
                            )
                        text_parts.append(text)
                        text_streamed = True
                        if thinking_open:
                            yield {"type": "thinking_end", "content": ""}
                            thinking_open = False
                        yield {
                            "type": "content",
                            "content": text,
                            "is_final": False,
                        }
                    response = await stream.get_final_message()

                t_llm_done = time.monotonic()
                logger.info(
                    "FastWorker LLM turn complete: llm_ms=%.0f, "
                    "total_ms=%.0f, stop_reason=%s, user_input=%.60s",
                    (t_llm_done - t_llm_start) * 1000,
                    (t_llm_done - t_agentic_start) * 1000,
                    getattr(response, "stop_reason", "?"),
                    user_input,
                )

                content_blocks = response.content or []
                assistant_blocks: List[Dict[str, Any]] = []
                tool_uses: List[Dict[str, Any]] = []

                for block in content_blocks:
                    block_type = getattr(block, "type", None)
                    if block_type == "text":
                        text = (getattr(block, "text", "") or "").strip()
                        if text and not text_streamed:
                            text_parts.append(text)
                        if text:
                            assistant_blocks.append({"type": "text", "text": text})
                    elif block_type == "tool_use":
                        tool_use = {
                            "id": getattr(block, "id", ""),
                            "name": getattr(block, "name", ""),
                            "input": getattr(block, "input", {}) or {},
                        }
                        tool_uses.append(tool_use)
                        assistant_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tool_use["id"],
                                "name": tool_use["name"],
                                "input": tool_use["input"],
                            }
                        )

                if assistant_blocks:
                    messages.append({"role": "assistant", "content": assistant_blocks})

                if text_parts and tool_uses and not text_streamed:
                    if thinking_open:
                        yield {"type": "thinking_end", "content": ""}
                        thinking_open = False
                    yield {
                        "type": "content",
                        "content": "".join(text_parts),
                        "is_final": False,
                    }

                if not tool_uses:
                    if thinking_open:
                        yield {"type": "thinking_end", "content": ""}
                        thinking_open = False
                    final_text = "".join(text_parts).strip() or "我已经处理好了。"
                    if text_streamed and final_text:
                        # Avoid duplicating full content after streamed deltas.
                        yield {"type": "content", "content": "", "is_final": True}
                    else:
                        yield {
                            "type": "content",
                            "content": final_text,
                            "is_final": True,
                        }
                    return

                tool_result_blocks: List[Dict[str, Any]] = []

                for tool_use in tool_uses:
                    tool_name = tool_use["name"]
                    tool_input = tool_use["input"]
                    tool_use_id = tool_use["id"]

                    if tool_call_count >= self._fast_agentic_max_tool_calls:
                        tool_result_blocks.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "is_error": True,
                                "content": json.dumps(
                                    {"error": "tool_call_limit_exceeded"},
                                    ensure_ascii=False,
                                ),
                            }
                        )
                        continue

                    tool_call_count += 1
                    execution_id = str(uuid4())
                    if thinking_open:
                        yield {"type": "thinking_end", "content": ""}
                        thinking_open = False

                    yield {
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "arguments": tool_input,
                        "execution_id": execution_id,
                    }

                    while True:
                        try:
                            tool_progress_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break

                    tool_task = asyncio.create_task(
                        self._execute_agentic_tool(
                            tool_name=tool_name,
                            arguments=tool_input,
                            bridge=bridge,
                            persistence=persistence,
                            tool_context=tool_ctx,
                            request_context=context,
                            execution_id=execution_id,
                        )
                    )
                    last_progress_message: Optional[str] = None
                    while not tool_task.done():
                        try:
                            progress = await asyncio.wait_for(
                                tool_progress_queue.get(),
                                timeout=0.2,
                            )
                        except asyncio.TimeoutError:
                            continue
                        if progress.get("execution_id") != execution_id:
                            continue
                        progress_message = str(progress.get("message") or "").strip()
                        if not progress_message or progress_message == last_progress_message:
                            continue
                        last_progress_message = progress_message
                        yield {
                            "type": "tool_progress",
                            "tool_name": tool_name,
                            "execution_id": execution_id,
                            "stage": progress.get("stage"),
                            "summary": progress_message,
                            "message": progress_message,
                        }

                    while True:
                        try:
                            progress = tool_progress_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                        if progress.get("execution_id") != execution_id:
                            continue
                        progress_message = str(progress.get("message") or "").strip()
                        if not progress_message or progress_message == last_progress_message:
                            continue
                        last_progress_message = progress_message
                        yield {
                            "type": "tool_progress",
                            "tool_name": tool_name,
                            "execution_id": execution_id,
                            "stage": progress.get("stage"),
                            "summary": progress_message,
                            "message": progress_message,
                        }

                    tool_run = await tool_task

                    await tool_db.commit()

                    tool_output = tool_run.get("tool_output", {})
                    is_error = bool(tool_run.get("is_error", False))
                    duration_ms = int(tool_run.get("duration_ms", 0) or 0)
                    summary = tool_run.get("summary") or f"{tool_name}执行完成"

                    chunk: Dict[str, Any] = {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "success": not is_error,
                        "summary": summary,
                        "execution_id": execution_id,
                        "execution_time_ms": duration_ms,
                    }
                    if is_error:
                        chunk["error"] = tool_run.get("error") or "工具执行失败"
                    else:
                        chunk["result"] = tool_output
                    yield chunk

                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "is_error": is_error,
                            "content": json.dumps(
                                tool_output if not is_error else {"error": chunk["error"]},
                                ensure_ascii=False,
                                default=str,
                            ),
                        }
                    )

                if tool_result_blocks:
                    messages.append({"role": "user", "content": tool_result_blocks})

            # max_turns exhausted: check whether to upgrade to Slow Path
            if thinking_open:
                yield {"type": "thinking_end", "content": ""}

            if self._should_upgrade_to_slow(messages, user_input):
                logger.info(
                    "FastWorker upgrading to Slow Path: user_id=%s",
                    user_id,
                )
                yield {
                    "type": "upgrade_to_slow",
                    "partial_context": messages,
                    "reason": "tool_limit_exceeded",
                }
                return

            yield {
                "type": "content",
                "content": "我已完成查询，但暂时无法整理最终回复。您可以换个问法再试一次。",
                "is_final": True,
            }

    @staticmethod
    def _should_upgrade_to_slow(
        messages: List[Dict[str, Any]],
        user_message: str,
    ) -> bool:
        """Detect whether the current task exceeds Fast Path capability.

        Upgrade signals:
        - 3+ unique tools were invoked across assistant turns
        - Incomplete multi-step plan (assistant mentioned tool_use but
          not all were resolved)

        Returns True if the task should be escalated to Slow Path.
        """
        unique_tools: set = set()

        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    name = block.get("name")
                    if name:
                        unique_tools.add(name)

        return len(unique_tools) >= FastWorkerResult.UPGRADE_UNIQUE_TOOLS_THRESHOLD

    async def _execute_agentic_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        bridge: Any,
        persistence: ToolPersistenceHandler,
        tool_context: ToolExecutionContext,
        request_context: Optional[Dict[str, Any]],
        execution_id: str,
    ) -> Dict[str, Any]:
        """Execute a fast-agentic tool with 3-layer persistence."""
        async def _weather_executor(
            tool_name: str,
            arguments: Dict[str, Any],
            context: ToolExecutionContext,
        ) -> Dict[str, Any]:
            return await self._execute_weather_tool(
                arguments=arguments,
                request_context=request_context,
                tool_context=context,
            )

        async def _bridge_executor(
            tool_name: str,
            arguments: Dict[str, Any],
            context: ToolExecutionContext,
        ) -> Dict[str, Any]:
            result = await bridge.execute_tool(tool_name, arguments, context)
            if isinstance(result, dict) and result.get("success") is False:
                error = (
                    result.get("error")
                    or result.get("message")
                    or f"{tool_name} 执行失败"
                )
                raise RuntimeError(str(error))
            return result if isinstance(result, dict) else {"result": result}

        base_executor = (
            _weather_executor if tool_name == "get_weather" else _bridge_executor
        )

        async def _timed_executor(
            tool_name: str,
            arguments: Dict[str, Any],
            context: ToolExecutionContext,
        ) -> Dict[str, Any]:
            timeout_seconds = self._resolve_tool_timeout_seconds(tool_name)
            # Keep timeout inside persistence call so timeout/error is still
            # recorded by the 3-layer storage.
            return await asyncio.wait_for(
                base_executor(
                    tool_name=tool_name,
                    arguments=arguments,
                    context=context,
                ),
                timeout=timeout_seconds,
            )

        run = await persistence.execute_with_persistence(
            tool_name=tool_name,
            arguments=arguments,
            executor=_timed_executor,
            context=tool_context,
            execution_id=execution_id,
        )

        is_error = bool(run.get("is_error", False))
        if is_error:
            return {
                "is_error": True,
                "summary": run.get("summary") or f"{tool_name} 执行失败",
                "error": run.get("error_message") or run.get("content") or "工具执行失败",
                "duration_ms": run.get("duration_ms", 0),
                "tool_output": {},
            }

        full_result = run.get("full_result") or {}
        if tool_name == "get_weather" and isinstance(full_result, dict):
            tool_output = full_result.get("weather") or full_result
        else:
            tool_output = full_result

        return {
            "is_error": False,
            "summary": run.get("summary") or f"{tool_name} 执行完成",
            "duration_ms": run.get("duration_ms", 0),
            "tool_output": tool_output if isinstance(tool_output, dict) else {"result": tool_output},
        }

    async def _execute_weather_tool(
        self,
        arguments: Dict[str, Any],
        request_context: Optional[Dict[str, Any]],
        tool_context: Optional[ToolExecutionContext] = None,
    ) -> Dict[str, Any]:
        """Synthetic weather tool used by fast-agentic mode."""
        progress_cb = tool_context.progress_callback if tool_context else None
        self._emit_tool_progress(
            progress_cb, "weather_prepare", "正在解析天气查询参数..."
        )

        location = self._normalize_filter_value(arguments.get("location"))
        latitude = self._safe_float(arguments.get("latitude"))
        longitude = self._safe_float(arguments.get("longitude"))

        if request_context:
            # Avoid mixing explicit city queries with context coordinates.
            # If location is explicitly provided, only trust tool-provided coords.
            if not location:
                if latitude is None:
                    latitude = self._safe_float(request_context.get("latitude"))
                if longitude is None:
                    longitude = self._safe_float(request_context.get("longitude"))
                location = self._normalize_filter_value(
                    request_context.get("location_name")
                )

        if not location and (latitude is None or longitude is None):
            raise ValueError("缺少地点信息，请提供城市名或定位坐标")

        self._emit_tool_progress(
            progress_cb, "weather_fetch", "正在获取天气数据..."
        )
        weather_data = await self._fetch_weather(
            location=location,
            latitude=latitude,
            longitude=longitude,
            progress_cb=progress_cb,
        )
        display_location = (
            self._normalize_filter_value(weather_data.get("location"))
            or location
            or "当前位置"
        )
        weather_data["location"] = display_location
        self._emit_tool_progress(
            progress_cb, "weather_done", f"{display_location}天气数据已获取"
        )

        return {
            "summary": f"{display_location}天气数据获取成功",
            "weather": weather_data,
            "key_results": {
                "location": display_location,
                "temperature": weather_data.get("temperature"),
                "condition": weather_data.get("condition"),
            },
        }

    def _build_agentic_system_prompt(
        self,
        intent: IntentClassification,
        context: Optional[Dict[str, Any]],
        assembled_context: Optional[str] = None,
    ) -> str:
        """Build system prompt for lightweight fast agentic loop."""
        lines = [self.AGENTIC_SYSTEM_PROMPT]
        lines.append(f"当前意图动作: {intent.action.value}")
        if intent.lookup_filter:
            lines.append(f"分类器识别的关键实体: {intent.lookup_filter}")
        if context:
            location_name = self._normalize_filter_value(context.get("location_name"))
            lat = self._safe_float(context.get("latitude"))
            lon = self._safe_float(context.get("longitude"))
            if location_name:
                lines.append(f"用户上报位置名称: {location_name}")
            if lat is not None and lon is not None:
                lines.append(f"用户上报坐标: latitude={lat}, longitude={lon}")
        if assembled_context:
            lines.append(f"\n## 相关上下文\n{assembled_context}")
        return "\n".join(lines)

    @staticmethod
    def _weather_tool_definition() -> Dict[str, Any]:
        """Synthetic weather tool definition for fast-agentic mode."""
        return {
            "name": "get_weather",
            "description": "查询天气信息。优先使用用户提供的位置或定位坐标。",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "城市或地区名称"},
                    "latitude": {"type": "number", "description": "纬度"},
                    "longitude": {"type": "number", "description": "经度"},
                },
            },
        }

    async def _handle_weather(
        self,
        user_input: str,
        intent: IntentClassification,
        context: Optional[Dict[str, Any]],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle weather queries with tool events.

        Location resolution:
        1. lookup_filter from Haiku intent classifier (e.g. "揭阳")
        2. User's current location from context
        """
        explicit_location = self._normalize_filter_value(intent.lookup_filter)
        location = explicit_location or self._normalize_filter_value(
            context.get("location_name") if context else None
        )
        latitude = self._safe_float(context.get("latitude")) if context else None
        longitude = self._safe_float(context.get("longitude")) if context else None

        # User explicitly asked for a city: do not mix in current GPS coordinates.
        if explicit_location:
            latitude = None
            longitude = None

        has_geo = latitude is not None and longitude is not None

        if not location and not has_geo:
            yield {
                "type": "content",
                "content": "请问您想查询哪个城市的天气呢？",
                "is_final": True,
            }
            return

        tool_args: Dict[str, Any] = {}
        if location:
            tool_args["location"] = location
        if has_geo:
            tool_args["latitude"] = latitude
            tool_args["longitude"] = longitude

        exec_id = str(uuid4())
        yield {
            "type": "tool_start",
            "tool_name": "get_weather",
            "arguments": tool_args,
            "execution_id": exec_id,
        }

        t0 = time.monotonic()
        try:
            weather_data = await self._fetch_weather(
                location=location,
                latitude=latitude,
                longitude=longitude,
            )
        except WeatherUnavailableError as e:
            display_location = location or "当前位置"
            logger.warning("Weather unavailable for %s: %s", display_location, e)
            duration_ms = int((time.monotonic() - t0) * 1000)
            yield {
                "type": "tool_result",
                "tool_name": "get_weather",
                "success": False,
                "summary": f"{display_location}天气数据获取失败",
                "error": str(e),
                "execution_id": exec_id,
                "execution_time_ms": duration_ms,
            }
            yield {
                "type": "content",
                "content": f"抱歉，暂时无法获取{display_location}的天气数据，请稍后再试。",
                "is_final": True,
            }
            return

        display_location = (
            self._normalize_filter_value(weather_data.get("location"))
            or location
            or "当前位置"
        )
        weather_data["location"] = display_location

        duration_ms = int((time.monotonic() - t0) * 1000)
        yield {
            "type": "tool_result",
            "tool_name": "get_weather",
            "success": True,
            "summary": f"{display_location}天气数据获取成功",
            "result": weather_data,
            "execution_id": exec_id,
            "execution_time_ms": duration_ms,
        }

        location_hint = ""
        if context and context.get("location_name"):
            location_hint = f"\n用户所在城市: {context['location_name']}"

        prompt = f"""用户询问天气情况。

用户问题: {user_input}{location_hint}
天气数据: {weather_data}

请用简洁友好的语气回答用户的天气问题。"""

        async for chunk in self._stream_llm_response(prompt):
            yield chunk

    async def _handle_time(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle time/date queries."""
        import pytz
        from ...core.utils.timezone import DEFAULT_TIMEZONE_NAME

        tz = context.get("timezone", DEFAULT_TIMEZONE_NAME) if context else DEFAULT_TIMEZONE_NAME

        user_tz = pytz.timezone(tz)
        now = datetime.now(user_tz)

        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekdays[now.weekday()]
        time_str = now.strftime("%Y年%m月%d日 %H:%M")

        response = f"现在是 {time_str}，{weekday}。"

        yield {"type": "content", "content": response, "is_final": True}

    async def _handle_chat(
        self,
        user_input: str,
        intent: IntentClassification,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle casual chat and greetings."""
        prompt = f"""作为一个友好的AI助手，请回应用户的问候或闲聊。

用户: {user_input}

保持回复简短、友好、自然。"""

        async for chunk in self._stream_llm_response(prompt):
            yield chunk

    async def _handle_data_lookup(
        self,
        user_input: str,
        intent: IntentClassification,
        user_id: str,
        family_id: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Handle data lookups using intent.lookup_target and intent.lookup_filter
        from the Haiku classifier only (no keyword fallback).
        """
        # Resolve DataLookupType from Haiku's lookup_target
        sub_type = self._normalize_filter_value(intent.lookup_filter)
        if intent.lookup_target and intent.lookup_target != LookupTarget.UNKNOWN:
            lookup_type = lookup_target_to_type(intent.lookup_target)
        else:
            lookup_type = DataLookupType.UNKNOWN

        if lookup_type == DataLookupType.UNKNOWN:
            yield {
                "type": "content",
                "content": "我可以帮您查日程、任务、提醒、行程或家庭成员信息。请再具体说一下您想查哪一类。",
                "is_final": True,
            }
            return

        tool_name = f"query_{lookup_type.value}"
        exec_id = str(uuid4())

        yield {
            "type": "tool_start",
            "tool_name": tool_name,
            "arguments": {
                "lookup_type": lookup_type.value,
                "sub_type": sub_type,
            },
            "execution_id": exec_id,
        }

        t0 = time.monotonic()
        try:
            async with get_db_session() as db:
                lookup_service = DataLookupService(db)
                result = await asyncio.wait_for(
                    lookup_service.lookup(
                        lookup_type=lookup_type,
                        user_id=user_id,
                        family_id=family_id,
                        sub_type=sub_type,
                    ),
                    timeout=self.DB_TIMEOUT_SECONDS,
                )

                duration_ms = int((time.monotonic() - t0) * 1000)

                if not result.success:
                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "success": False,
                        "summary": result.message,
                        "result": None,
                        "execution_id": exec_id,
                        "execution_time_ms": duration_ms,
                    }
                    yield {
                        "type": "content",
                        "content": f"抱歉，查询时出现问题: {result.message}",
                        "is_final": True,
                    }
                    return

                formatted_data = lookup_service.format_for_llm(result)

                yield {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "success": True,
                    "summary": result.message,
                    "result": result.data,
                    "execution_id": exec_id,
                    "execution_time_ms": duration_ms,
                }

                prompt = f"""用户查询数据，请根据以下信息用自然的中文回答。

用户问题: {user_input}

查询结果:
{formatted_data}

请用简洁友好的语气总结这些信息回答用户。如果没有数据，也要友好地告知用户。"""

                async for chunk in self._stream_llm_response(prompt):
                    yield chunk

        except asyncio.TimeoutError:
            logger.error("Data lookup timed out after %ds", self.DB_TIMEOUT_SECONDS)
            duration_ms = int((time.monotonic() - t0) * 1000)
            yield {
                "type": "tool_result",
                "tool_name": tool_name,
                "success": False,
                "summary": "查询超时",
                "result": None,
                "execution_id": exec_id,
                "execution_time_ms": duration_ms,
            }
            yield {
                "type": "error",
                "content": "查询数据超时，请稍后重试",
            }
        except Exception as e:
            logger.error("Data lookup failed: %s", e)
            duration_ms = int((time.monotonic() - t0) * 1000)
            yield {
                "type": "tool_result",
                "tool_name": tool_name,
                "success": False,
                "summary": str(e),
                "result": None,
                "execution_id": exec_id,
                "execution_time_ms": duration_ms,
            }
            yield {
                "type": "error",
                "content": "查询数据时出现错误，请稍后重试",
            }

    async def _handle_fallback(
        self,
        user_input: str,
        intent: IntentClassification,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Fallback handler for unmatched intents."""
        prompt = f"""请友好地回应用户。

用户: {user_input}

如果这个请求需要复杂处理，请告知用户稍等处理中。"""

        async for chunk in self._stream_llm_response(prompt):
            yield chunk

    def _build_history_messages(self, user_input: str) -> List[Dict[str, str]]:
        """Build multi-turn messages from full conversation history + user input."""
        messages: List[Dict[str, str]] = []
        for msg in self._conversation_history:
            role = msg.get("role", "user")
            content = (msg.get("content") or "").strip()
            if content and role in ("user", "assistant"):
                messages.append({"role": role, "content": content})
        normalized_input = (user_input or "").strip()
        if normalized_input:
            if not (
                messages
                and messages[-1].get("role") == "user"
                and (messages[-1].get("content") or "").strip() == normalized_input
            ):
                messages.append({"role": "user", "content": normalized_input})
        return messages

    def _build_messages(self, prompt: str) -> List[Dict[str, str]]:
        """Backward-compatible wrapper for legacy handlers."""
        return self._build_history_messages(prompt)

    async def _stream_llm_response(
        self,
        prompt: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream LLM response with conversation history and timeout."""
        messages = self._build_messages(prompt)
        t_stream_start = time.monotonic()
        first_chunk_logged = False

        try:
            # asyncio.timeout is 3.11+; fall back to async_timeout for 3.9/3.10
            try:
                from asyncio import timeout as _timeout
            except ImportError:
                from async_timeout import timeout as _timeout
            async with _timeout(self.LLM_TIMEOUT_SECONDS):
                async with self.client.messages.stream(
                    model=self._model,
                    max_tokens=512,
                    messages=messages,
                ) as stream:
                    async for text in stream.text_stream:
                        if not first_chunk_logged:
                            logger.info(
                                "FastWorker _stream_llm_response ttft_ms=%.0f, model=%s",
                                (time.monotonic() - t_stream_start) * 1000,
                                self._model,
                            )
                            first_chunk_logged = True
                        yield {"type": "content", "content": text, "is_final": False}

            yield {"type": "content", "content": "", "is_final": True}

        except (TimeoutError, asyncio.TimeoutError):
            logger.error("LLM streaming timed out after %ds", self.LLM_TIMEOUT_SECONDS)
            yield {
                "type": "error",
                "content": "回复生成超时，请稍后重试",
            }
        except Exception as e:
            logger.error("LLM streaming error: %s", e)
            yield {
                "type": "error",
                "content": "生成回复时出现错误",
            }

    async def _fetch_weather(
        self,
        location: Optional[str],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        progress_cb: Optional[Callable[[str, str], None]] = None,
    ) -> Dict[str, Any]:
        """Fetch weather data from WeatherService."""
        if self._weather_service is None:
            self._weather_service = WeatherService()
        service = self._weather_service
        weather = await service.get_weather(
            latitude=latitude,
            longitude=longitude,
            city=location,
            progress_cb=progress_cb,
        )
        return {
            "location": weather.location or location,
            "temperature": f"{weather.temperature}°C",
            "condition": weather.condition,
            "humidity": weather.humidity or "",
            "wind": weather.wind or "",
            "high_temp": f"{weather.high_temp}°C" if weather.high_temp is not None else None,
            "low_temp": f"{weather.low_temp}°C" if weather.low_temp is not None else None,
            "icon": service.get_weather_icon(weather.condition),
        }

    def _resolve_tool_timeout_seconds(self, tool_name: str) -> int:
        """Resolve per-tool execution timeout for fast-agentic mode."""
        if tool_name == "get_weather":
            return self._fast_weather_tool_timeout_seconds
        return self._fast_agentic_tool_timeout_seconds

    @staticmethod
    def _emit_tool_progress(
        progress_cb: Optional[Callable[[str, str], None]],
        stage: str,
        message: str,
    ) -> None:
        """Best-effort tool progress callback."""
        if not progress_cb:
            return
        try:
            progress_cb(stage, message)
        except Exception:
            logger.debug("FastWorker tool progress callback failed", exc_info=True)

    async def _try_assemble_context(
        self,
        user_id: str,
        family_id: str,
        session_id: Optional[str],
        user_message: str,
        action_type: Optional[str] = None,
    ) -> Optional[str]:
        """Try V8 ContextAssembler; return None on failure (graceful fallback)."""
        try:
            from ..context_assembler import ContextAssembler
            from ..context_fetchers import (
                aggregate_dismissed_entities,
                fetch_curation_hints,
                fetch_l1_notes,
                fetch_l2_messages,
                fetch_l3_summaries,
                fetch_l4_memories,
                fetch_l5_orchestration,
            )
            from ..entity_resolver import resolve_entities

            async def _combined_l1_fetcher(
                uid: UUID, fid: UUID, db=None,
            ) -> list:
                notes = await fetch_l1_notes(uid, fid, db=db)
                hints = await fetch_curation_hints(uid, fid, db=db)
                return notes + hints

            if self._context_assembler is None:
                self._context_assembler = ContextAssembler(
                    l1_fetcher=_combined_l1_fetcher,
                    l2_fetcher=fetch_l2_messages,
                    l3_fetcher=fetch_l3_summaries,
                    l4_fetcher=fetch_l4_memories,
                    l5_fetcher=fetch_l5_orchestration,
                    entity_resolver=resolve_entities,
                )
            dismissed = await aggregate_dismissed_entities(
                user_id=self._safe_uuid(user_id),
                family_id=self._safe_uuid(family_id),
            )
            prompt_text, metadata = await self._context_assembler.assemble(
                user_id=self._safe_uuid(user_id),
                family_id=self._safe_uuid(family_id),
                session_id=session_id or "",
                user_message=user_message,
                action_type=action_type,
                dismissed_entity_ids=dismissed if dismissed else None,
            )
            self._context_metadata = metadata
            return prompt_text if prompt_text else None
        except Exception as e:
            logger.debug("ContextAssembler unavailable in fast path: %s", e)
            return None

    @staticmethod
    def _normalize_filter_value(raw: Optional[object]) -> Optional[str]:
        """Normalize model / context filter values."""
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        if text.lower() in {"null", "none", "unknown", "n/a"}:
            return None
        return text

    @staticmethod
    def _safe_float(value: Optional[object]) -> Optional[float]:
        """Convert value to float when possible."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_uuid(value: str) -> UUID:
        """Parse UUID string with safe fallback."""
        try:
            return UUID(str(value))
        except Exception:
            return UUID(int=0)
