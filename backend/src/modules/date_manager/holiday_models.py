"""Holiday ORM model and configuration: ChineseHolidayPlan + holiday config helpers.

Split from models.py to keep file sizes under 800 lines.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Set

from sqlalchemy import Column, String, Integer, Date, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from uuid import uuid4

from ...db.session import Base
from ...core.utils.timezone import utc_now, local_today
from .enums import HolidayCategory


# ─── Holiday Config Helpers ──────────────────────────────────────────────────


@dataclass
class HolidayMetadata:
    """Metadata for a holiday."""
    name: str
    category: HolidayCategory
    description: str
    preparation_tips: List[str]


# Major holidays - warrant 30-day advance notice for preparation
MAJOR_HOLIDAYS: Set[str] = {
    "春节",
    "国庆节",
    "中秋节",
}

# Minor holidays - 7-day advance notice
MINOR_HOLIDAYS: Set[str] = {
    "元旦",
    "清明节",
    "劳动节",
    "端午节",
    "元宵节",
    "重阳节",
    "除夕",
}

# 24 Solar Terms (二十四节气)
SOLAR_TERMS: Set[str] = {
    "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
    "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
    "立秋", "处暑", "白露", "秋分", "寒露", "霜降",
    "立冬", "小雪", "大雪", "冬至", "小寒", "大寒",
}

# Lunar holidays (农历节日)
LUNAR_HOLIDAYS: Set[str] = {
    "春节",
    "元宵节",
    "龙抬头",
    "端午节",
    "七夕节",
    "中元节",
    "中秋节",
    "重阳节",
    "腊八节",
    "小年",
    "除夕",
}


# Reminder offset configurations (days before event)
REMINDER_OFFSETS: Dict[HolidayCategory, List[int]] = {
    HolidayCategory.MAJOR: [-30, -7, -3, 0],  # Major: 30, 7, 3 days before + day of
    HolidayCategory.MINOR: [-7, -1, 0],  # Minor: 7, 1 day before + day of
    HolidayCategory.SOLAR_TERM: [-3, 0],  # Solar terms: 3 days before + day of
}


# Holiday preparation tips
HOLIDAY_TIPS: Dict[str, List[str]] = {
    "春节": [
        "提前30天预订机票/火车票",
        "准备年货清单",
        "红包预算规划",
        "大扫除安排",
        "年夜饭菜单",
    ],
    "中秋节": [
        "提前2周购买月饼",
        "安排家庭团聚",
        "准备送礼清单",
    ],
    "国庆节": [
        "规划出行计划",
        "提前预订住宿",
        "避开高峰出行",
    ],
    "清明节": [
        "安排扫墓时间",
        "准备祭扫用品",
        "注意防火安全",
    ],
    "端午节": [
        "准备粽子材料",
        "安排家庭活动",
    ],
    "冬至": [
        "北方吃饺子，南方吃汤圆",
        "注意保暖养生",
    ],
}


def get_holiday_category(holiday_name: str) -> HolidayCategory:
    """Get the category of a holiday."""
    if holiday_name in MAJOR_HOLIDAYS:
        return HolidayCategory.MAJOR
    elif holiday_name in SOLAR_TERMS:
        return HolidayCategory.SOLAR_TERM
    else:
        return HolidayCategory.MINOR


def get_reminder_offsets(holiday_name: str) -> List[int]:
    """Get reminder offsets for a holiday."""
    category = get_holiday_category(holiday_name)
    return REMINDER_OFFSETS[category]


def get_preparation_tips(holiday_name: str) -> List[str]:
    """Get preparation tips for a holiday."""
    return HOLIDAY_TIPS.get(holiday_name, [])


def is_major_holiday(holiday_name: str) -> bool:
    """Check if a holiday is a major holiday."""
    return holiday_name in MAJOR_HOLIDAYS


def is_lunar_holiday(holiday_name: str) -> bool:
    """Check if a holiday is a lunar calendar holiday."""
    return holiday_name in LUNAR_HOLIDAYS


def is_solar_term(holiday_name: str) -> bool:
    """Check if the name is a solar term."""
    return holiday_name in SOLAR_TERMS


# ─── ORM Model ───────────────────────────────────────────────────────────────


class ChineseHolidayPlan(Base):
    """中国传统节日准备方案"""
    __tablename__ = "chinese_holiday_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    family_id = Column(UUID(as_uuid=True), nullable=False)
    holiday_type = Column(String(50), nullable=False)
    holiday_year = Column(Integer, nullable=False)
    holiday_date = Column(Date, nullable=False)
    plan_content = Column(JSONB, nullable=False)
    region = Column(String(50))  # north, south, east, west, etc.
    status = Column(String(20), default="draft")  # draft, sent, adopted, in_progress, completed
    adopted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_chinese_holiday_plans_family", "family_id", "holiday_type", "holiday_year"),
    )

    # Holiday configurations
    HOLIDAY_CONFIG = {
        "spring_festival": {
            "name": "春节",
            "type": "lunar",
            "lunar_month": 1,
            "lunar_day": 1,
            "prepare_days": 30,
            "duration_days": 15,
        },
        "lantern_festival": {
            "name": "元宵节",
            "type": "lunar",
            "lunar_month": 1,
            "lunar_day": 15,
            "prepare_days": 7,
            "duration_days": 1,
        },
        "qingming": {
            "name": "清明节",
            "type": "solar_term",
            "solar_term": "清明",
            "prepare_days": 14,
            "duration_days": 3,
        },
        "dragon_boat": {
            "name": "端午节",
            "type": "lunar",
            "lunar_month": 5,
            "lunar_day": 5,
            "prepare_days": 14,
            "duration_days": 3,
        },
        "mid_autumn": {
            "name": "中秋节",
            "type": "lunar",
            "lunar_month": 8,
            "lunar_day": 15,
            "prepare_days": 21,
            "duration_days": 3,
        },
        "double_ninth": {
            "name": "重阳节",
            "type": "lunar",
            "lunar_month": 9,
            "lunar_day": 9,
            "prepare_days": 7,
            "duration_days": 1,
        },
        "winter_solstice": {
            "name": "冬至",
            "type": "solar_term",
            "solar_term": "冬至",
            "prepare_days": 7,
            "duration_days": 1,
        },
        "laba_festival": {
            "name": "腊八节",
            "type": "lunar",
            "lunar_month": 12,
            "lunar_day": 8,
            "prepare_days": 3,
            "duration_days": 1,
        },
    }

    @property
    def holiday_name(self) -> str:
        """获取节日名称"""
        config = self.HOLIDAY_CONFIG.get(self.holiday_type, {})
        return config.get("name", self.holiday_type)

    @property
    def days_until_holiday(self) -> int:
        """计算距离节日还有多少天"""
        if not self.holiday_date:
            return -1
        delta = self.holiday_date - local_today()
        return delta.days

    @property
    def is_in_preparation_window(self) -> bool:
        """检查是否在准备窗口内"""
        config = self.HOLIDAY_CONFIG.get(self.holiday_type, {})
        prepare_days = config.get("prepare_days", 14)
        return 0 < self.days_until_holiday <= prepare_days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "family_id": str(self.family_id),
            "holiday_type": self.holiday_type,
            "holiday_name": self.holiday_name,
            "holiday_year": self.holiday_year,
            "holiday_date": self.holiday_date.isoformat() if self.holiday_date else None,
            "plan_content": self.plan_content,
            "region": self.region,
            "status": self.status,
            "adopted_at": self.adopted_at.isoformat() if self.adopted_at else None,
            "days_until_holiday": self.days_until_holiday,
            "is_in_preparation_window": self.is_in_preparation_window,
        }


# Status constants for ChineseHolidayPlan
class HolidayPlanStatus:
    DRAFT = "draft"
    SENT = "sent"
    ACTIVE = "active"
    ADOPTED = "adopted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
