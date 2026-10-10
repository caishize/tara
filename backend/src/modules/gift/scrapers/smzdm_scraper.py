"""
SMZDM (什么值得买) scraper for trending gifts.

SMZDM aggregates deals from multiple platforms, making it a good source
for gift recommendations with price/discount data.
"""

import httpx
import asyncio
import random
import re
from typing import Optional, List
from datetime import datetime
from bs4 import BeautifulSoup
import logging

from .base_scraper import BaseScraper, ScrapedGift
from ..models import GiftCategory
from ....core.utils.timezone import utc_now


# Category mapping to SMZDM category slugs
SMZDM_CATEGORY_MAP = {
    GiftCategory.ELECTRONICS: ["shouji", "diannaoshuma"],
    GiftCategory.FASHION: ["fushi", "xie", "xiangbao"],
    GiftCategory.JEWELRY: ["zhubao"],
    GiftCategory.COSMETICS: ["hufu", "geren"],
    GiftCategory.HEALTH: ["yingyangbaojian"],
    GiftCategory.BOOKS: ["tushu"],
    GiftCategory.TOYS: ["wanju", "muyingwanju"],
    GiftCategory.SPORTS: ["yundong", "huwai"],
    GiftCategory.HOME: ["jiaju", "shenghuodianqi"],
    GiftCategory.FOOD: ["shipin", "jiuxian"],
    GiftCategory.EXPERIENCE: None,
    GiftCategory.CUSTOM: None,
}

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


class SMZDMScraper(BaseScraper):
    """
    SMZDM (什么值得买) scraper.

    Scrapes deal recommendations which include:
    - Cross-platform price comparisons
    - User ratings and popularity
    - Historical pricing data
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("smzdm", "https://www.smzdm.com")
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers=self._get_headers()
            )
        return self._client

    def _get_headers(self) -> dict:
        """Get request headers with random User-Agent."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Referer": "https://www.smzdm.com/",
        }

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with error handling and rate limiting."""
        try:
            await asyncio.sleep(random.uniform(1.0, 3.0))

            response = await self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error fetching {url}: {e.response.status_code}")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from text like '¥199' or '199元'."""
        if not price_text:
            return None
        price_str = re.sub(r'[¥￥元]', '', price_text).strip()
        try:
            return float(price_str)
        except ValueError:
            return None

    def _parse_rating(self, rating_element) -> Optional[float]:
        """Parse rating from SMZDM's worthiness indicator."""
        if not rating_element:
            return None
        try:
            zhi_count = rating_element.get_text(strip=True)
            count = int(re.sub(r'[^\d]', '', zhi_count) or 0)
            return min(5.0, count / 200)
        except Exception:
            return None

    def _extract_deal_info(self, item_element, category: GiftCategory, rank: int) -> Optional[ScrapedGift]:
        """Extract deal information from a SMZDM item element."""
        try:
            title_elem = item_element.select_one('.feed-block-title, .z-highlight, h5.item-name, a.item-link-name')
            if not title_elem:
                return None

            name = title_elem.get_text(strip=True)
            if not name:
                return None

            link_elem = item_element.select_one('a[href*="/p/"]')
            external_id = None
            product_url = None
            if link_elem:
                href = link_elem.get('href', '')
                product_url = href if href.startswith('http') else f"https://www.smzdm.com{href}"
                id_match = re.search(r'/p/(\d+)', href)
                if id_match:
                    external_id = id_match.group(1)

            if not external_id:
                external_id = f"smzdm_{category.value}_{rank}_{utc_now().strftime('%Y%m%d')}"

            img_elem = item_element.select_one('img.z-feed-img, img.item-img, .feed-block-img img')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src') or img_elem.get('data-src')
                if image_url and not image_url.startswith('http'):
                    image_url = f"https:{image_url}"

            price_elem = item_element.select_one('.z-highlight, .red-price, .item-price, .feed-block-price')
            price = self._parse_price(price_elem.get_text(strip=True) if price_elem else None) or 0

            original_price_elem = item_element.select_one('.item-original-price, del')
            original_price = self._parse_price(original_price_elem.get_text(strip=True) if original_price_elem else None)

            desc_elem = item_element.select_one('.feed-block-descripe, .item-descripe, .feed-block-extras')
            description = desc_elem.get_text(strip=True)[:200] if desc_elem else None

            brand = None
            if name:
                brand_match = re.match(r'^([A-Za-z]+|[\u4e00-\u9fa5]{2,4})', name)
                if brand_match:
                    brand = brand_match.group(1)

            rating_elem = item_element.select_one('.z-group-data, .praise-num')
            rating = self._parse_rating(rating_elem) or 4.0

            comment_elem = item_element.select_one('.comment-num, .z-group-data')
            review_count = 0
            if comment_elem:
                count_text = comment_elem.get_text(strip=True)
                count_match = re.search(r'(\d+)', count_text)
                if count_match:
                    review_count = int(count_match.group(1))

            return ScrapedGift(
                external_id=external_id,
                name=name,
                brand=brand,
                price=price,
                original_price=original_price,
                discount_percent=self._calculate_discount_percent(price, original_price) if original_price else None,
                rating=rating,
                review_count=review_count,
                image_url=image_url,
                product_url=product_url,
                category=category,
                data_source=self.source_name,
                rank=rank,
                popularity_score=self._calculate_popularity_score(
                    rating=rating,
                    review_count=review_count,
                    rank=rank
                ),
                description=description or "热门好价，值得入手"
            )

        except Exception as e:
            self.logger.error(f"Error extracting deal info: {e}")
            return None

    async def scrape_category(
        self,
        category: GiftCategory,
        limit: int = 50
    ) -> list:
        """Scrape gifts from a SMZDM category."""
        smzdm_cats = SMZDM_CATEGORY_MAP.get(category)
        if not smzdm_cats:
            self.logger.warning(f"No SMZDM category mapping for {category.value}")
            return []

        all_gifts = []

        for smzdm_cat in smzdm_cats:
            if len(all_gifts) >= limit:
                break

            url = f"https://www.smzdm.com/fenlei/{smzdm_cat}/"
            self.logger.info(f"Scraping SMZDM category: {url}")

            html = await self._fetch_page(url)
            if not html:
                continue

            soup = BeautifulSoup(html, 'html.parser')
            items = soup.select('.feed-block, .feed-row-wide, .list-ajax-container > li')

            for i, item in enumerate(items):
                if len(all_gifts) >= limit:
                    break

                gift = self._extract_deal_info(item, category, len(all_gifts) + 1)
                if gift and gift.price > 0:
                    all_gifts.append(gift)

        self.logger.info(f"Scraped {len(all_gifts)} gifts for category {category.value}")
        return all_gifts[:limit]

    async def scrape_trending(self, limit: int = 100) -> list:
        """Scrape overall hot deals from SMZDM's hot list."""
        url = "https://www.smzdm.com/top/"
        self.logger.info(f"Scraping SMZDM trending: {url}")

        html = await self._fetch_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        all_gifts = []

        items = soup.select('.feed-block, .feed-row-wide, .top-list-item')

        for i, item in enumerate(items):
            if len(all_gifts) >= limit:
                break

            category = self._detect_category(item)
            gift = self._extract_deal_info(item, category, i + 1)
            if gift and gift.price > 0:
                all_gifts.append(gift)

        self.logger.info(f"Scraped {len(all_gifts)} trending gifts from SMZDM")
        return all_gifts

    def _detect_category(self, item_element) -> GiftCategory:
        """Try to detect category from item element."""
        item_text = item_element.get_text().lower()

        category_keywords = {
            GiftCategory.ELECTRONICS: ['手机', '电脑', '数码', '耳机', '相机', 'iphone', 'ipad', '笔记本'],
            GiftCategory.FASHION: ['服装', '鞋', '包', '衣服', '外套', '裤子', '裙'],
            GiftCategory.COSMETICS: ['化妆', '护肤', '美妆', '口红', '面膜', '精华'],
            GiftCategory.HOME: ['家居', '家电', '厨房', '清洁', '收纳', '床上用品'],
            GiftCategory.FOOD: ['食品', '零食', '饮料', '咖啡', '茶', '酒', '巧克力'],
            GiftCategory.SPORTS: ['运动', '户外', '健身', '球', '跑步'],
            GiftCategory.TOYS: ['玩具', '模型', '乐高', '游戏', 'switch', 'ps5'],
            GiftCategory.BOOKS: ['图书', '书籍', '书', '阅读'],
            GiftCategory.HEALTH: ['保健', '维生素', '营养', '健康'],
            GiftCategory.JEWELRY: ['手表', '首饰', '珠宝', '戒指', '项链'],
        }

        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in item_text:
                    return category

        return GiftCategory.ELECTRONICS

    async def scrape_gift_guide(self, occasion: str) -> list:
        """Scrape SMZDM's gift guide articles for an occasion."""
        search_url = f"https://www.smzdm.com/search/?q={occasion}礼物&c=home"
        self.logger.info(f"Searching SMZDM gift guides: {search_url}")

        html = await self._fetch_page(search_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        all_gifts = []

        items = soup.select('.feed-block, .search-list-item')
        for i, item in enumerate(items[:20]):
            category = self._detect_category(item)
            gift = self._extract_deal_info(item, category, i + 1)
            if gift:
                all_gifts.append(gift)

        return all_gifts

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None
