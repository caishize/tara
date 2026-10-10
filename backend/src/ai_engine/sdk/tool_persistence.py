"""
Tool Persistence Handler - 3-layer persistence logic for tool executions.

Extracted from tool_adapter.py to be independent of Anthropic API format.
Used by the MCP tool server.

3-layer context:
    Layer 1: summary (one-sentence, stored in message.tool_calls JSONB)
    Layer 2: key_results (structured data, stored in tool_execution_logs)
    Layer 3: full_result (complete raw return, stored in tool_execution_logs)
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from ...config.settings import settings

logger = logging.getLogger(__name__)

_FALLBACK_TTL_SECONDS = 24 * 60 * 60  # 24 hours
DEFAULT_MAX_TOOL_CALLS = 100


def _strip_null_bytes(obj: Any) -> Any:
    """Recursively strip \\u0000 (null bytes) from strings in nested structures.

    PostgreSQL text/jsonb columns reject \\u0000. Web search results and other
    external data may contain them, so we sanitize before persisting.
    """
    if isinstance(obj, str):
        return obj.replace("\x00", "")
    if isinstance(obj, dict):
        return {k: _strip_null_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_null_bytes(item) for item in obj]
    return obj


class ToolPersistenceHandler:
    """
    Handles 3-layer persistence for tool executions.

    Responsibilities:
    1. Track execution IDs and timing
    2. Persist to tool_execution_logs (DB) with fallback to Redis
    3. Extract Layer 1 summary and Layer 2 key_results
    4. Fire on_tool_start / on_tool_end callbacks
    5. Enforce tool call limits
    """

    def __init__(
        self,
        db: AsyncSession,
        user_id: str,
        family_id: str,
        session_id: str,
        path_type: str = "slow",
        on_tool_start: Optional[Callable[..., Coroutine]] = None,
        on_tool_end: Optional[Callable[..., Coroutine]] = None,
        on_tool_progress: Optional[Callable[..., Coroutine]] = None,
        max_tool_calls: Optional[int] = None,
        tool_timeout_seconds: Optional[int] = None,
    ):
        self._db = db
        self._user_id = user_id
        self._family_id = family_id
        self._session_id = session_id
        self._path_type = path_type
        self._on_tool_start = on_tool_start
        self._on_tool_end = on_tool_end
        self._on_tool_progress = on_tool_progress
        self._iteration = 1
        self._tool_call_count = 0
        self._max_tool_calls = max_tool_calls or DEFAULT_MAX_TOOL_CALLS
        configured_timeout = (
            tool_timeout_seconds
            if tool_timeout_seconds is not None
            else settings.agentic_tool_timeout_seconds
        )
        self._tool_timeout_seconds = max(0, int(configured_timeout or 0))

    def advance_iteration(self) -> None:
        """Advance the agentic iteration counter."""
        self._iteration += 1

    @property
    def iteration(self) -> int:
        return self._iteration

    @property
    def tool_call_count(self) -> int:
        return self._tool_call_count

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def family_id(self) -> str:
        return self._family_id

    @property
    def session_id(self) -> str:
        return self._session_id

    async def _trace_phase(
        self,
        tool_name: str,
        phase: str,
        coro: Coroutine[Any, Any, Any],
    ) -> tuple[Any, int]:
        """Run a phase coroutine with start/end timing logs."""
        started_at = time.monotonic()
        logger.info(
            "Tool phase start: tool=%s phase=%s session=%s",
            tool_name, phase, self._session_id,
        )
        result = await coro
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        log_fn = logger.warning if elapsed_ms > 5000 else logger.info
        log_fn(
            "Tool phase done: tool=%s phase=%s elapsed_ms=%d session=%s",
            tool_name, phase, elapsed_ms, self._session_id,
        )
        return result, elapsed_ms

    async def execute_with_persistence(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        executor: Callable[..., Coroutine],
        context: Any,
        message_id: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool via the provided executor with 3-layer persistence.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments from LLM
            executor: Async callable that performs the actual tool execution
            context: ToolExecutionContext passed to executor
            message_id: Optional message ID to link execution to

        Returns:
            Dict with keys: content (str), is_error (bool),
            execution_id (str), short_id (str), summary (str),
            status (str), key_results (optional)
        """
        self._tool_call_count += 1
        if self._tool_call_count > self._max_tool_calls:
            logger.error(
                "Tool call limit exceeded (%d/%d) in session %s",
                self._tool_call_count, self._max_tool_calls, self._session_id,
            )
            return {
                "content": f"Error: 工具调用次数超过限制 ({self._max_tool_calls})",
                "is_error": True,
                "execution_id": "",
                "short_id": "",
                "summary": "调用次数超限",
                "status": "error",
            }

        if execution_id:
            try:
                execution_uuid = uuid.UUID(str(execution_id))
            except Exception:
                logger.warning(
                    "Invalid execution_id '%s' for tool %s, regenerated UUID",
                    execution_id,
                    tool_name,
                )
                execution_uuid = uuid.uuid4()
        else:
            execution_uuid = uuid.uuid4()
        short_id = str(execution_uuid).split("-")[0]
        start_time = time.monotonic()

        start_callback_ms = 0
        if self._on_tool_start:
            _, start_callback_ms = await self._trace_phase(
                tool_name,
                "on_tool_start",
                self._on_tool_start(
                    execution_id=str(execution_uuid),
                    short_id=short_id,
                    tool_name=tool_name,
                    arguments=arguments,
                ),
            )

        # Wire progress_callback so tool executors can publish real-time
        # progress events (e.g., "正在搜索...", "已获取...") to the client.
        if self._on_tool_progress:
            on_progress = self._on_tool_progress

            def _progress_cb(stage: str, message: str) -> None:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(on_progress(
                        execution_id=str(execution_uuid),
                        tool_name=tool_name,
                        stage=stage,
                        message=message,
                    ))
                except RuntimeError:
                    pass

            context.progress_callback = _progress_cb

        try:
            execute_coro = executor(
                tool_name=tool_name,
                arguments=arguments,
                context=context,
            )
            if self._tool_timeout_seconds > 0:
                result, executor_ms = await self._trace_phase(
                    tool_name,
                    "executor",
                    asyncio.wait_for(
                        execute_coro,
                        timeout=self._tool_timeout_seconds,
                    ),
                )
            else:
                result, executor_ms = await self._trace_phase(
                    tool_name, "executor", execute_coro
                )

            duration_ms = int((time.monotonic() - start_time) * 1000)

            summary, key_results = self._extract_summary_and_key_results(
                tool_name, result
            )

            _, persist_ms = await self._trace_phase(
                tool_name,
                "persist_success",
                self._persist_execution(
                    execution_id=execution_uuid,
                    tool_name=tool_name,
                    arguments=arguments,
                    status="success",
                    summary=summary,
                    key_results=key_results,
                    full_result=result if isinstance(result, dict) else {"result": str(result)},
                    execution_time_ms=duration_ms,
                    message_id=message_id,
                ),
            )

            callback_ms = 0
            if self._on_tool_end:
                _, callback_ms = await self._trace_phase(
                    tool_name,
                    "on_tool_end_success",
                    self._on_tool_end(
                        execution_id=str(execution_uuid),
                        short_id=short_id,
                        tool_name=tool_name,
                        status="success",
                        summary=summary,
                        key_results=key_results,
                        duration_ms=duration_ms,
                        full_result=result if isinstance(result, dict) else None,
                    ),
                )

            tail_ms = persist_ms + callback_ms
            if tail_ms > 1000:
                logger.warning(
                    "Slow tool tail for %s: start_cb_ms=%d exec_ms=%d persist_ms=%d callback_ms=%d tail_ms=%d total_ms=%d session=%s",
                    tool_name,
                    start_callback_ms,
                    executor_ms,
                    persist_ms,
                    callback_ms,
                    tail_ms,
                    duration_ms,
                    self._session_id,
                )

            return {
                "content": str(result),
                "is_error": False,
                "execution_id": str(execution_uuid),
                "short_id": short_id,
                "summary": summary,
                "status": "success",
                "key_results": key_results,
                "duration_ms": duration_ms,
                "full_result": result if isinstance(result, dict) else {"result": str(result)},
            }

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            timeout_seconds = self._tool_timeout_seconds
            error_msg = f"工具执行超时（>{timeout_seconds}s）"

            await self._trace_phase(
                tool_name,
                "persist_error_timeout",
                self._persist_execution(
                    execution_id=execution_uuid,
                    tool_name=tool_name,
                    arguments=arguments,
                    status="error",
                    error_message=error_msg,
                    summary=error_msg,
                    execution_time_ms=duration_ms,
                    message_id=message_id,
                ),
            )

            if self._on_tool_end:
                await self._trace_phase(
                    tool_name,
                    "on_tool_end_timeout",
                    self._on_tool_end(
                        execution_id=str(execution_uuid),
                        short_id=short_id,
                        tool_name=tool_name,
                        status="error",
                        summary=error_msg,
                        duration_ms=duration_ms,
                    ),
                )

            logger.error(
                "Tool execution timed out: %s (timeout=%ss)",
                tool_name,
                timeout_seconds,
            )
            return {
                "content": f"Error: {error_msg}",
                "is_error": True,
                "execution_id": str(execution_uuid),
                "short_id": short_id,
                "summary": error_msg,
                "status": "error",
                "duration_ms": duration_ms,
                "error_message": error_msg,
                "error_type": "timeout",
            }

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            error_msg = str(e)

            await self._trace_phase(
                tool_name,
                "persist_error_exception",
                self._persist_execution(
                    execution_id=execution_uuid,
                    tool_name=tool_name,
                    arguments=arguments,
                    status="error",
                    error_message=error_msg,
                    summary=f"执行失败: {error_msg[:100]}",
                    execution_time_ms=duration_ms,
                    message_id=message_id,
                ),
            )

            if self._on_tool_end:
                await self._trace_phase(
                    tool_name,
                    "on_tool_end_exception",
                    self._on_tool_end(
                        execution_id=str(execution_uuid),
                        short_id=short_id,
                        tool_name=tool_name,
                        status="error",
                        summary=f"执行失败: {error_msg[:100]}",
                        duration_ms=duration_ms,
                    ),
                )

            logger.error("Tool execution failed: %s - %s", tool_name, error_msg)
            return {
                "content": f"Error: {error_msg}",
                "is_error": True,
                "execution_id": str(execution_uuid),
                "short_id": short_id,
                "summary": f"执行失败: {error_msg[:100]}",
                "status": "error",
                "duration_ms": duration_ms,
                "error_message": error_msg,
            }

    async def _persist_execution(
        self,
        execution_id: uuid.UUID,
        tool_name: str,
        arguments: Dict[str, Any],
        status: str,
        summary: Optional[str] = None,
        key_results: Optional[Dict[str, Any]] = None,
        full_result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        message_id: Optional[str] = None,
    ) -> None:
        """Persist tool execution to tool_execution_logs table."""
        try:
            from ...modules.conversation.models import ToolExecutionLog

            log = ToolExecutionLog(
                id=execution_id,
                session_id=uuid.UUID(self._session_id) if self._session_id else None,
                user_id=uuid.UUID(self._user_id),
                family_id=uuid.UUID(self._family_id),
                message_id=uuid.UUID(message_id) if message_id else None,
                path_type=self._path_type,
                tool_name=tool_name,
                arguments=_strip_null_bytes(arguments),
                status=status,
                error_message=error_message.replace("\x00", "") if error_message else None,
                summary=summary.replace("\x00", "") if summary else None,
                key_results=_strip_null_bytes(key_results),
                full_result=_strip_null_bytes(full_result),
                execution_time_ms=execution_time_ms,
                iteration=self._iteration,
            )
            # If a prior flush failed (e.g. IntegrityError in tool executor),
            # the session is in a rolled-back state. Rollback first so
            # begin_nested() can create a fresh savepoint.
            if self._db.is_active is False:
                await self._db.rollback()
            async with self._db.begin_nested():
                self._db.add(log)
                await self._db.flush()
        except Exception as e:
            logger.error(
                "Failed to persist tool execution %s (tool=%s, status=%s, session=%s): %s",
                execution_id, tool_name, status, self._session_id, e,
            )
            await self._persist_execution_fallback(
                execution_id=execution_id,
                tool_name=tool_name,
                arguments=arguments,
                status=status,
                summary=summary,
                key_results=key_results,
                execution_time_ms=execution_time_ms,
            )

    async def _persist_execution_fallback(
        self,
        execution_id: uuid.UUID,
        tool_name: str,
        arguments: Dict[str, Any],
        status: str,
        summary: Optional[str] = None,
        key_results: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None,
    ) -> None:
        """Best-effort Redis fallback when DB persistence fails."""
        try:
            import json
            from ...core.cache import redis_client
            redis = redis_client.client
            if redis is None:
                logger.critical(
                    "Tool execution %s persistence lost: DB failed and Redis unavailable "
                    "(tool=%s, session=%s)",
                    execution_id, tool_name, self._session_id,
                )
                return
            key = f"tool_exec_fallback:{execution_id}"
            data = json.dumps(_strip_null_bytes({
                "execution_id": str(execution_id),
                "session_id": self._session_id,
                "user_id": self._user_id,
                "family_id": self._family_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "status": status,
                "summary": summary,
                "key_results": key_results,
                "execution_time_ms": execution_time_ms,
                "path_type": self._path_type,
                "iteration": self._iteration,
            }), default=str)
            await redis.set(key, data, ex=_FALLBACK_TTL_SECONDS)
            logger.warning(
                "Tool execution %s fell back to Redis due to DB failure (tool=%s)",
                execution_id, tool_name,
            )
        except Exception as fallback_err:
            logger.error(
                "Redis fallback also failed for execution %s: %s",
                execution_id, fallback_err,
            )

    @staticmethod
    def _extract_summary_and_key_results(
        tool_name: str,
        result: Any,
    ) -> tuple:
        """Extract Layer 1 summary and Layer 2 key_results from tool result."""
        if result is None:
            return (f"{tool_name}: no result returned", None)

        if not isinstance(result, dict):
            return (str(result)[:200], None)

        explicit_summary = result.get("summary") or result.get("message")
        key_results = result.get("key_results")

        # Use comprehensive generator when no explicit summary
        if not explicit_summary:
            try:
                from ...modules.conversation.tool_summary_generator import (
                    generate_summary_for_tool,
                )
                gen_summary, gen_key = generate_summary_for_tool(tool_name, result)
                if gen_summary:
                    explicit_summary = gen_summary
                if gen_key and not key_results:
                    key_results = gen_key
            except Exception:
                pass

        summary = explicit_summary or f"{tool_name} 执行完成"

        if not key_results:
            try:
                from ..workers.key_results_extractor import extract_key_results
                key_results = extract_key_results(tool_name, result)
            except ImportError:
                logger.debug("key_results_extractor not available, skipping extraction")

        return (summary, key_results)

    @staticmethod
    def get_execution_layer1(
        execution_id: str,
        tool_name: str,
        status: str,
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build Layer 1 record for message.tool_calls JSONB."""
        short_id = execution_id.split("-")[0] if "-" in execution_id else execution_id[:8]
        return {
            "execution_id": execution_id,
            "short_id": short_id,
            "tool_name": tool_name,
            "summary": summary or "",
            "status": status,
        }
