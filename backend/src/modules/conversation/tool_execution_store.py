"""Tool Execution Store - Context-Aware Storage for Tool Executions.

Implements a layered context management system:
  Layer 1 (Always in context): Metadata + one-line summary
  Layer 2 (Key results): Important data points that might be needed
  Layer 3 (Full details): Complete results, logs, raw data (on-demand only)
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .tool_summary_generator import generate_summary_for_tool  # noqa: F401

logger = get_logger(__name__)


@dataclass
class ToolExecutionRecord:
    """A record of a single tool execution with layered detail levels."""

    execution_id: str
    tool_name: str
    arguments: Dict[str, Any]

    # Timing
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Status
    status: str = "running"  # "running", "success", "error"
    error_message: Optional[str] = None

    # Layer 1: Always in context (compact)
    summary: str = ""

    # Layer 2: Key results (moderate detail)
    key_results: Dict[str, Any] = field(default_factory=dict)

    # Layer 3: Full details (on-demand only)
    full_result: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)

    # Metadata
    iteration: int = 1
    session_id: Optional[str] = None

    def add_log(self, message: str):
        timestamp = utc_now().isoformat()
        self.logs.append(f"[{timestamp}] {message}")

    def _finalize(self):
        self.ended_at = utc_now()
        self.duration_ms = int(
            (self.ended_at - self.started_at).total_seconds() * 1000
        )

    def complete(
        self,
        result: Dict[str, Any],
        summary: str,
        key_results: Optional[Dict[str, Any]] = None,
    ):
        self._finalize()
        self.status = "success"
        self.summary = summary
        self.full_result = result
        self.key_results = key_results or {}
        self.add_log(f"Completed successfully: {summary}")

    def fail(self, error: str):
        self._finalize()
        self.status = "error"
        self.error_message = error
        self.summary = f"执行失败: {error[:50]}"
        self.add_log(f"Failed: {error}")

    @property
    def short_id(self) -> str:
        return (
            self.execution_id.split("-")[0]
            if "-" in self.execution_id
            else self.execution_id[:8]
        )

    def get_context_summary(self) -> str:
        """Layer 1: minimal context representation."""
        duration_str = f"{self.duration_ms}ms" if self.duration_ms else "运行中"
        status_emoji = {
            "success": "✅",
            "error": "❌",
            "running": "⏳",
        }.get(self.status, "?")

        lines = [
            f"[#{self.short_id}] {self.tool_name} - {status_emoji} {self.status} ({duration_str})",
            f"  参数: {self._format_args_brief()}",
            f"  摘要: {self.summary or '(无摘要)'}",
        ]

        if self.status == "success":
            lines.append(
                f'  → 查看详情: view_tool_details("{self.execution_id}")'
            )

        return "\n".join(lines)

    def get_key_results_context(self) -> str:
        """Layer 2: context with key results included."""
        base = self.get_context_summary()
        if self.key_results:
            key_results_str = json.dumps(
                self.key_results, ensure_ascii=False, indent=2
            )
            if len(key_results_str) > 500:
                key_results_str = key_results_str[:500] + "... (truncated)"
            base += f"\n  关键结果:\n{self._indent(key_results_str, 4)}"
        return base

    def get_full_details(self) -> Dict[str, Any]:
        """Layer 3: complete execution details."""
        return {
            "execution_id": self.execution_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_message": self.error_message,
            "summary": self.summary,
            "key_results": self.key_results,
            "full_result": self.full_result,
            "logs": self.logs,
        }

    def _format_args_brief(self) -> str:
        if not self.arguments:
            return "(无参数)"

        parts = []
        for key, value in self.arguments.items():
            if isinstance(value, str) and len(value) > 30:
                value = value[:30] + "..."
            elif isinstance(value, (dict, list)):
                value = f"<{type(value).__name__}>"
            parts.append(f"{key}={value}")

        result = ", ".join(parts)
        if len(result) > 100:
            result = result[:100] + "..."
        return result

    def _indent(self, text: str, spaces: int) -> str:
        prefix = " " * spaces
        return "\n".join(prefix + line for line in text.split("\n"))


class ToolExecutionStore:
    """In-memory store for tool executions within a session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id
        self._executions: Dict[str, ToolExecutionRecord] = {}
        self._execution_order: List[str] = []
        self._current_iteration: int = 1

    def start_execution(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> ToolExecutionRecord:
        execution_id = str(uuid.uuid4())

        record = ToolExecutionRecord(
            execution_id=execution_id,
            tool_name=tool_name,
            arguments=arguments,
            started_at=utc_now(),
            iteration=self._current_iteration,
            session_id=self.session_id,
        )
        record.add_log(f"Started execution of {tool_name}")

        self._executions[execution_id] = record
        self._execution_order.append(execution_id)

        logger.debug(f"Started tool execution: {execution_id} - {tool_name}")
        return record

    def get_execution(self, execution_id: str) -> Optional[ToolExecutionRecord]:
        return self._executions.get(execution_id)

    def get_all_executions(self) -> List[ToolExecutionRecord]:
        return [self._executions[eid] for eid in self._execution_order]

    def get_current_iteration_executions(self) -> List[ToolExecutionRecord]:
        return [
            self._executions[eid]
            for eid in self._execution_order
            if self._executions[eid].iteration == self._current_iteration
        ]

    def advance_iteration(self):
        self._current_iteration += 1
        logger.debug(f"Advanced to iteration {self._current_iteration}")

    @property
    def current_iteration(self) -> int:
        return self._current_iteration

    def generate_context_for_llm(
        self, include_current_iteration_details: bool = True
    ) -> str:
        if not self._executions:
            return ""

        sections = []

        iterations: Dict[int, List[ToolExecutionRecord]] = {}
        for eid in self._execution_order:
            record = self._executions[eid]
            if record.iteration not in iterations:
                iterations[record.iteration] = []
            iterations[record.iteration].append(record)

        for iteration_num in sorted(iterations.keys()):
            records = iterations[iteration_num]
            is_current = iteration_num == self._current_iteration

            section_lines = [f"【第{iteration_num}轮工具执行】"]

            for record in records:
                if is_current and include_current_iteration_details:
                    section_lines.append(record.get_key_results_context())
                else:
                    section_lines.append(record.get_context_summary())
                section_lines.append("")

            sections.append("\n".join(section_lines))

        return "\n\n".join(sections)

    def generate_tool_result_message(
        self, execution_id: str, max_result_size: int = 2000
    ) -> str:
        record = self._executions.get(execution_id)
        if not record:
            return json.dumps({"error": f"Execution {execution_id} not found"})

        if record.status == "error":
            error_msg = record.error_message or "未知错误"
            error_type = None
            if isinstance(record.full_result, dict):
                error_type = record.full_result.get("error_type")
            recovery_hint = self._generate_error_recovery_hint(
                record.tool_name, error_msg, error_type=error_type
            )
            return json.dumps(
                {
                    "execution_id": execution_id,
                    "success": False,
                    "error": error_msg,
                    "error_type": error_type,
                    "_recovery_hint": recovery_hint,
                },
                ensure_ascii=False,
                default=str,
            )

        full_result_str = json.dumps(
            record.full_result, ensure_ascii=False, default=str
        )
        result_is_large = len(full_result_str) > max_result_size

        iteration_num = record.iteration

        iteration_executions = [
            eid
            for eid in self._execution_order
            if self._executions.get(eid)
            and self._executions[eid].iteration == iteration_num
        ]
        execution_index = (
            iteration_executions.index(execution_id) + 1
            if execution_id in iteration_executions
            else 1
        )
        total_in_iteration = len(iteration_executions)

        result = {
            "execution_id": execution_id,
            "iteration": iteration_num,
            "execution_order": f"第{iteration_num}轮第{execution_index}/{total_in_iteration}个",
            "success": True,
            "started_at": (
                record.started_at.isoformat() if record.started_at else None
            ),
            "ended_at": (
                record.ended_at.isoformat() if record.ended_at else None
            ),
            "duration_ms": record.duration_ms,
        }

        if result_is_large:
            result["result"] = record.key_results
            result["_summary"] = record.summary
            omitted_info = self._describe_omitted_data(
                record.tool_name, record.full_result, record.key_results
            )
            result["_omitted"] = omitted_info
            result["_note"] = (
                f"结果已压缩（原始 {len(full_result_str)} 字符）。"
                f"{omitted_info} 如需完整数据，调用 view_tool_details(\"{execution_id}\")"
            )
        else:
            result["result"] = record.full_result
            result["_summary"] = record.summary

        result["_reflect"] = self._generate_reflection_guidance(
            record.tool_name, record.full_result
        )

        return json.dumps(result, ensure_ascii=False, default=str)

    def _describe_omitted_data(
        self,
        tool_name: str,
        full_result: Dict[str, Any],
        key_results: Dict[str, Any],
    ) -> str:
        tool_field_config = {
            "recommend_gift": ("recommendations", "个推荐项"),
            "query_members": ("members", "位成员"),
            "query_upcoming_dates": ("dates", "个日期"),
            "web_search": ("results", "条搜索结果"),
        }

        config = tool_field_config.get(tool_name)
        if config:
            field_name, unit_word = config
            total = len(full_result.get(field_name, []))
            shown = len(key_results.get(field_name, []))
            if total > shown:
                return f"已省略 {total - shown} {unit_word}的详细信息。"

        omitted_parts = []
        for key, value in full_result.items():
            if not isinstance(value, list) or len(value) == 0:
                continue

            kr_value = key_results.get(key)
            if isinstance(kr_value, dict) and "_count" in kr_value:
                shown_count = len(kr_value.get("_sample", []))
                if kr_value["_count"] > shown_count:
                    omitted_parts.append(
                        f"{key}({kr_value['_count'] - shown_count}项)"
                    )
            elif isinstance(kr_value, list) and len(value) > len(kr_value):
                omitted_parts.append(f"{key}({len(value) - len(kr_value)}项)")

        if omitted_parts:
            return f"已省略: {', '.join(omitted_parts)}"

        return "部分详细数据已省略。"

    def _generate_reflection_guidance(
        self, tool_name: str, result: Dict[str, Any]
    ) -> str:
        tool_reflections = {
            "recommend_gift": lambda r: self._reflect_recommend_gift(r),
            "query_members": lambda r: (
                f"已查询到 {r.get('count', 0)} 位成员。"
                "✅ 可以回答用户关于成员的问题，或用于其他工具（如礼物推荐）。"
                "⚠️ 如果用户问的成员不在列表中，提醒用户先添加该成员。"
            ),
            "add_trip_itinerary": lambda r: self._reflect_add_trip_itinerary(r),
            "add_member": lambda r: (
                f"已添加成员: {r.get('name', '')}。"
                "✅ 成员已创建，可继续进行其他操作（如添加生日、推荐礼物）。"
                "⚠️ 询问用户是否需要补充成员的其他信息（生日、偏好等）。"
            ),
            "add_important_date": lambda r: (
                f"已添加日期: {r.get('title', '')}。"
                "✅ 日期已保存，可询问是否设置提醒。"
            ),
            "set_reminder": lambda r: (
                f"已设置提醒: {r.get('content', '')[:30]}..."
                "✅ 提醒已创建，确认时间并告知用户。"
            ),
            "web_search": lambda r: (
                f"已完成搜索: {r.get('query', '')}。"
                "✅ 可基于结果直接回答用户，或继续调用业务工具落库。"
            ),
            "view_tool_details": lambda r: (
                "已获取工具执行详情。"
                "✅ 详情已加载，可以回答用户关于该执行结果的具体问题。"
            ),
        }

        if tool_name in tool_reflections:
            return tool_reflections[tool_name](result)

        success = result.get("success", True)
        if success:
            return (
                "✅ 工具执行成功。检查结果是否满足用户需求，"
                "如果信息完整可以回复用户，否则考虑是否需要调用其他工具补充。"
            )
        return (
            "⚠️ 工具执行遇到问题。查看 _recovery_hint 了解如何解决，"
            "或尝试使用不同参数重试。"
        )

    def _generate_error_recovery_hint(
        self,
        tool_name: str,
        error_msg: str,
        error_type: Optional[str] = None,
    ) -> str:
        error_lower = error_msg.lower()

        error_type_hints = {
            "validation": "请检查参数格式是否正确，必填参数是否已提供",
            "not_found": "目标资源不存在，请先查询确认后再操作",
            "already_exists": "资源已存在，无需重复创建；如需更新，请使用对应的更新工具",
            "permission": "权限不足，请确认用户有执行此操作的权限",
            "external": "外部服务暂时不可用，可以稍后重试或使用替代方案",
            "rate_limit": "请求过于频繁，请等待片刻后重试",
            "internal": "系统内部错误，请稍后重试",
        }

        base_hint = (
            error_type_hints.get(error_type) if error_type else None
        )

        tool_recovery_hints = {
            "update_member_info": "先用 query_members 确认成员存在",
            "delete_member": "先用 query_members 确认成员存在",
            "get_member_details": "先用 query_members 获取成员列表",
            "add_member": "如果成员已存在，使用 update_member_info 更新信息",
            "recommend_gift": "先用 query_members 确认接收者信息",
            "update_trip": "先用 query_trips 获取 trip_id，此工具仅用于更新备注/状态",
            "set_reminder": "检查时间格式是否正确（如 2024-01-15 14:30）",
            "view_tool_details": "从之前的工具执行记录中获取正确的 execution_id",
        }

        pattern_hints = []
        if "not found" in error_lower or "未找到" in error_lower:
            pattern_hints.append("目标不存在，请先查询确认")
        if "already exists" in error_lower or "已存在" in error_lower:
            pattern_hints.append("资源已存在，考虑使用更新而非创建")
        if "timeout" in error_lower or "超时" in error_lower:
            pattern_hints.append("操作超时，尝试简化参数或分步执行")

        hints = []
        if base_hint:
            hints.append(base_hint)
        hints.extend(pattern_hints)
        if tool_name in tool_recovery_hints:
            tool_hint = tool_recovery_hints[tool_name]
            if tool_hint not in hints:
                hints.append(f"💡 {tool_hint}")

        if hints:
            return " | ".join(hints[:2])

        return "请检查参数是否正确，或尝试其他方式完成任务"

    def _reflect_add_trip_itinerary(self, result: Dict[str, Any]) -> str:
        destination = result.get("destination", "")
        trip_name = result.get("trip_name", "")
        days_saved = int(result.get("days_saved", 0) or 0)
        target = trip_name or destination or "行程"

        if days_saved <= 0:
            return (
                f"⚠️ 行程更新结果不完整：{target}。"
                "❌ 未检测到新增天数。"
                "💡 建议：检查 trip_id 是否正确，或重新调用 add_trip_itinerary。"
            )

        return (
            f"✅ 已更新 {target}，新增 {days_saved} 天行程。"
            "🎯 目标已达成，可继续展示详情或收集用户调整意见。"
        )

    def _reflect_recommend_gift(self, result: Dict[str, Any]) -> str:
        recommendations = result.get("recommendations", [])
        recipient = result.get(
            "recipient_name", result.get("member_name", "")
        )
        budget = result.get("budget")

        num_recommendations = (
            len(recommendations) if isinstance(recommendations, list) else 0
        )

        if num_recommendations == 0:
            return (
                "⚠️ 礼物推荐失败：未找到合适的推荐。"
                "❌ 任务未完成，推荐列表为空。"
                "💡 建议：1) 检查收礼人信息是否完整（先查询成员详情）；"
                "2) 尝试调整预算范围或放宽偏好条件；"
                "3) 告知用户暂无合适推荐并询问是否调整需求。"
            )

        budget_note = f"（预算 {budget} 元）" if budget else ""
        return (
            f"✅ 已为{recipient}推荐 {num_recommendations} 个礼物{budget_note}。"
            "🎯 目标已达成，推荐已生成，可呈现给用户。"
            "📋 下一步：询问用户是否满意，或是否需要更多选择/不同类型。"
        )

    # ── DB persistence methods ──────────────────────────────────────

    async def persist_to_db(
        self,
        db_session,
        user_id: str,
        family_id: str,
        path_type: str = "slow",
    ) -> int:
        from .models import ToolExecutionLog

        parsed_user_id = uuid.UUID(user_id)
        parsed_family_id = uuid.UUID(family_id)

        count = 0
        for eid in self._execution_order:
            record = self._executions[eid]
            try:
                try:
                    log_id = uuid.UUID(record.execution_id)
                except (ValueError, AttributeError):
                    logger.warning(
                        "Invalid execution_id format: %s, generating new UUID",
                        record.execution_id,
                    )
                    log_id = uuid.uuid4()
                log = ToolExecutionLog(
                    id=log_id,
                    session_id=(
                        uuid.UUID(record.session_id)
                        if record.session_id
                        else None
                    ),
                    user_id=parsed_user_id,
                    family_id=parsed_family_id,
                    path_type=path_type,
                    tool_name=record.tool_name,
                    arguments=record.arguments,
                    status=record.status,
                    error_message=record.error_message,
                    summary=record.summary,
                    key_results=(
                        record.key_results if record.key_results else None
                    ),
                    full_result=(
                        record.full_result if record.full_result else None
                    ),
                    execution_time_ms=record.duration_ms,
                    iteration=record.iteration,
                )
                db_session.add(log)
                count += 1
            except Exception as e:
                logger.warning("Failed to persist execution %s: %s", eid, e)

        if count > 0:
            await db_session.flush()
        return count

    @classmethod
    async def load_from_db(
        cls, db_session, session_id: str
    ) -> "ToolExecutionStore":
        from sqlalchemy import select

        from .models import ToolExecutionLog

        store = cls(session_id=session_id)

        result = await db_session.execute(
            select(ToolExecutionLog)
            .where(ToolExecutionLog.session_id == uuid.UUID(session_id))
            .order_by(ToolExecutionLog.created_at)
        )
        logs = result.scalars().all()

        max_iteration = 1
        for log in logs:
            record = ToolExecutionRecord(
                execution_id=str(log.id),
                tool_name=log.tool_name,
                arguments=log.arguments or {},
                started_at=log.created_at,
                ended_at=log.created_at,
                duration_ms=log.execution_time_ms,
                status=log.status,
                error_message=log.error_message,
                summary=log.summary or "",
                key_results=log.key_results or {},
                full_result=log.full_result or {},
                iteration=log.iteration or 1,
                session_id=session_id,
            )
            store._executions[record.execution_id] = record
            store._execution_order.append(record.execution_id)
            if record.iteration > max_iteration:
                max_iteration = record.iteration

        store._current_iteration = max_iteration
        return store

    def get_layer1_records(self) -> List[Dict[str, Any]]:
        return [
            {
                "execution_id": record.execution_id,
                "short_id": record.short_id,
                "tool_name": record.tool_name,
                "summary": record.summary,
                "status": record.status,
            }
            for eid in self._execution_order
            for record in [self._executions[eid]]
        ]

    @staticmethod
    async def get_execution_detail(
        db_session,
        execution_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Load a single tool execution detail from DB (Layer 3).

        Verifies the user owns the session that produced this execution.
        Returns None if not found or user has no access.
        """
        from sqlalchemy import select

        from .models import ToolExecutionLog, AssistantChatSession

        result = await db_session.execute(
            select(ToolExecutionLog)
            .join(
                AssistantChatSession,
                ToolExecutionLog.session_id == AssistantChatSession.id,
            )
            .where(
                ToolExecutionLog.id == uuid.UUID(execution_id),
                AssistantChatSession.user_id == uuid.UUID(user_id),
            )
        )
        log = result.scalar_one_or_none()
        if log is None:
            return None

        return {
            "execution_id": str(log.id),
            "tool_name": log.tool_name,
            "arguments": log.arguments,
            "status": log.status,
            "summary": log.summary,
            "key_results": log.key_results,
            "full_result": log.full_result,
            "execution_time_ms": log.execution_time_ms,
            "iteration": log.iteration,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }


# Tool definition for viewing execution details
VIEW_EXECUTION_DETAILS_TOOL = {
    "type": "function",
    "function": {
        "name": "view_tool_details",
        "description": (
            "查看某次工具执行的详细结果。\n\n"
            "使用场景：\n"
            "1. 当工具结果被压缩显示时，获取完整数据\n"
            "2. 当用户询问工具结果中的具体细节时\n"
            "3. 当需要引用之前工具调用的完整原始数据时"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "execution_id": {
                    "type": "string",
                    "description": "工具执行记录的完整 UUID",
                },
                "detail_level": {
                    "type": "string",
                    "enum": ["key_results", "full"],
                    "description": "key_results=关键结果, full=完整返回",
                    "default": "key_results",
                },
            },
            "required": ["execution_id"],
        },
    },
}
