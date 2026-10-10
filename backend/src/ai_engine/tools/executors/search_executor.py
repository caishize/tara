"""Search domain tool executor — web search via WebSearchService.

Replaces SDK builtin WebSearch when the API endpoint (e.g. DashScope)
does not support server-side web search connectors.  Uses the existing
WebSearchService (Tavily / Serper / DuckDuckGo / Baidu).
"""

from typing import Any, Dict, Optional
from uuid import UUID

from ....config.logging import get_logger
from ..shared.errors import ToolErrorType, tool_error
from ..shared.progress import ProgressCallback
from .base import BaseToolExecutor

logger = get_logger(__name__)


class SearchToolExecutor(BaseToolExecutor):
    """Handles web_search tool."""

    def __init__(self, db, session_id=None):
        super().__init__(db, session_id)

    async def web_search(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Execute a web search query via WebSearchService."""
        from ..web_search import (
            get_web_search_service,
        )

        query = args.get("query", "")
        if not query:
            return tool_error(ToolErrorType.VALIDATION, "请提供搜索关键词")

        num_results = args.get("num_results", 5)

        try:
            service = get_web_search_service()
            if not service.is_available():
                return {
                    "success": False,
                    "message": "搜索服务不可用，请检查 TAVILY_API_KEY 或 SERPER_API_KEY 配置",
                }

            self._emit_progress(progress_cb, "searching", f"正在搜索: {query}")

            result = await service.search(
                query=query,
                num_results=num_results,
            )

            results = result.get("results", [])
            source = result.get("source", "unknown")

            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", r.get("snippet", "")),
                })

            return {
                "success": True,
                "results": formatted,
                "total": len(formatted),
                "source": source,
                "query": query,
                "summary": f"「{query}」搜索到 {len(formatted)} 条结果",
            }

        except Exception as e:
            logger.error("Web search failed: %s", e)
            return tool_error(ToolErrorType.INTERNAL, f"搜索失败: {e}")
