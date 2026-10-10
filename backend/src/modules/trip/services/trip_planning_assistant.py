"""
Trip Planning Assistant - higher-level assistant for trip planning integration.

Provides convenience methods for integrating trip planning into the conversation flow,
including PRD 4.2 card-style formatting.

Extracted from trip_context_planner_service.py for file size management.
"""
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from .trip_context_types import TripContextPlan, TripPlanItem
from .trip_context_planner_service import TripContextPlannerService
from ....config.logging import get_logger

logger = get_logger(__name__)


class TripPlanningAssistant:
    """
    Higher-level assistant for trip planning integration.

    This class provides convenience methods for integrating trip planning
    into the conversation flow.
    """

    def __init__(self, db: AsyncSession):
        from uuid import UUID
        self.planner = TripContextPlannerService(db)

    async def check_and_plan(
        self,
        user_id: "UUID",
        message: str,
        detected_locations: List[str],
        family_id: Optional["UUID"] = None,
    ) -> Optional[TripContextPlan]:
        """
        Check if the message warrants trip planning and generate plan if so.

        PRD 4.2: 时空关联建议卡片
        - 检测出差/旅行意图
        - 自动关联目的地相关的人物、礼物、重要日期

        Args:
            user_id: The user ID
            message: The user message
            detected_locations: List of locations detected in the message
            family_id: Optional family ID for date lookups

        Returns:
            TripContextPlan if planning is warranted, None otherwise
        """
        from uuid import UUID

        # Check if message contains trip-related keywords
        trip_keywords = ["出差", "旅行", "旅游", "去", "到", "行程", "规划", "下周", "下个月"]
        has_trip_intent = any(kw in message for kw in trip_keywords)

        if not has_trip_intent or not detected_locations:
            return None

        # Generate plan for the first detected location
        destination = detected_locations[0]

        try:
            plan = await self.planner.generate_trip_plan(
                user_id=user_id,
                destination=destination,
                additional_context=message,
                family_id=family_id,
            )

            # Only return if plan has meaningful content
            if plan.items or plan.people_to_meet or plan.tasks:
                return plan

        except Exception as e:
            logger.error(f"Trip planning failed: {e}")

        return None

    async def format_plan_for_response(self, plan: TripContextPlan) -> str:
        """
        Format a trip plan for inclusion in assistant response.

        PRD 4.2 卡片样式:
        ┌─ 📍 北京出差 · 智能建议 ─────────────┐
        │ 👤 李思远（5年未见），建议周二晚约    │
        │ 🎁 之前提过给孩子买北京特色绘本       │
        │ ⚠️ 周二岳父生日，建议今天寄出礼物     │
        └─────────────────────────────────────┘
        """
        if not plan.items and not plan.people_to_meet and not plan.tasks and not plan.reminders:
            return ""

        # Categorize items
        category_map = {"meeting": [], "task": [], "reminder": [], "suggestion": []}
        for item in plan.items:
            category = item.category if item.category in category_map else "suggestion"
            category_map[category].append(item)

        # Build card items with icons
        card_items: List[str] = []

        # 1. People to meet (highest priority)
        if category_map["meeting"]:
            card_items.extend(
                _format_prd_card_item(item, "👤") for item in category_map["meeting"]
            )
        elif plan.people_to_meet:
            card_items.extend(
                f"👤 {person}，建议抽空见面" for person in plan.people_to_meet
            )

        # 2. Tasks/Gifts
        if category_map["task"]:
            card_items.extend(
                _format_prd_card_item(item, "🎁") for item in category_map["task"]
            )
        elif plan.tasks:
            card_items.extend(f"🎁 {task}" for task in plan.tasks[:3])

        # 3. Reminders (time-sensitive)
        if category_map["reminder"]:
            card_items.extend(
                _format_prd_card_item(item, "⚠️") for item in category_map["reminder"]
            )
        elif plan.reminders:
            card_items.extend(f"⚠️ {reminder}" for reminder in plan.reminders[:2])

        # 4. Other suggestions
        card_items.extend(
            _format_prd_card_item(item, "💡") for item in category_map["suggestion"][:2]
        )

        if not card_items:
            return ""

        # Build card (max 5 items)
        trip_type = getattr(plan, "trip_type", None) or "出差"
        separator = "───────────────────────"

        parts = [
            f"📍 **{plan.destination}{trip_type} · 智能建议**",
            separator,
            *card_items[:5],
            separator,
        ]

        if plan.summary:
            truncated_summary = (
                plan.summary[:60] + ("..." if len(plan.summary) > 60 else "")
            )
            parts.append(f"💡 {truncated_summary}")

        return "\n".join(parts)


def _format_prd_card_item(item: TripPlanItem, icon: str) -> str:
    """
    格式化单个卡片项（PRD 4.2 样式）

    示例输出:
    - 👤 李思远（5年未见），建议周二晚约
    - 🎁 之前提过给孩子买北京特色绘本
    - ⚠️ 周二岳父生日，建议今天寄出礼物
    """
    text_parts: List[str] = []

    # Add person name if present
    if item.person:
        text_parts.append(item.person)

    # Add time hint or title
    if item.time_hint:
        suffix = (
            f"，{item.time_hint}"
            if item.time_hint != item.title and not item.person
            else item.time_hint
        )
        if item.person:
            text_parts.append(suffix)
        else:
            combined = item.title + (
                f"，{item.time_hint}" if item.time_hint != item.title else ""
            )
            text_parts.append(combined)
    elif item.title and (not item.person or item.title != item.person):
        text_parts.append(item.title)

    content = "".join(text_parts)
    if len(content) > 35:
        content = content[:32] + "..."

    return f"{icon} {content}"


def _format_plan_item(item: TripPlanItem) -> str:
    """Format a single plan item with appropriate icon (legacy method)"""
    icon_map = {
        "meeting": "👤",
        "task": "🎁",
        "reminder": "⚠️",
        "suggestion": "💡",
    }
    icon = icon_map.get(item.category, "•")

    # Build item text
    text_parts = [item.title]
    if item.time_hint:
        text_parts.append(f"，{item.time_hint}")

    return f"{icon} {''.join(text_parts)}"
