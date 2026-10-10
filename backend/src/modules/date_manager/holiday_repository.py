"""
Chinese Holiday Repository - Data access for holiday plans.

Canonical location. Old location (assistant/repositories/holiday_repository.py)
re-exports from here.
"""

from datetime import date, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ChineseHolidayPlan
from ...core.utils.timezone import utc_now, local_today


class HolidayRepository:
    """中国传统节日仓库"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_plan(
        self,
        family_id: UUID,
        holiday_type: str,
        holiday_year: int,
        holiday_date: date,
        plan_content: dict,
        region: Optional[str] = None,
    ) -> ChineseHolidayPlan:
        """创建节日准备方案"""
        plan = ChineseHolidayPlan(
            family_id=family_id,
            holiday_type=holiday_type,
            holiday_year=holiday_year,
            holiday_date=holiday_date,
            plan_content=plan_content,
            region=region,
        )
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def get_plan(self, plan_id: UUID) -> Optional[ChineseHolidayPlan]:
        """获取方案"""
        result = await self.db.execute(
            select(ChineseHolidayPlan).where(ChineseHolidayPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def get_plan_by_holiday(
        self,
        family_id: UUID,
        holiday_type: str,
        holiday_year: int,
    ) -> Optional[ChineseHolidayPlan]:
        """根据节日类型和年份获取方案"""
        result = await self.db.execute(
            select(ChineseHolidayPlan).where(
                ChineseHolidayPlan.family_id == family_id,
                ChineseHolidayPlan.holiday_type == holiday_type,
                ChineseHolidayPlan.holiday_year == holiday_year,
            )
        )
        return result.scalar_one_or_none()

    async def get_family_plans(
        self,
        family_id: UUID,
        year: Optional[int] = None,
        status: Optional[str] = None,
    ) -> List[ChineseHolidayPlan]:
        """获取家庭的节日方案列表"""
        query = select(ChineseHolidayPlan).where(
            ChineseHolidayPlan.family_id == family_id
        )
        if year:
            query = query.where(ChineseHolidayPlan.holiday_year == year)
        if status:
            query = query.where(ChineseHolidayPlan.status == status)

        query = query.order_by(ChineseHolidayPlan.holiday_date.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_upcoming_holidays(
        self,
        family_id: UUID,
        days: int = 60,
    ) -> List[ChineseHolidayPlan]:
        """获取即将到来的节日方案"""
        end_date = local_today() + timedelta(days=days)
        result = await self.db.execute(
            select(ChineseHolidayPlan).where(
                ChineseHolidayPlan.family_id == family_id,
                ChineseHolidayPlan.holiday_date >= local_today(),
                ChineseHolidayPlan.holiday_date <= end_date,
            )
            .order_by(ChineseHolidayPlan.holiday_date.asc())
        )
        return list(result.scalars().all())

    async def get_plans_in_preparation(
        self,
        family_id: UUID,
    ) -> List[ChineseHolidayPlan]:
        """获取处于准备阶段的方案"""
        result = await self.db.execute(
            select(ChineseHolidayPlan).where(
                ChineseHolidayPlan.family_id == family_id,
                ChineseHolidayPlan.holiday_date >= local_today(),
                ChineseHolidayPlan.status.in_(["draft", "sent", "adopted", "in_progress"]),
            )
            .order_by(ChineseHolidayPlan.holiday_date.asc())
        )
        plans = list(result.scalars().all())
        return [p for p in plans if p.is_in_preparation_window]

    async def update_plan(
        self,
        plan_id: UUID,
        **kwargs,
    ) -> Optional[ChineseHolidayPlan]:
        """更新方案"""
        kwargs["updated_at"] = utc_now()
        await self.db.execute(
            update(ChineseHolidayPlan)
            .where(ChineseHolidayPlan.id == plan_id)
            .values(**kwargs)
        )
        await self.db.commit()
        return await self.get_plan(plan_id)

    async def adopt_plan(
        self,
        plan_id: UUID,
    ) -> Optional[ChineseHolidayPlan]:
        """采纳方案"""
        return await self.update_plan(
            plan_id,
            status="adopted",
            adopted_at=utc_now(),
        )

    async def update_plan_content(
        self,
        plan_id: UUID,
        plan_content: dict,
    ) -> Optional[ChineseHolidayPlan]:
        """更新方案内容"""
        return await self.update_plan(plan_id, plan_content=plan_content)

    async def mark_in_progress(self, plan_id: UUID) -> Optional[ChineseHolidayPlan]:
        """标记进行中"""
        return await self.update_plan(plan_id, status="in_progress")

    async def mark_completed(self, plan_id: UUID) -> Optional[ChineseHolidayPlan]:
        """标记已完成"""
        return await self.update_plan(plan_id, status="completed")

    async def delete_plan(self, plan_id: UUID) -> bool:
        """删除方案"""
        result = await self.db.execute(
            delete(ChineseHolidayPlan)
            .where(ChineseHolidayPlan.id == plan_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def get_red_envelope_summary(
        self,
        plan_id: UUID,
    ) -> Optional[dict]:
        """获取红包汇总信息"""
        plan = await self.get_plan(plan_id)
        if not plan or "red_envelopes" not in plan.plan_content:
            return None
        return plan.plan_content.get("red_envelopes")

    async def get_shopping_summary(
        self,
        plan_id: UUID,
    ) -> Optional[dict]:
        """获取购物清单汇总"""
        plan = await self.get_plan(plan_id)
        if not plan or "shopping_list" not in plan.plan_content:
            return None
        return plan.plan_content.get("shopping_list")

    async def update_red_envelope_item(
        self,
        plan_id: UUID,
        recipient: str,
        amount: int,
    ) -> Optional[ChineseHolidayPlan]:
        """更新红包项"""
        plan = await self.get_plan(plan_id)
        if not plan:
            return None

        content = plan.plan_content or {}
        red_envelopes = content.get("red_envelopes", {"items": [], "total": 0})

        for item in red_envelopes.get("items", []):
            if item.get("recipient") == recipient:
                item["amount"] = amount
                break

        red_envelopes["total"] = sum(
            item.get("amount", item.get("suggested_amount", 0))
            for item in red_envelopes.get("items", [])
        )

        content["red_envelopes"] = red_envelopes
        return await self.update_plan_content(plan_id, content)
