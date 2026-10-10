"""Gift trending / occasion / data-source domain models.

SQLAlchemy models for the trending side of the gift module:
    - trending_gifts: trending/seasonal gifts from external sources
    - occasions: preset occasion definitions (holidays, etc.)
    - occasion_gifts: many-to-many linking occasions to trending gifts
    - data_sources: configuration for trending gift data sources
    - update_logs: tracking data update task executions
    - user_gift_saves: user favorited/saved trending gifts
"""
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ...db.session import Base
from ...core.utils.timezone import utc_now
from .models_enums import DateType, GiftCategory, UpdateStatus


class TrendingGift(Base):
    """TrendingGift entity — fetched from external sources."""

    __tablename__ = "trending_gifts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    external_id = Column(String(100), nullable=False)
    data_source = Column(String(50), nullable=False)

    name = Column(String(500), nullable=False)
    brand = Column(String(200), nullable=True)

    price = Column(Numeric(10, 2), nullable=False)
    original_price = Column(Numeric(10, 2), nullable=True)
    discount_percent = Column(Integer, nullable=True)

    rating = Column(Numeric(2, 1), nullable=True)
    review_count = Column(Integer, default=0)

    image_url = Column(String(1000), nullable=True)
    product_url = Column(String(1000), nullable=True)

    category = Column(String(50), nullable=False)
    popularity_score = Column(Integer, default=0)
    rank = Column(Integer, nullable=True)
    description = Column(String(500), nullable=True)

    is_active = Column(Boolean, default=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TrendingGift(id={self.id}, name={self.name[:30]}..., category={self.category})>"

    @property
    def gift_category(self) -> GiftCategory:
        return GiftCategory(self.category)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "external_id": self.external_id,
            "name": self.name,
            "brand": self.brand,
            "price": float(self.price) if self.price else None,
            "original_price": float(self.original_price) if self.original_price else None,
            "discount_percent": self.discount_percent,
            "rating": float(self.rating) if self.rating else None,
            "review_count": self.review_count,
            "image_url": self.image_url,
            "product_url": self.product_url,
            "category": self.category,
            "data_source": self.data_source,
            "popularity_score": self.popularity_score,
            "rank": self.rank,
            "description": self.description,
            "is_active": self.is_active,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Occasion(Base):
    """Occasion entity — preset occasions for gift recommendations."""

    __tablename__ = "occasions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String(100), nullable=False, unique=True)
    name_en = Column(String(100), nullable=True, unique=True)

    date_type = Column(String(20), nullable=False)
    solar_date = Column(String(10), nullable=True)
    lunar_month = Column(Integer, nullable=True)
    lunar_day = Column(Integer, nullable=True)
    week_ordinal = Column(Integer, nullable=True)
    weekday = Column(Integer, nullable=True)

    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    gift_categories = Column(ARRAY(String), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Occasion(id={self.id}, name={self.name}, date_type={self.date_type})>"

    @property
    def occasion_date_type(self) -> DateType:
        return DateType(self.date_type)

    @property
    def categories(self) -> List[GiftCategory]:
        if not self.gift_categories:
            return []
        return [GiftCategory(cat) for cat in self.gift_categories if cat in GiftCategory._value2member_map_]

    def calculate_date(self, year: int) -> Optional[date]:
        if self.date_type == DateType.SOLAR.value:
            return self._calculate_solar_date(year)
        elif self.date_type == DateType.LUNAR.value:
            return self._calculate_lunar_date(year)
        elif self.date_type == DateType.RELATIVE.value:
            return self._calculate_relative_date(year)
        return None

    def _calculate_solar_date(self, year: int) -> Optional[date]:
        if not self.solar_date:
            return None
        try:
            month, day = map(int, self.solar_date.split("-"))
            return date(year, month, day)
        except (ValueError, AttributeError):
            return None

    def _calculate_lunar_date(self, year: int) -> Optional[date]:
        if not self.lunar_month or not self.lunar_day:
            return None
        try:
            from lunardate import LunarDate
            lunar = LunarDate(year, self.lunar_month, self.lunar_day)
            return lunar.toSolarDate()
        except (ImportError, ValueError):
            return None

    def _calculate_relative_date(self, year: int) -> Optional[date]:
        if self.week_ordinal is None or self.weekday is None:
            return None
        month = self._get_relative_month()
        if not month:
            return None
        try:
            first_day = date(year, month, 1)
            days_until_target = (self.weekday - first_day.weekday()) % 7
            first_occurrence = first_day.replace(day=1 + days_until_target)
            target_date = first_occurrence.replace(
                day=first_occurrence.day + (self.week_ordinal - 1) * 7
            )
            return target_date
        except ValueError:
            return None

    def _get_relative_month(self) -> Optional[int]:
        relative_months = {
            "mothers_day": 5,
            "fathers_day": 6,
            "thanksgiving": 11,
        }
        return relative_months.get(self.name_en)

    def days_until(self, from_date: Optional[date] = None) -> Optional[int]:
        if from_date is None:
            from_date = date.today()
        year = from_date.year
        occasion_date = self.calculate_date(year)
        if occasion_date is None:
            return None
        if occasion_date < from_date:
            occasion_date = self.calculate_date(year + 1)
        if occasion_date is None:
            return None
        return (occasion_date - from_date).days

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "name_en": self.name_en,
            "date_type": self.date_type,
            "solar_date": self.solar_date,
            "lunar_month": self.lunar_month,
            "lunar_day": self.lunar_day,
            "week_ordinal": self.week_ordinal,
            "weekday": self.weekday,
            "is_active": self.is_active,
            "description": self.description,
            "gift_categories": self.gift_categories,
        }


class OccasionGift(Base):
    """OccasionGift entity — links occasions to trending gifts."""

    __tablename__ = "occasion_gifts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    occasion_id = Column(UUID(as_uuid=True), ForeignKey("occasions.id", ondelete="CASCADE"), nullable=False)
    gift_id = Column(UUID(as_uuid=True), ForeignKey("trending_gifts.id", ondelete="CASCADE"), nullable=False)

    sort_order = Column(Integer, default=0)
    match_reason = Column(String(200), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    occasion = relationship("Occasion", backref="occasion_gifts")
    gift = relationship("TrendingGift", backref="occasion_gifts")

    def __repr__(self):
        return f"<OccasionGift(occasion_id={self.occasion_id}, gift_id={self.gift_id})>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "occasion_id": str(self.occasion_id),
            "gift_id": str(self.gift_id),
            "sort_order": self.sort_order,
            "match_reason": self.match_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DataSource(Base):
    """DataSource entity — configuration for trending gift data sources."""

    __tablename__ = "data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String(100), nullable=False, unique=True)
    source_type = Column(String(50), nullable=False)
    base_url = Column(String(500), nullable=False)
    config = Column(JSONB, default={})

    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    last_fetch_at = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DataSource(id={self.id}, name={self.name}, type={self.source_type})>"

    @property
    def is_scraper(self) -> bool:
        return self.source_type == "scraper"

    @property
    def is_api(self) -> bool:
        return self.source_type == "api"

    def get_config_value(self, key: str, default: Any = None) -> Any:
        if not self.config:
            return default
        return self.config.get(key, default)

    def increment_error_count(self) -> None:
        self.error_count = (self.error_count or 0) + 1

    def reset_error_count(self) -> None:
        self.error_count = 0

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "source_type": self.source_type,
            "base_url": self.base_url,
            "is_active": self.is_active,
            "priority": self.priority,
            "last_fetch_at": self.last_fetch_at.isoformat() if self.last_fetch_at else None,
            "error_count": self.error_count,
        }


class UpdateLog(Base):
    """UpdateLog entity — tracks data update task executions."""

    __tablename__ = "update_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    task_id = Column(String(100), nullable=True, unique=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False)

    gifts_added = Column(Integer, default=0)
    gifts_updated = Column(Integer, default=0)
    gifts_deleted = Column(Integer, default=0)

    error_message = Column(Text, nullable=True)
    source_stats = Column(JSONB, default={})

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<UpdateLog(id={self.id}, task_id={self.task_id}, status={self.status})>"

    @property
    def update_status(self) -> UpdateStatus:
        return UpdateStatus(self.status)

    @property
    def duration_seconds(self) -> Optional[float]:
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def total_gifts_processed(self) -> int:
        return (self.gifts_added or 0) + (self.gifts_updated or 0)

    def mark_running(self, task_id: Optional[str] = None) -> None:
        self.status = UpdateStatus.RUNNING.value
        self.started_at = utc_now()
        if task_id:
            self.task_id = task_id

    def mark_success(self, gifts_added: int = 0, gifts_updated: int = 0, gifts_deleted: int = 0) -> None:
        self.status = UpdateStatus.SUCCESS.value
        self.completed_at = utc_now()
        self.gifts_added = gifts_added
        self.gifts_updated = gifts_updated
        self.gifts_deleted = gifts_deleted

    def mark_failed(self, error_message: str) -> None:
        self.status = UpdateStatus.FAILED.value
        self.completed_at = utc_now()
        self.error_message = error_message

    def mark_partial(self, error_message: str, gifts_added: int = 0, gifts_updated: int = 0) -> None:
        self.status = UpdateStatus.PARTIAL.value
        self.completed_at = utc_now()
        self.error_message = error_message
        self.gifts_added = gifts_added
        self.gifts_updated = gifts_updated

    def add_source_stat(self, source_name: str, stat: Dict[str, Any]) -> None:
        if not self.source_stats:
            self.source_stats = {}
        self.source_stats[source_name] = stat

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "gifts_added": self.gifts_added,
            "gifts_updated": self.gifts_updated,
            "gifts_deleted": self.gifts_deleted,
            "error_message": self.error_message,
            "source_stats": self.source_stats,
            "duration_seconds": self.duration_seconds,
        }


class UserGiftSave(Base):
    """UserGiftSave entity — user's saved/favorited trending gifts."""

    __tablename__ = "user_gift_saves"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gift_id = Column(UUID(as_uuid=True), ForeignKey("trending_gifts.id", ondelete="CASCADE"), nullable=False)

    saved_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    note = Column(String(500), nullable=True)

    gift = relationship("TrendingGift", backref="user_saves")

    def __repr__(self):
        return f"<UserGiftSave(user_id={self.user_id}, gift_id={self.gift_id})>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "gift_id": str(self.gift_id),
            "saved_at": self.saved_at.isoformat() if self.saved_at else None,
            "note": self.note,
        }
