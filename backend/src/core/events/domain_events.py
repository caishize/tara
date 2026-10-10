"""
领域事件定义

定义系统中所有跨模块通信的领域事件。
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum

from .event_bus import DomainEvent


# ============ 日期管理事件 ============

@dataclass
class ImportantDateCreated(DomainEvent):
    """重要日期创建事件"""
    date_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    date_type: str = field(default="")  # birthday, anniversary, holiday, etc.
    title: str = field(default="")
    occasion_date: date = field(default=None)
    member_id: Optional[UUID] = field(default=None)
    is_recurring: bool = field(default=False)
    reminder_offsets: List[int] = field(default_factory=list)  # [-30, -7, -1, 0]
    needs_gift: bool = field(default=True)  # 是否需要送礼


@dataclass
class ImportantDateUpdated(DomainEvent):
    """重要日期更新事件"""
    date_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    changes: Dict[str, Any] = field(default_factory=dict)  # 变更的字段
    old_values: Dict[str, Any] = field(default_factory=dict)
    new_values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportantDateDeleted(DomainEvent):
    """重要日期删除事件"""
    date_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    date_type: str = field(default="")
    member_id: Optional[UUID] = field(default=None)


# ============ 礼物推荐事件 ============

@dataclass
class GiftTaskCreated(DomainEvent):
    """礼物推荐任务创建事件"""
    task_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    important_date_id: UUID = field(default=None)
    member_id: UUID = field(default=None)
    occasion: str = field(default="")
    occasion_date: date = field(default=None)
    scheduled_time: datetime = field(default=None)


@dataclass
class GiftRecommendationGenerated(DomainEvent):
    """礼物推荐生成完成事件"""
    recommendation_id: UUID = field(default=None)
    task_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    member_id: UUID = field(default=None)
    occasion: str = field(default="")
    options_count: int = field(default=0)
    personalization_score: float = field(default=0.0)


@dataclass
class GiftOptionSelected(DomainEvent):
    """礼物方案选择事件"""
    recommendation_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    member_id: UUID = field(default=None)  # 收礼人
    user_id: UUID = field(default=None)  # 选择者
    option_index: int = field(default=0)
    gift_name: str = field(default="")
    gift_category: str = field(default="")
    gift_price: Optional[float] = field(default=None)


@dataclass
class GiftRecommendationExpired(DomainEvent):
    """礼物推荐过期事件"""
    recommendation_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    member_id: UUID = field(default=None)
    occasion_date: date = field(default=None)


# ============ 礼物历史事件 ============

@dataclass
class GiftHistoryRecorded(DomainEvent):
    """送礼历史记录事件"""
    history_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    giver_user_id: UUID = field(default=None)
    recipient_member_id: UUID = field(default=None)
    gift_name: str = field(default="")
    gift_category: str = field(default="")
    occasion: str = field(default="")
    occasion_date: date = field(default=None)
    related_date_id: Optional[UUID] = field(default=None)
    recommendation_id: Optional[UUID] = field(default=None)


@dataclass
class GiftFeedbackReceived(DomainEvent):
    """礼物反馈收到事件"""
    history_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    recipient_member_id: UUID = field(default=None)
    gift_category: str = field(default="")
    feedback_rating: str = field(default="")  # love_it, like_it, neutral, dislike, hate_it
    feedback_comment: Optional[str] = field(default=None)


# ============ 成员管理事件 ============

@dataclass
class MemberProfileUpdated(DomainEvent):
    """成员画像更新事件"""
    member_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    updated_fields: List[str] = field(default_factory=list)


@dataclass
class MemberRelationChanged(DomainEvent):
    """成员关系变更事件"""
    relation_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    from_member_id: UUID = field(default=None)
    to_member_id: UUID = field(default=None)
    relation_type: str = field(default="")
    intimacy_level: int = field(default=5)


# ============ 偏好学习事件 ============

@dataclass
class PreferenceUpdated(DomainEvent):
    """偏好更新事件"""
    preference_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    member_id: UUID = field(default=None)
    gift_category: str = field(default="")
    old_score: float = field(default=0.0)
    new_score: float = field(default=0.0)
    confidence: float = field(default=0.0)
    source: str = field(default="")  # feedback, manual, inferred


# ============ 提醒事件 ============

@dataclass
class DateReminderTriggered(DomainEvent):
    """日期提醒触发事件"""
    reminder_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    date_id: UUID = field(default=None)
    member_id: Optional[UUID] = field(default=None)
    date_type: str = field(default="")
    title: str = field(default="")
    days_until: int = field(default=0)  # 距离事件还有几天
    has_gift_recommendation: bool = field(default=False)
    recommendation_id: Optional[UUID] = field(default=None)


@dataclass
class DateApproaching(DomainEvent):
    """日期临近事件 — 由 scheduler 触发，通知 curation 和 briefing"""
    date_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    days_until: int = field(default=0)
    date_type: str = field(default="")
    title: str = field(default="")
    member_id: Optional[UUID] = field(default=None)


# ============ 旅行事件 ============

@dataclass
class TripCreated(DomainEvent):
    """旅行计划创建事件 — 通知 curation 和 memory"""
    plan_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    user_id: UUID = field(default=None)
    destination: str = field(default="")
    start_date: Optional[date] = field(default=None)
    end_date: Optional[date] = field(default=None)
    trip_type: str = field(default="")


@dataclass
class TripUpdated(DomainEvent):
    """旅行计划更新事件 — 通知 curation 重新策展"""
    plan_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    destination: str = field(default="")


@dataclass
class TripCancelled(DomainEvent):
    """旅行计划取消事件 — 通知 curation 清理关联事件"""
    plan_id: UUID = field(default=None)
    family_id: UUID = field(default=None)


@dataclass
class TripDeleted(DomainEvent):
    """旅行计划删除事件 — 通知 curation 清理"""
    plan_id: UUID = field(default=None)
    family_id: UUID = field(default=None)


@dataclass
class TripCompleted(DomainEvent):
    """旅行完成事件 — 通知 memory 提取旅行记忆"""
    plan_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    trip_memory_ids: List[UUID] = field(default_factory=list)


# ============ 记忆事件 ============

@dataclass
class MemoryExtracted(DomainEvent):
    """记忆提取事件 — 通知 curation/briefing/member/relationship"""
    memory_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    user_id: UUID = field(default=None)
    memory_type: str = field(default="")
    entities: Dict[str, Any] = field(default_factory=dict)
    mentioned_persons: List[str] = field(default_factory=list)


@dataclass
class InsightGenerated(DomainEvent):
    """洞察生成事件 — 通知 briefing"""
    insight_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    insight_type: str = field(default="")
    importance_score: float = field(default=0.0)


# ============ 策展事件 ============

@dataclass
class EventCurated(DomainEvent):
    """事件策展完成 — 通知 briefing 和 graph"""
    event_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    event_type: str = field(default="")
    priority: str = field(default="")
    title: str = field(default="")


@dataclass
class EventRequested(DomainEvent):
    """Agent 工具请求创建事件 — 发给 curation"""
    family_id: UUID = field(default=None)
    user_id: UUID = field(default=None)
    title: str = field(default="")
    event_type: str = field(default="")
    start_time: Optional[datetime] = field(default=None)
    end_time: Optional[datetime] = field(default=None)
    location: Optional[str] = field(default=None)
    description: Optional[str] = field(default=None)
    source: str = field(default="agent")


# ============ 看板事件 ============

@dataclass
class PreparationToggled(DomainEvent):
    """准备项勾选事件 — 通知 briefing"""
    event_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    item_key: UUID = field(default=None)
    done: bool = field(default=False)


# ============ 人情事件 ============

@dataclass
class FavorRecorded(DomainEvent):
    """人情记录事件 — 通知 memory 和 briefing"""
    favor_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    person_id: UUID = field(default=None)
    direction: str = field(default="")  # "given" or "received"
    amount: Optional[float] = field(default=None)
    occasion: str = field(default="")


# ============ 礼物状态事件 ============

@dataclass
class GiftTaskStatusChanged(DomainEvent):
    """礼物任务状态变更 — 通知 briefing"""
    task_id: UUID = field(default=None)
    family_id: UUID = field(default=None)
    old_status: str = field(default="")
    new_status: str = field(default="")
    gift_name: Optional[str] = field(default=None)


# 事件类型到是否需要送礼的映射
GIFTABLE_DATE_TYPES = {
    "birthday",
    "anniversary",
    "holiday",
    "graduation",
    "wedding",
    "newborn",
    "housewarming",
    "promotion",
    "custom"  # custom 需要检查 needs_gift 标记
}

# 非送礼类型（健康相关）
NON_GIFTABLE_DATE_TYPES = {
    "vaccine",
    "medical_check"
}

# 日期类型到场合的映射
DATE_TYPE_TO_OCCASION = {
    "birthday": "birthday",
    "anniversary": "anniversary",
    "holiday": "holiday",
    "graduation": "graduation",
    "wedding": "wedding",
    "newborn": "newborn",
    "housewarming": "housewarming",
    "promotion": "promotion",
    "custom": "custom"
}
