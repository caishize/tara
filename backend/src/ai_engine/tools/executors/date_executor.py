"""Date domain tool executor — important date management + lunar calendar conversion."""

from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ..shared.errors import ToolErrorType, tool_error
from ..shared.progress import ProgressCallback
from .base import BaseToolExecutor

logger = get_logger(__name__)

# Chinese day names for display
_CHINESE_DAY_NAMES = {
    1: "初一", 2: "初二", 3: "初三", 4: "初四", 5: "初五",
    6: "初六", 7: "初七", 8: "初八", 9: "初九", 10: "初十",
    11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五",
    16: "十六", 17: "十七", 18: "十八", 19: "十九", 20: "二十",
    21: "廿一", 22: "廿二", 23: "廿三", 24: "廿四", 25: "廿五",
    26: "廿六", 27: "廿七", 28: "廿八", 29: "廿九", 30: "三十",
}

_CHINESE_MONTH_NAMES = {
    1: "正月", 2: "二月", 3: "三月", 4: "四月", 5: "五月", 6: "六月",
    7: "七月", 8: "八月", 9: "九月", 10: "十月", 11: "冬月", 12: "腊月",
}


class DateToolExecutor(BaseToolExecutor):
    """Handles add/query/update/delete for important dates."""

    async def add_important_date(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.date_manager.date_repository import ImportantDateRepository
        from ....modules.member.repositories.member_repository import MemberRepository

        repo = ImportantDateRepository(self.db)

        member_id = None
        person = args.get("person")
        if person:
            member_repo = MemberRepository(self.db)
            members = await member_repo.search_by_name(family_id, person)
            if members:
                member_id = members[0].id

        important_date = await repo.create_date(
            family_id=family_id,
            title=args.get("title"),
            date_type=args.get("date_type", "other"),
            month=args.get("month"),
            day=args.get("day"),
            is_lunar=args.get("is_lunar", False),
            member_id=member_id,
            created_by=user_id,
        )

        await self.db.commit()

        return {
            "success": True,
            "date_id": str(important_date.id),
            "title": args.get("title"),
            "date": f"{args.get('month')}月{args.get('day')}日",
            "is_lunar": args.get("is_lunar", False),
        }

    async def query_upcoming_dates(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.date_manager.date_repository import ImportantDateRepository

        repo = ImportantDateRepository(self.db)
        raw_days = args.get("days_ahead", args.get("days", 30))
        try:
            days = int(raw_days)
        except (TypeError, ValueError):
            days = 30
        days = max(1, min(days, 365))
        dates = await repo.get_upcoming_dates(family_id, days=days)
        date_type = args.get("date_type")
        if isinstance(date_type, str) and date_type and date_type != "all":
            dates = [d for d in dates if d.date_type == date_type]

        return {
            "success": True,
            "dates": [
                {
                    "id": str(d.id),
                    "title": d.title,
                    "date": f"{d.lunar_month or d.solar_date.month}月{d.lunar_day or d.solar_date.day}日",
                    "is_lunar": d.is_lunar,
                }
                for d in dates
            ],
            "count": len(dates),
        }

    async def update_important_date(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.date_manager.models import ImportantDate
        from sqlalchemy import select, and_

        title = args.get("title")
        if not title:
            return tool_error(
                ToolErrorType.VALIDATION,
                "缺少必要参数: title",
                hint="请提供要更新的日期标题",
            )

        updates = args.get("updates", {})
        if not updates:
            return tool_error(ToolErrorType.VALIDATION, "缺少更新内容")

        stmt = select(ImportantDate).where(
            and_(
                ImportantDate.family_id == family_id,
                ImportantDate.title == title,
            )
        )
        result = await self.db.execute(stmt)
        important_date = result.scalar_one_or_none()

        if not important_date:
            return tool_error(
                ToolErrorType.NOT_FOUND,
                f"未找到标题为「{title}」的重要日期",
                hint="请确认日期标题是否正确",
            )

        if "new_title" in updates:
            important_date.title = updates["new_title"]
        if "month" in updates:
            important_date.month = updates["month"]
        if "day" in updates:
            important_date.day = updates["day"]
        if "is_lunar" in updates:
            important_date.is_lunar = updates["is_lunar"]
        if "reminder_days" in updates:
            important_date.reminder_days_before = updates["reminder_days"]

        await self.db.commit()

        return {
            "success": True,
            "title": important_date.title,
            "message": f"已更新重要日期: {important_date.title}",
        }

    async def delete_important_date(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        from ....modules.date_manager.models import ImportantDate
        from sqlalchemy import select, and_

        title = args.get("title")
        if not title:
            return tool_error(ToolErrorType.VALIDATION, "缺少必要参数: title")

        stmt = select(ImportantDate).where(
            and_(
                ImportantDate.family_id == family_id,
                ImportantDate.title == title,
            )
        )
        result = await self.db.execute(stmt)
        important_date = result.scalar_one_or_none()

        if not important_date:
            return tool_error(
                ToolErrorType.NOT_FOUND,
                f"未找到标题为「{title}」的重要日期",
            )

        await self.db.delete(important_date)
        await self.db.commit()

        return {
            "success": True,
            "title": title,
            "message": f"已删除重要日期: {title}",
        }

    async def convert_lunar_date(
        self,
        args: Dict[str, Any],
        family_id: UUID,
        user_id: UUID,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Convert between lunar and solar (Gregorian) dates."""
        from ....modules.date_manager.lunar_provider import lunar_calendar_provider

        direction = args.get("direction", "lunar_to_solar")
        year = args.get("year")
        month = args.get("month")
        day = args.get("day")
        is_leap = args.get("is_leap", False)

        if not all([year, month, day]):
            return tool_error(
                ToolErrorType.VALIDATION,
                "缺少必要参数: year, month, day",
                hint="请提供年、月、日",
            )

        try:
            if direction == "lunar_to_solar":
                solar_date = await lunar_calendar_provider.lunar_to_solar(
                    year, month, day, is_leap
                )
                lunar_month_name = _CHINESE_MONTH_NAMES.get(month, f"{month}月")
                lunar_day_name = _CHINESE_DAY_NAMES.get(day, f"{day}日")
                leap_prefix = "闰" if is_leap else ""

                return {
                    "success": True,
                    "direction": "lunar_to_solar",
                    "lunar_date": f"农历{year}年{leap_prefix}{lunar_month_name}{lunar_day_name}",
                    "solar_date": solar_date.isoformat(),
                    "solar_date_display": f"{solar_date.year}年{solar_date.month}月{solar_date.day}日",
                    "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][solar_date.weekday()],
                }
            elif direction == "solar_to_lunar":
                lunar = await lunar_calendar_provider.solar_to_lunar(
                    date(year, month, day)
                )
                lunar_month_name = _CHINESE_MONTH_NAMES.get(lunar.month, f"{lunar.month}月")
                lunar_day_name = _CHINESE_DAY_NAMES.get(lunar.day, f"{lunar.day}日")
                leap_prefix = "闰" if lunar.is_leap else ""

                return {
                    "success": True,
                    "direction": "solar_to_lunar",
                    "solar_date": f"{year}年{month}月{day}日",
                    "lunar_date": f"农历{lunar.year}年{leap_prefix}{lunar_month_name}{lunar_day_name}",
                    "lunar_year": lunar.year,
                    "lunar_month": lunar.month,
                    "lunar_day": lunar.day,
                    "is_leap_month": lunar.is_leap,
                }
            else:
                return tool_error(
                    ToolErrorType.VALIDATION,
                    f"无效的转换方向: {direction}",
                    hint="direction 必须是 'lunar_to_solar' 或 'solar_to_lunar'",
                )
        except Exception as e:
            logger.warning("Lunar calendar conversion failed: %s", e)
            return tool_error(
                ToolErrorType.INTERNAL,
                f"农历转换失败: {e}",
                hint="请检查日期是否有效",
            )
