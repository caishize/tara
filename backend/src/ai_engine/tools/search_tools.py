"""
Web search tools for Claude Agent.

Custom MCP web search tool using WebSearchService (Tavily/Serper/DuckDuckGo)
as a replacement for SDK builtin WebSearch, which requires the official
Anthropic API and does not work with compatible proxies like DashScope.
"""

from .registry import ToolCategory, ToolRegistry
from .shared.wrap import wrap_method as _wrap_method
from .executors.search_executor import SearchToolExecutor


def register_search_tools(
    registry: ToolRegistry,
    executor: SearchToolExecutor,
) -> None:
    """Register web search tools with the registry."""

    registry.register(
        name="web_search",
        description=(
            "搜索互联网获取实时信息。用于查询旅行攻略、美食推荐、"
            "景点信息、天气、新闻等需要最新数据的场景。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词",
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认5",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        executor=_wrap_method(executor.web_search),
        category=ToolCategory.SEARCH,
    )
