"""
Holiday Service - Chinese traditional holiday planning assistant

Provides comprehensive planning for Chinese holidays:
- Spring Festival (春节)
- Mid-Autumn Festival (中秋节)
- Dragon Boat Festival (端午节)
- Qingming Festival (清明节)
- Other traditional holidays
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ....core.utils.timezone import local_today
from ...date_manager.holiday_repository import HolidayRepository
from ...date_manager.models import ChineseHolidayPlan


class HolidayService:
    """节日准备服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.holiday_repo = HolidayRepository(db)

    async def generate_holiday_plan(
        self,
        family_id: UUID,
        holiday_type: str,
        year: Optional[int] = None,
        region: Optional[str] = None,
    ) -> ChineseHolidayPlan:
        """生成节日准备方案"""
        if not year:
            year = local_today().year
            # 如果节日已过，规划下一年
            holiday_date = self._calculate_holiday_date(holiday_type, year)
            if holiday_date and holiday_date < local_today():
                year += 1

        holiday_date = self._calculate_holiday_date(holiday_type, year)
        if not holiday_date:
            holiday_date = date(year, 1, 1)  # 默认日期

        # 检查是否已有该年的方案
        existing = await self.holiday_repo.get_plan_by_holiday(family_id, holiday_type, year)
        if existing:
            return existing

        # 获取家庭成员信息用于规划
        family_members = await self._get_family_members(family_id)

        # 生成方案内容
        plan_content = await self._generate_plan_content(
            holiday_type=holiday_type,
            family_members=family_members,
            region=region,
        )

        # 创建方案
        plan = await self.holiday_repo.create_plan(
            family_id=family_id,
            holiday_type=holiday_type,
            holiday_year=year,
            holiday_date=holiday_date,
            plan_content=plan_content,
            region=region,
        )

        return plan

    def _calculate_holiday_date(
        self,
        holiday_type: str,
        year: int,
    ) -> Optional[date]:
        """计算节日日期"""
        # 农历转公历需要使用农历库，这里简化处理
        # 实际项目中应该使用 lunarcalendar 或 chinese_calendar 库

        # 简化的日期估算（实际应使用精确的农历转换）
        estimated_dates = {
            "spring_festival": date(year, 2, 1),  # 大约在1月下旬到2月中旬
            "lantern_festival": date(year, 2, 15),
            "qingming": date(year, 4, 5),  # 清明通常在4月4-6日
            "dragon_boat": date(year, 6, 10),  # 大约在5月下旬到6月中旬
            "mid_autumn": date(year, 9, 20),  # 大约在9月到10月
            "double_ninth": date(year, 10, 15),
            "winter_solstice": date(year, 12, 22),  # 冬至通常在12月21-23日
            "laba_festival": date(year, 1, 15),  # 腊八在腊月初八
        }

        return estimated_dates.get(holiday_type)

    async def _get_family_members(self, family_id: UUID) -> List[Dict[str, Any]]:
        """获取家庭成员信息"""
        from ...member.models import Member

        result = await self.db.execute(
            select(Member).where(Member.family_id == family_id)
        )
        members = result.scalars().all()

        return [
            {
                "id": str(m.id),
                "name": m.nickname or m.name,
                "relationship": m.tags[0] if m.tags else None,
                "age": self._calculate_age(m.date_of_birth) if m.date_of_birth else None,
            }
            for m in members
        ]

    def _calculate_age(self, birth_date: date) -> int:
        """计算年龄"""
        today = local_today()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age

    async def _generate_plan_content(
        self,
        holiday_type: str,
        family_members: List[Dict[str, Any]],
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成方案内容"""
        if holiday_type == "spring_festival":
            return await self._generate_spring_festival_plan(family_members, region)
        elif holiday_type == "mid_autumn":
            return await self._generate_mid_autumn_plan(family_members, region)
        elif holiday_type == "dragon_boat":
            return await self._generate_dragon_boat_plan(family_members, region)
        elif holiday_type == "qingming":
            return await self._generate_qingming_plan(family_members, region)
        else:
            return self._generate_generic_holiday_plan(holiday_type, family_members)

    async def _generate_spring_festival_plan(
        self,
        family_members: List[Dict[str, Any]],
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成春节准备方案"""
        # 计算红包预算
        red_envelope_items = []
        total_red_envelope = 0

        for member in family_members:
            relationship = member.get("relationship", "")
            age = member.get("age")

            # 根据关系和年龄推荐红包金额
            if relationship in ["grandfather", "grandmother", "father", "mother"]:
                amount = 2000
                reason = "孝敬长辈"
            elif relationship in ["uncle", "aunt"]:
                amount = 500
                reason = "走亲访友"
            elif age and age < 18:
                amount = 200
                reason = "给小朋友的压岁钱"
            else:
                continue

            red_envelope_items.append({
                "recipient": member.get("name", ""),
                "relationship": relationship,
                "suggested_amount": amount,
                "reason": reason,
                "lucky_amounts": self._get_lucky_amounts(amount),
            })
            total_red_envelope += amount

        # 年货清单
        shopping_list = {
            "categories": [
                {
                    "name": "干货坚果",
                    "budget": 500,
                    "items": [
                        {"name": "腰果", "quantity": "2斤", "estimated_price": 80},
                        {"name": "开心果", "quantity": "2斤", "estimated_price": 100},
                        {"name": "瓜子", "quantity": "5斤", "estimated_price": 50},
                        {"name": "核桃", "quantity": "2斤", "estimated_price": 60},
                    ],
                },
                {
                    "name": "糖果零食",
                    "budget": 300,
                    "items": [
                        {"name": "徐福记糖果", "quantity": "2盒", "estimated_price": 80},
                        {"name": "巧克力", "quantity": "2盒", "estimated_price": 100},
                        {"name": "果脯蜜饯", "quantity": "2包", "estimated_price": 50},
                    ],
                },
                {
                    "name": "烟酒礼品",
                    "budget": 1500,
                    "items": [
                        {"name": "白酒", "quantity": "2瓶", "estimated_price": 600},
                        {"name": "红酒", "quantity": "2瓶", "estimated_price": 400},
                        {"name": "香烟", "quantity": "2条", "estimated_price": 500},
                    ],
                },
                {
                    "name": "肉类海鲜",
                    "budget": 800,
                    "items": [
                        {"name": "猪肉", "quantity": "10斤", "estimated_price": 200},
                        {"name": "牛肉", "quantity": "5斤", "estimated_price": 250},
                        {"name": "鸡", "quantity": "2只", "estimated_price": 100},
                        {"name": "鱼", "quantity": "2条", "estimated_price": 150},
                    ],
                },
                {
                    "name": "蔬菜水果",
                    "budget": 400,
                    "items": [
                        {"name": "苹果", "quantity": "1箱", "estimated_price": 80},
                        {"name": "橙子", "quantity": "1箱", "estimated_price": 80},
                        {"name": "蔬菜", "quantity": "若干", "estimated_price": 100},
                    ],
                },
            ],
            "total_budget": 3500,
        }

        # 走亲访友安排
        visit_schedule = [
            {"date": "除夕", "description": "在家团圆吃年夜饭", "priority": "high"},
            {"date": "初一", "description": "在家接待来拜年的亲友", "priority": "high"},
            {"date": "初二", "description": "回娘家（如适用）", "priority": "high"},
            {"date": "初三", "description": "走访亲戚", "priority": "medium"},
            {"date": "初四", "description": "走访朋友", "priority": "medium"},
            {"date": "初五", "description": "迎财神/破五", "priority": "low"},
        ]

        # 年夜饭菜单
        dinner_menu = {
            "dishes": [
                {"name": "红烧鱼", "significance": "年年有余", "difficulty": "medium"},
                {"name": "白切鸡", "significance": "大吉大利", "difficulty": "easy"},
                {"name": "红烧肉", "significance": "红红火火", "difficulty": "medium"},
                {"name": "饺子", "significance": "招财进宝", "difficulty": "hard"},
                {"name": "八宝饭", "significance": "团团圆圆", "difficulty": "medium"},
                {"name": "清蒸虾", "significance": "虾同笑谐音", "difficulty": "easy"},
                {"name": "蔬菜沙拉", "significance": "健康清爽", "difficulty": "easy"},
            ],
            "dietary_restrictions": [],
            "cooking_order": ["红烧肉", "白切鸡", "红烧鱼", "清蒸虾", "八宝饭", "饺子", "蔬菜沙拉"],
        }

        # 大扫除安排
        cleaning_schedule = [
            {"date": "腊月二十三", "task": "厨房油烟清洗", "difficulty": "hard"},
            {"date": "腊月二十四", "task": "扫房子、清洁天花板", "difficulty": "hard"},
            {"date": "腊月二十五", "task": "清洗窗帘、被套", "difficulty": "medium"},
            {"date": "腊月二十六", "task": "整理衣柜、换洗床品", "difficulty": "medium"},
            {"date": "腊月二十七", "task": "清洁家具、地板", "difficulty": "medium"},
            {"date": "腊月二十八", "task": "贴春联、挂灯笼", "difficulty": "easy"},
            {"date": "腊月二十九", "task": "最后整理、准备年夜饭食材", "difficulty": "easy"},
        ]

        return {
            "red_envelopes": {
                "items": red_envelope_items,
                "total": total_red_envelope,
                "suggestions": [
                    "红包金额建议用吉利数字，如88、168、288、666、888",
                    "给长辈的红包金额应该更多",
                    "给小朋友的压岁钱要准备新钞",
                ],
            },
            "shopping_list": shopping_list,
            "visit_schedule": visit_schedule,
            "dinner_menu": dinner_menu,
            "cleaning_schedule": cleaning_schedule,
            "decorations": [
                {"item": "春联", "quantity": 3, "where_to_buy": "超市/网购"},
                {"item": "福字", "quantity": 5, "where_to_buy": "超市/网购"},
                {"item": "灯笼", "quantity": 2, "where_to_buy": "网购"},
                {"item": "中国结", "quantity": 2, "where_to_buy": "超市/网购"},
            ],
            "taboos": [
                "初一不能扫地（会把财气扫走）",
                "初一不能打破东西（如打破要说岁岁平安）",
                "初一不能说不吉利的话",
                "初一不能催人起床",
            ],
        }

    def _get_lucky_amounts(self, base_amount: int) -> List[int]:
        """获取吉利金额选项"""
        lucky_numbers = [66, 88, 99, 168, 188, 288, 366, 388, 520, 666, 888, 999, 1314, 1688, 1888, 2888]
        return [n for n in lucky_numbers if n >= base_amount * 0.5 and n <= base_amount * 1.5]

    async def _generate_mid_autumn_plan(
        self,
        family_members: List[Dict[str, Any]],
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成中秋准备方案"""
        return {
            "mooncake_shopping": {
                "categories": [
                    {"name": "传统广式月饼", "budget": 300, "for": "家庭自用"},
                    {"name": "精品礼盒", "budget": 500, "for": "送礼"},
                    {"name": "冰皮月饼", "budget": 200, "for": "年轻人"},
                ],
                "recommendations": [
                    "提前1-2周购买，避免临近断货",
                    "送礼建议选品牌礼盒",
                    "注意保质期，月饼不宜久放",
                ],
            },
            "gift_preparation": [
                {"recipient": "父母", "suggestions": ["月饼礼盒", "茶叶", "水果"], "budget": 500},
                {"recipient": "领导/客户", "suggestions": ["高端月饼礼盒", "红酒"], "budget": 800},
                {"recipient": "朋友", "suggestions": ["精品月饼", "特产"], "budget": 300},
            ],
            "activities": [
                {"activity": "赏月", "location": "阳台/公园", "time": "晚上8-10点"},
                {"activity": "团圆饭", "location": "家中/餐厅", "time": "晚上6点"},
                {"activity": "灯笼/花灯", "location": "公园/景区", "time": "晚上"},
            ],
            "dinner_menu": {
                "dishes": [
                    {"name": "大闸蟹", "significance": "应季美食"},
                    {"name": "桂花糕", "significance": "中秋应景"},
                    {"name": "芋头", "significance": "团圆"},
                ],
            },
        }

    async def _generate_dragon_boat_plan(
        self,
        family_members: List[Dict[str, Any]],
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成端午准备方案"""
        return {
            "zongzi_preparation": {
                "types": [
                    {"name": "肉粽", "region": "南方", "filling": "五花肉、咸蛋黄"},
                    {"name": "甜粽", "region": "北方", "filling": "红枣、豆沙"},
                    {"name": "碱水粽", "region": "广东", "filling": "碱水"},
                ],
                "ingredients": [
                    {"name": "糯米", "quantity": "5斤", "estimated_price": 30},
                    {"name": "粽叶", "quantity": "2包", "estimated_price": 20},
                    {"name": "五花肉", "quantity": "2斤", "estimated_price": 60},
                    {"name": "咸蛋黄", "quantity": "20个", "estimated_price": 40},
                ],
                "buy_or_make": "建议提前2-3天准备材料，端午前一天包粽子",
            },
            "traditions": [
                {"activity": "挂艾草菖蒲", "purpose": "辟邪驱蚊"},
                {"activity": "佩香囊", "purpose": "辟邪驱虫"},
                {"activity": "喝雄黄酒", "purpose": "杀菌"},
                {"activity": "赛龙舟", "purpose": "纪念屈原"},
            ],
            "gift_suggestions": [
                {"item": "粽子礼盒", "budget": 200, "for": "通用"},
                {"item": "咸鸭蛋礼盒", "budget": 100, "for": "长辈"},
            ],
        }

    async def _generate_qingming_plan(
        self,
        family_members: List[Dict[str, Any]],
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """生成清明准备方案"""
        return {
            "tomb_sweeping": {
                "preparation": [
                    {"item": "鲜花", "purpose": "祭奠", "estimated_price": 100},
                    {"item": "香烛", "purpose": "祭祀", "estimated_price": 50},
                    {"item": "纸钱", "purpose": "祭祀", "estimated_price": 30},
                    {"item": "水果", "purpose": "供品", "estimated_price": 50},
                    {"item": "点心", "purpose": "供品", "estimated_price": 50},
                ],
                "tips": [
                    "建议避开高峰期，可选择提前或延后",
                    "注意防火安全，文明祭扫",
                    "穿着素色服装为宜",
                ],
            },
            "activities": [
                {"activity": "踏青", "description": "清明时节适合外出赏花"},
                {"activity": "放风筝", "description": "传统习俗"},
                {"activity": "吃青团", "description": "清明节传统食品"},
            ],
            "schedule_suggestion": "建议安排在清明节前后一周内完成扫墓",
        }

    def _generate_generic_holiday_plan(
        self,
        holiday_type: str,
        family_members: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """生成通用节日方案"""
        config = ChineseHolidayPlan.HOLIDAY_CONFIG.get(holiday_type, {})

        return {
            "holiday_name": config.get("name", holiday_type),
            "preparation_days": config.get("prepare_days", 7),
            "duration_days": config.get("duration_days", 1),
            "general_tasks": [
                "准备节日食品",
                "打扫房屋",
                "准备礼物（如需要）",
                "安排家庭活动",
            ],
        }

    async def get_red_envelope_budget(
        self,
        family_id: UUID,
        holiday_type: str = "spring_festival",
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取红包预算汇总"""
        if not year:
            year = local_today().year

        plan = await self.holiday_repo.get_plan_by_holiday(family_id, holiday_type, year)
        if not plan:
            return {"items": [], "total": 0}

        return await self.holiday_repo.get_red_envelope_summary(plan.id) or {"items": [], "total": 0}

    async def update_red_envelope(
        self,
        plan_id: UUID,
        recipient: str,
        amount: int,
    ) -> Optional[ChineseHolidayPlan]:
        """更新红包金额"""
        return await self.holiday_repo.update_red_envelope_item(plan_id, recipient, amount)

    async def get_shopping_list(
        self,
        family_id: UUID,
        holiday_type: str = "spring_festival",
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取购物清单"""
        if not year:
            year = local_today().year

        plan = await self.holiday_repo.get_plan_by_holiday(family_id, holiday_type, year)
        if not plan:
            return {"categories": [], "total_budget": 0}

        return await self.holiday_repo.get_shopping_summary(plan.id) or {"categories": [], "total_budget": 0}

    async def get_upcoming_holidays(
        self,
        family_id: UUID,
        days: int = 60,
    ) -> List[ChineseHolidayPlan]:
        """获取即将到来的节日"""
        return await self.holiday_repo.get_upcoming_holidays(family_id, days)

    async def adopt_plan(self, plan_id: UUID) -> Optional[ChineseHolidayPlan]:
        """采纳节日方案"""
        return await self.holiday_repo.adopt_plan(plan_id)
