"""Base scraper abstract class for trending gifts data sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import logging

from ..models import GiftCategory
from ....core.utils.timezone import utc_now


@dataclass
class ScrapedGift:
    """Data class representing a scraped gift item."""

    external_id: str
    name: str
    price: float
    category: GiftCategory
    data_source: str

    # Optional fields
    brand: Optional[str] = None
    original_price: Optional[float] = None
    discount_percent: Optional[int] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    popularity_score: Optional[int] = None
    rank: Optional[int] = None
    description: Optional[str] = None

    # Metadata
    scraped_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "external_id": self.external_id,
            "name": self.name,
            "brand": self.brand,
            "price": self.price,
            "original_price": self.original_price,
            "discount_percent": self.discount_percent,
            "rating": self.rating,
            "review_count": self.review_count,
            "image_url": self.image_url,
            "product_url": self.product_url,
            "category": self.category,
            "data_source": self.data_source,
            "popularity_score": self.popularity_score,
            "rank": self.rank,
            "description": self.description,
        }


class BaseScraper(ABC):
    """Abstract base class for all gift scrapers."""

    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url
        self.logger = logging.getLogger(f"scraper.{source_name}")

    @abstractmethod
    async def scrape_category(
        self,
        category: GiftCategory,
        limit: int = 50
    ) -> List[ScrapedGift]:
        pass

    @abstractmethod
    async def scrape_trending(self, limit: int = 100) -> List[ScrapedGift]:
        pass

    async def scrape_all_categories(
        self,
        categories: Optional[List[GiftCategory]] = None,
        limit_per_category: int = 20
    ) -> List[ScrapedGift]:
        if categories is None:
            categories = list(GiftCategory)

        all_gifts: List[ScrapedGift] = []

        for category in categories:
            try:
                self.logger.info(f"Scraping category: {category.value}")
                gifts = await self.scrape_category(category, limit_per_category)
                all_gifts.extend(gifts)
                self.logger.info(f"Scraped {len(gifts)} items from {category.value}")
            except Exception as e:
                self.logger.error(f"Failed to scrape {category.value}: {e}")
                continue

        return all_gifts

    def _calculate_popularity_score(
        self,
        rating: Optional[float] = None,
        review_count: Optional[int] = None,
        sales_count: Optional[int] = None,
        rank: Optional[int] = None
    ) -> int:
        score = 500

        if rating is not None:
            score += int(rating * 40)

        if review_count is not None:
            import math
            if review_count > 0:
                score += min(200, int(math.log10(review_count + 1) * 50))

        if sales_count is not None:
            import math
            if sales_count > 0:
                score += min(200, int(math.log10(sales_count + 1) * 40))

        if rank is not None:
            score += max(0, 200 - (rank * 2))

        return min(1000, max(0, score))

    def _calculate_discount_percent(
        self,
        price: float,
        original_price: Optional[float]
    ) -> Optional[int]:
        if original_price is None or original_price <= price:
            return None
        return int((1 - price / original_price) * 100)
