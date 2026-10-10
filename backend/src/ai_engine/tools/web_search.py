"""
Web Search Service.
Provides real-time web search capabilities for accurate information retrieval.
Uses Tavily, Serper, or DuckDuckGo APIs for search.
Inspired by CAMEL-AI SearchToolkit.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from ...config.settings import settings

logger = logging.getLogger(__name__)

# Try to import duckduckgo_search
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    logger.warning("duckduckgo-search not installed, DuckDuckGo search will be unavailable")


class WebSearchService:
    """Service for performing real-time web searches."""

    # Per-provider HTTP timeout (seconds). Lowered from 30s to reduce
    # cascading delays when the primary provider is unreachable.
    PROVIDER_TIMEOUT_SECONDS = 12.0
    # Total wall-clock budget for the entire search() method.
    TOTAL_SEARCH_TIMEOUT_SECONDS = 20.0

    def __init__(self):
        self.tavily_api_key = settings.tavily_api_key
        self.serper_api_key = settings.serper_api_key
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper lifecycle management."""
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                # Configure connection pool limits to prevent resource exhaustion
                limits = httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                    keepalive_expiry=30.0,
                )
                self._client = httpx.AsyncClient(
                    timeout=self.PROVIDER_TIMEOUT_SECONDS,
                    limits=limits,
                    follow_redirects=True,
                )
            return self._client

    async def close(self):
        """Close HTTP client with proper cleanup."""
        async with self._client_lock:
            if self._client is not None:
                try:
                    if not self._client.is_closed:
                        await self._client.aclose()
                except Exception as e:
                    logger.warning(f"Error closing HTTP client: {e}")
                finally:
                    self._client = None

    def is_available(self) -> bool:
        """Check if any search API is available."""
        return bool(self.tavily_api_key or self.serper_api_key or DDGS_AVAILABLE)

    async def search(
        self,
        query: str,
        num_results: int = 5,
        include_domains: Optional[List[str]] = None,
        search_depth: str = "advanced",
    ) -> Dict[str, Any]:
        """
        Perform a web search and return results.

        Args:
            query: Search query
            num_results: Number of results to return
            include_domains: Optional list of domains to include (e.g., ["dianping.com", "xiaohongshu.com"])
            search_depth: "basic" or "advanced" (for Tavily)

        Returns:
            Dict with search results and metadata
        """
        try:
            return await asyncio.wait_for(
                self._search_with_fallback(query, num_results, include_domains, search_depth),
                timeout=self.TOTAL_SEARCH_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Web search total timeout (%.0fs) exceeded for query: %s",
                self.TOTAL_SEARCH_TIMEOUT_SECONDS, query[:100],
            )
            return {"results": [], "error": f"搜索超时({self.TOTAL_SEARCH_TIMEOUT_SECONDS:.0f}s)，请稍后重试"}

    async def _search_with_fallback(
        self,
        query: str,
        num_results: int,
        include_domains: Optional[List[str]],
        search_depth: str,
    ) -> Dict[str, Any]:
        """Try providers in order, falling through on failure."""
        if self.tavily_api_key:
            result = await self._search_tavily(query, num_results, include_domains, search_depth)
            if result.get("results"):
                return result
            logger.warning("Tavily returned no results or failed, trying fallback")

        if self.serper_api_key:
            result = await self._search_serper(query, num_results)
            if result.get("results"):
                return result
            logger.warning("Serper returned no results or failed, trying fallback")

        if DDGS_AVAILABLE:
            result = await self._search_duckduckgo(query, num_results)
            if result.get("results"):
                return result
            logger.info("DuckDuckGo returned no results, trying Baidu search")

        return await self._search_baidu(query, num_results)

    async def _search_tavily(
        self,
        query: str,
        num_results: int,
        include_domains: Optional[List[str]],
        search_depth: str,
    ) -> Dict[str, Any]:
        """Search using Tavily API."""
        client = await self._get_client()

        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "max_results": num_results,
            "search_depth": search_depth,
            "include_answer": True,
            "include_raw_content": False,
        }

        if include_domains:
            payload["include_domains"] = include_domains

        try:
            response = await client.post(
                "https://api.tavily.com/search",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "answer": data.get("answer", ""),
                "results": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "content": r.get("content", ""),
                        "score": r.get("score", 0),
                    }
                    for r in data.get("results", [])
                ],
                "source": "tavily",
            }
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return {"results": [], "error": str(e)}

    async def _search_serper(
        self,
        query: str,
        num_results: int,
    ) -> Dict[str, Any]:
        """Search using Serper API (Google Search)."""
        client = await self._get_client()

        try:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={
                    "X-API-KEY": self.serper_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "q": query,
                    "num": num_results,
                    "gl": "cn",  # China locale for relevant results
                    "hl": "zh-cn",  # Chinese language
                },
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for r in data.get("organic", [])[:num_results]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "content": r.get("snippet", ""),
                    "score": r.get("position", 0),
                })

            # Include knowledge graph if available
            answer = ""
            if "knowledgeGraph" in data:
                kg = data["knowledgeGraph"]
                answer = kg.get("description", "")

            return {
                "answer": answer,
                "results": results,
                "source": "serper",
            }
        except Exception as e:
            logger.error(f"Serper search failed: {e}")
            return {"results": [], "error": str(e)}

    async def _search_duckduckgo(
        self,
        query: str,
        num_results: int,
    ) -> Dict[str, Any]:
        """
        Search using DuckDuckGo (free, no API key required).
        Inspired by CAMEL-AI SearchToolkit.
        """
        if not DDGS_AVAILABLE:
            return {"results": [], "error": "DuckDuckGo search not available"}

        try:
            # Run DuckDuckGo search in a thread pool since it's synchronous
            loop = asyncio.get_event_loop()
            results = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self._ddg_search_sync,
                    query,
                    num_results,
                ),
                timeout=self.PROVIDER_TIMEOUT_SECONDS,
            )
            return results
        except asyncio.TimeoutError:
            logger.error(
                "DuckDuckGo search timed out after %.0fs",
                self.PROVIDER_TIMEOUT_SECONDS,
            )
            return {"results": [], "error": "DuckDuckGo 搜索超时"}
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return {"results": [], "error": str(e)}

    def _ddg_search_sync(self, query: str, num_results: int) -> Dict[str, Any]:
        """Synchronous DuckDuckGo search helper."""
        results = []
        try:
            with DDGS() as ddgs:
                search_results = list(ddgs.text(
                    query,
                    region="cn-zh",  # Chinese region
                    safesearch="moderate",
                    max_results=num_results,
                ))

                for idx, r in enumerate(search_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "content": r.get("body", ""),
                        "score": 1.0 - (idx * 0.1),  # Decreasing score by position
                    })

            return {
                "answer": "",
                "results": results,
                "source": "duckduckgo",
            }
        except Exception as e:
            logger.error(f"DuckDuckGo sync search failed: {e}")
            return {"results": [], "error": str(e)}

    async def _search_baidu(
        self,
        query: str,
        num_results: int,
    ) -> Dict[str, Any]:
        """
        Search using Baidu web scraping (free, no API key required).
        Inspired by CAMEL-AI SearchToolkit's Baidu implementation.
        """
        from bs4 import BeautifulSoup
        from urllib.parse import quote

        client = await self._get_client()
        results = []

        try:
            # Baidu search URL
            encoded_query = quote(query)
            url = f"https://www.baidu.com/s?wd={encoded_query}&rn={num_results}"

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }

            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Find search result containers
            result_divs = soup.find_all("div", class_="result") or soup.find_all("div", class_="c-container")

            for idx, div in enumerate(result_divs[:num_results]):
                try:
                    # Extract title and URL
                    title_tag = div.find("h3") or div.find("a")
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)

                    # Get the link
                    link_tag = title_tag.find("a") if title_tag.name != "a" else title_tag
                    href = link_tag.get("href", "") if link_tag else ""

                    # Extract snippet/description - try multiple selectors
                    snippet = ""
                    snippet_selectors = [
                        ("span", {"class_": "content-right_8Zs40"}),
                        ("div", {"class_": "c-abstract"}),
                        ("div", {"class_": "c-span-last"}),
                        ("span", {"class_": "c-color-text"}),
                        ("div", {"class_": "c-row"}),
                        ("p", {}),
                    ]
                    for tag_name, attrs in snippet_selectors:
                        snippet_tag = div.find(tag_name, **attrs) if attrs else div.find(tag_name)
                        if snippet_tag:
                            snippet = snippet_tag.get_text(strip=True)
                            if snippet and len(snippet) > 20:  # Only use substantial snippets
                                break

                    # If still no snippet, get all text from the div
                    if not snippet or len(snippet) < 20:
                        all_text = div.get_text(strip=True)
                        # Remove title from text
                        snippet = all_text.replace(title, "").strip()[:300]

                    if title and (href or snippet):
                        results.append({
                            "title": title,
                            "url": href,
                            "content": snippet,
                            "score": 1.0 - (idx * 0.1),
                        })

                except Exception as e:
                    logger.debug(f"Failed to parse Baidu result: {e}")
                    continue

            return {
                "answer": "",
                "results": results,
                "source": "baidu",
            }

        except Exception as e:
            logger.error(f"Baidu search failed: {e}")
            return {"results": [], "error": str(e)}

    def _extract_platform(self, url: str) -> str:
        """从URL提取平台名称"""
        if not url:
            return "其他"
        url_lower = url.lower()
        if "mafengwo" in url_lower:
            return "马蜂窝"
        elif "ctrip" in url_lower:
            return "携程旅行"
        elif "xiaohongshu" in url_lower:
            return "小红书"
        elif "qyer" in url_lower:
            return "穷游网"
        elif "dianping" in url_lower:
            return "大众点评"
        elif "qunar" in url_lower:
            return "去哪儿"
        elif "fliggy" in url_lower or "alitrip" in url_lower:
            return "飞猪"
        return "其他"

    async def search_attractions(
        self,
        destination: str,
        styles: Optional[List[str]] = None,
        family_has_children: bool = False,
        family_has_elderly: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        搜索目的地景点攻略

        Args:
            destination: 目的地
            styles: 行程风格关键词 (如 ["文化历史", "户外探险"])
            family_has_children: 是否有儿童
            family_has_elderly: 是否有老人

        Returns:
            景点信息列表，包含来源URL和平台信息
        """
        current_year = local_now().year
        queries = [f"{destination} 旅游攻略 必去景点 {current_year}"]

        if styles:
            for style in styles[:2]:
                queries.append(f"{destination} {style} 景点推荐")

        if family_has_children:
            queries.append(f"{destination} 亲子游 儿童乐园 推荐")

        if family_has_elderly:
            queries.append(f"{destination} 适合老人 休闲景点")

        # 并发搜索
        search_tasks = [
            self.search(
                query,
                num_results=5,
                include_domains=["mafengwo.cn", "ctrip.com", "xiaohongshu.com", "qyer.com"],
            )
            for query in queries
        ]

        try:
            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            attractions = []
            seen_urls = set()

            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Attraction search failed: {result}")
                    continue
                if "error" in result:
                    continue
                for r in result.get("results", []):
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        attractions.append({
                            "title": r.get("title", ""),
                            "url": url,
                            "content": r.get("content", ""),
                            "platform": self._extract_platform(url),
                            "score": r.get("score", 0),
                        })

            return attractions[:15]  # 最多返回15条

        except Exception as e:
            logger.error(f"Search attractions failed: {e}")
            return []

    async def search_restaurants(
        self,
        destination: str,
        cuisine_types: Optional[List[str]] = None,
        occasion: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for restaurant recommendations for a destination.

        Args:
            destination: Travel destination (e.g., "深圳大鹏")
            cuisine_types: Optional list of cuisine types to search for
            occasion: Optional occasion (e.g., "家庭聚餐", "有老人小孩")

        Returns:
            List of restaurant information dictionaries
        """
        restaurants = []

        # Build search queries
        queries = []
        base_query = f"{destination} 美食推荐 餐厅"

        if cuisine_types:
            for cuisine in cuisine_types[:3]:  # Limit to top 3 cuisines
                queries.append(f"{destination} {cuisine} 推荐 好吃")
        else:
            queries.append(f"{base_query} 必吃")
            queries.append(f"{destination} 大众点评 高分餐厅")

        if occasion:
            queries.append(f"{destination} {occasion} 餐厅推荐")

        # Perform searches concurrently
        search_tasks = [
            self.search(
                query,
                num_results=3,
                include_domains=["dianping.com", "xiaohongshu.com", "mafengwo.cn"],
            )
            for query in queries
        ]

        try:
            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Search failed: {result}")
                    continue

                if "error" not in result:
                    for r in result.get("results", []):
                        # Extract restaurant info from search results
                        restaurants.append({
                            "source": r.get("url", ""),
                            "title": r.get("title", ""),
                            "snippet": r.get("content", ""),
                            "relevance": r.get("score", 0),
                        })
        except Exception as e:
            logger.error(f"Restaurant search failed: {e}")

        return restaurants

# Singleton instance with proper lifecycle management
_web_search_service: Optional[WebSearchService] = None
_service_lock = asyncio.Lock()


def get_web_search_service() -> WebSearchService:
    """Get the web search service singleton."""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService()
    return _web_search_service


async def cleanup_web_search_service():
    """
    Cleanup the web search service singleton.

    Call this function during application shutdown to properly close HTTP connections.
    """
    global _web_search_service
    if _web_search_service is not None:
        await _web_search_service.close()
        _web_search_service = None
        logger.info("Web search service HTTP client closed")
