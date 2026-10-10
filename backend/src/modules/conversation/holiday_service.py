"""Holiday Service for scheduler jobs.

Chinese holiday planning, reminders, and content generation.
Extracted from scheduler_support.py for file-size compliance.
"""
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..date_manager.models import ChineseHolidayPlan, HolidayPlanStatus
from ...core.utils.timezone import local_today

# HOLIDAY_CONFIG is a class attribute on ChineseHolidayPlan
HOLIDAY_CONFIG = ChineseHolidayPlan.HOLIDAY_CONFIG

logger = logging.getLogger(__name__)


class HolidayService:
    """Extended holiday service for scheduler jobs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_upcoming_holidays(self, days: int = 60) -> List[Dict[str, Any]]:
        """Get upcoming Chinese holidays within specified days."""
        today = local_today()
        current_year = today.year
        upcoming = []

        for holiday_type, config in HOLIDAY_CONFIG.items():
            # Get the holiday date for current year
            holiday_date = self._get_holiday_date(holiday_type, current_year)
            if not holiday_date:
                continue

            days_until = (holiday_date - today).days

            # Check current year and next year
            if 0 < days_until <= days:
                upcoming.append({
                    "type": holiday_type,
                    "name": config["name"],
                    "date": holiday_date,
                    "year": current_year,
                    "days_until": days_until,
                })

            # Check next year for holidays that have passed
            if days_until < 0:
                next_year_date = self._get_holiday_date(holiday_type, current_year + 1)
                if next_year_date:
                    next_days_until = (next_year_date - today).days
                    if 0 < next_days_until <= days:
                        upcoming.append({
                            "type": holiday_type,
                            "name": config["name"],
                            "date": next_year_date,
                            "year": current_year + 1,
                            "days_until": next_days_until,
                        })

        return sorted(upcoming, key=lambda x: x["days_until"])

    def _get_holiday_date(self, holiday_type: str, year: int) -> Optional[date]:
        """Get the date of a holiday for a specific year."""
        config = HOLIDAY_CONFIG.get(holiday_type, {})
        calculation = config.get("calculation", "fixed")

        if calculation == "fixed":
            month = config.get("month", 1)
            day = config.get("day", 1)
            return date(year, month, day)

        elif calculation == "lunar":
            # Convert lunar date to solar date using lunarcalendar library
            lunar_month = config.get("lunar_month", 1)
            lunar_day = config.get("lunar_day", 1)
            try:
                import lunarcalendar
                lunar = lunarcalendar.Lunar(year, lunar_month, lunar_day)
                solar = lunar.to_solar()
                return date(solar.year, solar.month, solar.day)
            except Exception:
                return None

        elif calculation == "variable":
            # Handle variable dates (like Qingming)
            if holiday_type == "qingming":
                # Qingming is around April 4-6
                return date(year, 4, 5)

        return None

    async def get_holiday_plan(
        self,
        family_id: UUID,
        holiday_type: str,
        year: int
    ) -> Optional[ChineseHolidayPlan]:
        """Get existing holiday plan."""
        result = await self.db.execute(
            select(ChineseHolidayPlan).where(
                and_(
                    ChineseHolidayPlan.family_id == family_id,
                    ChineseHolidayPlan.holiday_type == holiday_type,
                    ChineseHolidayPlan.holiday_year == year,
                    ChineseHolidayPlan.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()

    async def generate_holiday_plan(
        self,
        family_id: UUID,
        holiday_type: str,
        year: int,
        region: Optional[str] = None
    ) -> Optional[ChineseHolidayPlan]:
        """Generate a holiday preparation plan."""
        config = HOLIDAY_CONFIG.get(holiday_type)
        if not config:
            return None

        holiday_date = self._get_holiday_date(holiday_type, year)
        if not holiday_date:
            return None

        # Generate plan content based on holiday type
        plan_content = await self._generate_holiday_content(
            family_id, holiday_type, config, region
        )

        plan = ChineseHolidayPlan(
            family_id=family_id,
            holiday_type=holiday_type,
            holiday_name=config["name"],
            holiday_year=year,
            holiday_date=holiday_date,
            plan_content=plan_content,
            status=HolidayPlanStatus.DRAFT,
            region=region,
        )

        self.db.add(plan)
        await self.db.flush()
        return plan

    async def _generate_holiday_content(
        self,
        family_id: UUID,
        holiday_type: str,
        config: dict,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate holiday plan content."""
        content: Dict[str, Any] = {}

        # Get family members for red envelope planning
        from ..member.models import Member

        result = await self.db.execute(
            select(Member).where(
                and_(
                    Member.family_id == family_id,
                    Member.is_deleted == False
                )
            )
        )
        members = result.scalars().all()

        # Generate red envelope list for Spring Festival
        if holiday_type in ["spring_festival", "mid_autumn"]:
            red_envelopes = []
            for member in members:
                relationship = (member.tags[0] if member.tags else None) or "亲属"
                suggested_amount = self._get_suggested_red_envelope(relationship)
                if suggested_amount > 0:
                    red_envelopes.append({
                        "recipient": member.nickname or member.name,
                        "relationship": relationship,
                        "suggested_amount": suggested_amount,
                    })

            content["red_envelopes"] = {
                "items": red_envelopes,
                "total": sum(r["suggested_amount"] for r in red_envelopes),
            }

        # Generate shopping list
        shopping_categories = config.get("shopping_categories", [])
        if shopping_categories:
            content["shopping_list"] = {
                "categories": [
                    {
                        "name": cat,
                        "budget": self._get_category_budget(cat),
                        "items": self._get_category_items(cat, holiday_type),
                    }
                    for cat in shopping_categories
                ],
                "total_budget": sum(
                    self._get_category_budget(cat) for cat in shopping_categories
                ),
            }

        # Generate visit schedule for Spring Festival
        if holiday_type == "spring_festival":
            content["visit_schedule"] = [
                {"date": "除夕", "description": "与家人团聚年夜饭", "priority": "high"},
                {"date": "初一", "description": "拜年、发红包", "priority": "high"},
                {"date": "初二", "description": "回娘家", "priority": "medium"},
                {"date": "初三至初六", "description": "走亲访友", "priority": "medium"},
            ]

        # Generate dinner menu suggestions
        if holiday_type in ["spring_festival", "mid_autumn", "reunion_dinner"]:
            content["dinner_menu"] = {
                "dishes": self._get_menu_suggestions(holiday_type),
            }

        return content

    def _get_suggested_red_envelope(self, relationship: str) -> int:
        """Get suggested red envelope amount based on relationship."""
        amounts = {
            "父母": 2000,
            "公婆": 2000,
            "岳父母": 2000,
            "祖父母": 1000,
            "外祖父母": 1000,
            "兄弟姐妹": 500,
            "侄子侄女": 200,
            "外甥外甥女": 200,
            "表兄弟姐妹": 200,
            "堂兄弟姐妹": 200,
            "子女": 500,
            "配偶": 520,
        }
        return amounts.get(relationship, 100)

    def _get_category_budget(self, category: str) -> int:
        """Get budget for shopping category."""
        budgets = {
            "年货": 1000,
            "礼品": 800,
            "装饰": 200,
            "食材": 600,
            "服装": 500,
            "月饼": 300,
            "水果": 200,
        }
        return budgets.get(category, 300)

    def _get_category_items(self, category: str, holiday_type: str) -> List[Dict]:
        """Get shopping items for category."""
        items_map = {
            "年货": [
                {"name": "糖果", "quantity": "2kg", "estimated_price": 80},
                {"name": "坚果", "quantity": "1kg", "estimated_price": 120},
                {"name": "饮料", "quantity": "2箱", "estimated_price": 100},
            ],
            "礼品": [
                {"name": "茶叶", "quantity": "2盒", "estimated_price": 300},
                {"name": "保健品", "quantity": "1盒", "estimated_price": 400},
            ],
            "月饼": [
                {"name": "月饼礼盒", "quantity": "2盒", "estimated_price": 200},
            ],
            "食材": [
                {"name": "鸡", "quantity": "1只", "estimated_price": 80},
                {"name": "鱼", "quantity": "1条", "estimated_price": 60},
                {"name": "猪肉", "quantity": "2kg", "estimated_price": 100},
            ],
        }
        return items_map.get(category, [])

    def _get_menu_suggestions(self, holiday_type: str) -> List[Dict]:
        """Get menu suggestions for holiday."""
        if holiday_type == "spring_festival":
            return [
                {"name": "红烧鱼", "significance": "年年有余"},
                {"name": "红烧肉", "significance": "富足红火"},
                {"name": "饺子", "significance": "招财进宝"},
                {"name": "年糕", "significance": "年年高升"},
                {"name": "春卷", "significance": "黄金万两"},
            ]
        elif holiday_type == "mid_autumn":
            return [
                {"name": "螃蟹", "significance": "秋季美味"},
                {"name": "桂花糕", "significance": "金桂飘香"},
                {"name": "芋头", "significance": "阖家团圆"},
            ]
        return []

    async def send_holiday_reminder(
        self,
        plan: ChineseHolidayPlan,
        reminder_type: str
    ) -> bool:
        """Send a holiday preparation reminder."""
        from ...core.push.notification_provider import app_notification_provider

        messages = {
            "planning": f"{plan.holiday_name}还有一个月，是时候开始规划了！",
            "shopping": f"{plan.holiday_name}还有两周，别忘了采购年货！",
            "preparation": f"{plan.holiday_name}还有一周，最后准备阶段！",
            "final": f"{plan.holiday_name}就在眼前，确认一切准备就绪！",
        }

        message = messages.get(reminder_type, f"{plan.holiday_name}准备提醒")

        await app_notification_provider.send_notification(
            family_id=str(plan.family_id),
            title=f"{plan.holiday_name}准备提醒",
            body=message,
            data={
                "plan_id": str(plan.id),
                "holiday_type": plan.holiday_type,
                "reminder_type": reminder_type,
            }
        )

        return True
