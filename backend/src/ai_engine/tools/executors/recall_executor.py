"""
Recall Executor - Provides tools for querying tool execution history.

Tools:
- view_tool_details: View Layer 2/3 details of a specific execution (by UUID PK)
- recall_tool_result: Search historical tool executions across sessions
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, or_

from ..shared.errors import tool_error, ToolErrorType
from ..shared.progress import ProgressCallback
from ..shared.sql_utils import escape_like
from .base import BaseToolExecutor

logger = logging.getLogger(__name__)


class RecallToolExecutor(BaseToolExecutor):
    """Executor for tool execution recall and detail viewing."""

    MAX_KEYWORD_LENGTH = 200  # Prevent unbounded LIKE pattern size
    MAX_TOOL_NAME_LENGTH = 100

    async def view_tool_details(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """
        View details of a specific tool execution by UUID.

        Returns Layer 2 (key_results) or Layer 3 (full_result) based on detail_level.
        """
        from ....modules.conversation.models import ToolExecutionLog

        execution_id_str = args.get("execution_id", "")
        detail_level = args.get("detail_level", "key_results")

        try:
            execution_id = UUID(execution_id_str)
        except (ValueError, AttributeError):
            return tool_error(
                ToolErrorType.VALIDATION,
                "无效的执行记录 ID 格式",
                hint="请提供完整的 UUID 格式，如 a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            )

        result = await self.db.execute(
            select(ToolExecutionLog).where(
                ToolExecutionLog.id == execution_id,
                ToolExecutionLog.user_id == user_id,
            )
        )
        log = result.scalar_one_or_none()

        if not log:
            return tool_error(
                ToolErrorType.NOT_FOUND,
                "未找到该执行记录",
                hint="该记录可能已过期清理，仅保留摘要信息",
            )

        if detail_level == "full":
            return {
                "success": True,
                "execution_id": str(log.id),
                "short_id": str(log.id).split("-")[0],
                "tool_name": log.tool_name,
                "arguments": log.arguments,
                "status": log.status,
                "summary": log.summary,
                "key_results": log.key_results,
                "full_result": log.full_result,
                "execution_time_ms": log.execution_time_ms,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }

        return {
            "success": True,
            "execution_id": str(log.id),
            "short_id": str(log.id).split("-")[0],
            "tool_name": log.tool_name,
            "status": log.status,
            "summary": log.summary,
            "key_results": log.key_results,
            "execution_time_ms": log.execution_time_ms,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    async def recall_tool_result(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """
        Search historical tool executions across sessions.

        Uses user_id index for efficient cross-session lookups.
        """
        from ....modules.conversation.models import ToolExecutionLog

        keyword = args.get("keyword", "")
        tool_name_filter = args.get("tool_name")
        limit = max(1, min(args.get("limit", 5), 20))

        if not keyword:
            return tool_error(
                ToolErrorType.VALIDATION,
                "请提供搜索关键词",
            )

        if len(keyword) > self.MAX_KEYWORD_LENGTH:
            keyword = keyword[:self.MAX_KEYWORD_LENGTH]

        escaped_keyword = escape_like(keyword)

        # Search summary (indexed via ix_tool_exec_user) and tool_name.
        # Avoid casting JSONB→String for ILIKE as it triggers full-table
        # scans.  The summary field already captures the human-readable
        # essence of each execution; tool_name covers tool-specific recall.
        conditions = [
            ToolExecutionLog.user_id == user_id,
            ToolExecutionLog.status == "success",
            or_(
                ToolExecutionLog.summary.ilike(f"%{escaped_keyword}%", escape="\\"),
                ToolExecutionLog.tool_name.ilike(f"%{escaped_keyword}%", escape="\\"),
            ),
        ]

        if tool_name_filter:
            if len(tool_name_filter) > self.MAX_TOOL_NAME_LENGTH:
                tool_name_filter = tool_name_filter[:self.MAX_TOOL_NAME_LENGTH]
            conditions.append(ToolExecutionLog.tool_name == tool_name_filter)

        query = (
            select(ToolExecutionLog)
            .where(*conditions)
            .order_by(ToolExecutionLog.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        logs = result.scalars().all()

        return {
            "success": True,
            "keyword": keyword,
            "count": len(logs),
            "results": [
                {
                    "execution_id": str(log.id),
                    "short_id": str(log.id).split("-")[0],
                    "tool_name": log.tool_name,
                    "summary": log.summary,
                    "arguments_brief": self._format_args_brief(log.arguments),
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
            "hint": "使用 view_tool_details(execution_id) 查看任一结果的详细内容",
        }

    @staticmethod
    def _format_args_brief(arguments: Optional[Dict[str, Any]]) -> str:
        """Format arguments as a brief string for display."""
        if not arguments:
            return ""
        parts = []
        for key, value in list(arguments.items())[:3]:
            val_str = str(value)[:50]
            parts.append(f"{key}={val_str}")
        brief = ", ".join(parts)
        if len(arguments) > 3:
            brief += f" (+{len(arguments) - 3} more)"
        return brief
