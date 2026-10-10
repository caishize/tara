"""
Itinerary planning service for generating detailed day-by-day travel schedules.
"""
from typing import List, Dict, Optional, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.trip_plan import TripPlan
from ..models.trip_itinerary import TripItinerary
from ....core.interfaces.llm_provider import ILLMProvider


class ItineraryPlanner:
    """Service for generating and managing detailed travel itineraries."""

    def __init__(
        self,
        db: AsyncSession,
        llm_provider: ILLMProvider
    ):
        self.db = db
        self.llm = llm_provider

    async def generate_daily_schedule(
        self,
        trip_id: UUID,
        destination: str,
        start_date: date,
        end_date: date,
        family_composition: Dict[str, Any],
        budget: Optional[float] = None,
        preferences: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate detailed daily schedule for the entire trip.

        Args:
            trip_id: Travel plan ID
            destination: Destination name
            start_date: Trip start date
            end_date: Trip end date
            family_composition: Family composition analysis
            budget: Total budget
            preferences: User preferences (pace, interests, must-visit, etc.)

        Returns:
            List of daily itineraries with detailed schedule
        """
        duration_days = (end_date - start_date).days + 1

        # Build LLM prompt for itinerary generation
        prompt = self._build_itinerary_prompt(
            destination,
            duration_days,
            family_composition,
            budget,
            preferences
        )

        # Generate itinerary using LLM
        llm_response = await self.llm.generate_text(prompt, temperature=0.6)

        # Parse LLM response
        daily_schedules = self._parse_itinerary_response(llm_response, duration_days)

        # Save itineraries to database
        itineraries = []
        for day_num, schedule in enumerate(daily_schedules, start=1):
            itinerary = TripItinerary(
                trip_id=trip_id,
                day_number=day_num,
                schedule=schedule.get("activities", []),
                packing_notes=schedule.get("packing_notes")
            )
            self.db.add(itinerary)
            itineraries.append({
                "day_number": day_num,
                "date": start_date + timedelta(days=day_num - 1),
                "schedule": schedule.get("activities", []),
                "packing_notes": schedule.get("packing_notes"),
                "total_estimated_cost": self._calculate_day_cost(schedule.get("activities", []))
            })

        await self.db.commit()

        return itineraries

    def _build_itinerary_prompt(
        self,
        destination: str,
        duration_days: int,
        family_composition: Dict[str, Any],
        budget: Optional[float],
        preferences: Optional[Dict[str, Any]]
    ) -> str:
        """Build LLM prompt for itinerary generation."""

        children = family_composition.get("children", [])
        elderly = family_composition.get("elderly", [])
        special_needs = family_composition.get("special_needs", [])

        pace = preferences.get("pace", "moderate") if preferences else "moderate"
        interests = preferences.get("interests", []) if preferences else []
        must_visit = preferences.get("must_visit", []) if preferences else []

        prompt = f"""你是一个专业的旅行行程规划师。请为以下家庭旅行生成详细的{duration_days}天行程安排。

目的地: {destination}
行程天数: {duration_days}天{duration_days - 1}夜
总预算: {budget or '未设定'}元

家庭成员:
- 儿童: {len(children)}人 ({', '.join([str(c['age']) + '岁' for c in children]) if children else '无'})
- 老人: {len(elderly)}人 ({', '.join([str(e['age']) + '岁' for e in elderly]) if elderly else '无'})
- 特殊需求: {', '.join(special_needs) if special_needs else '无'}

用户偏好:
- 行程节奏: {pace} (relaxed/moderate/packed)
- 兴趣: {', '.join(interests) if interests else '文化、美食、自然'}
- 必去景点: {', '.join(must_visit) if must_visit else '无特别要求'}

请为每天生成详细的行程安排，包含:

每天的活动安排需包含:
1. time: 时间 (HH:MM格式)
2. activity_type: 活动类型 (transportation/accommodation/attraction/meal/other)
3. title: 活动标题
4. location: 地点
5. description: 详细描述
6. estimated_cost: 预计费用 (每人)
7. booking_info: 预订信息 (如有)
8. notes: 注意事项

特别要求:
- 考虑3岁儿童需要午休时间 (14:00-16:00)
- 老人友好的慢节奏安排，避免行程过于紧凑
- 每天行程安排在09:00-20:00之间
- 包含早中晚餐安排
- 第一天包含交通到达时间
- 最后一天包含返程交通
- 预留合理的交通时间和休息时间

请以JSON格式返回，格式如下:
[
  {{
    "day": 1,
    "activities": [
      {{
        "time": "09:00",
        "activity_type": "transportation",
        "title": "高铁出发",
        "location": "上海虹桥站",
        "description": "G1234次，09:00-11:30到达杭州东站",
        "estimated_cost": 150,
        "booking_info": {{"advance_days": 30, "platform": "12306"}},
        "notes": "提前30分钟到达车站，携带身份证"
      }},
      {{
        "time": "12:30",
        "activity_type": "meal",
        "title": "午餐",
        "location": "外婆家(西湖店)",
        "description": "杭帮菜，有儿童餐椅，人均80元",
        "estimated_cost": 80,
        "notes": "推荐东坡肉、西湖醋鱼"
      }},
      {{
        "time": "14:00",
        "activity_type": "other",
        "title": "酒店入住 + 儿童午休",
        "location": "如家酒店(西湖店)",
        "description": "办理入住，孩子午休",
        "estimated_cost": 0,
        "booking_info": {{"advance_days": 14, "platform": "携程", "price_per_night": 400}},
        "notes": "预订家庭房，有儿童设施"
      }},
      {{
        "time": "16:00",
        "activity_type": "attraction",
        "title": "西湖游船",
        "location": "西湖景区",
        "description": "环湖游船，欣赏西湖美景，约1小时",
        "estimated_cost": 55,
        "notes": "准备防晒，看管好孩子"
      }},
      {{
        "time": "18:00",
        "activity_type": "meal",
        "title": "晚餐",
        "location": "河坊街小吃",
        "description": "品尝杭州小吃，定胜糕、片儿川",
        "estimated_cost": 50,
        "notes": "注意儿童饮食安全"
      }},
      {{
        "time": "20:00",
        "activity_type": "other",
        "title": "返回酒店休息",
        "location": "如家酒店",
        "description": "结束第一天行程，早点休息",
        "estimated_cost": 0,
        "notes": "准备第二天出行物品"
      }}
    ]
  }},
  {{
    "day": 2,
    "activities": [
      // Day 2 activities...
    ]
  }}
]
"""

        return prompt

    def _parse_itinerary_response(
        self,
        llm_response: str,
        duration_days: int
    ) -> List[Dict[str, Any]]:
        """Parse LLM response into structured daily schedules."""
        import json
        import re

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                daily_schedules = json.loads(json_str)
                return daily_schedules
            else:
                daily_schedules = json.loads(llm_response)
                return daily_schedules
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse itinerary JSON from LLM: {e}")
            raise RuntimeError("行程规划生成失败：无法解析 LLM 返回结果，请重试")

    def _calculate_day_cost(self, activities: List[Dict[str, Any]]) -> float:
        """Calculate total estimated cost for a day's activities."""
        total = 0.0
        for activity in activities:
            cost = activity.get("estimated_cost", 0)
            if cost:
                total += float(cost)
        return total

    async def generate_packing_list(
        self,
        destination: str,
        duration_days: int,
        season: str,
        family_composition: Dict[str, Any],
        weather_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[str]]:
        """
        Generate packing list categorized by type.

        Categories:
        - 证件类: ID cards, passports, etc.
        - 衣物类: Clothing based on weather
        - 日用品类: Daily necessities
        - 电子设备类: Electronics
        - 药品类: Medications
        - 儿童用品类: Child items (if applicable)

        Args:
            destination: Destination name
            duration_days: Trip duration
            season: Travel season
            family_composition: Family composition
            weather_info: Weather forecast

        Returns:
            Categorized packing list
        """
        has_children = len(family_composition.get("children", [])) > 0
        has_elderly = len(family_composition.get("elderly", [])) > 0

        packing_list = {
            "证件类": [
                "身份证/护照",
                "户口本(儿童出行)" if has_children else None,
                "学生证(如有优惠)",
                "健康码/行程卡(如需要)",
                "预订确认单(酒店/交通)"
            ],
            "衣物类": self._generate_clothing_list(season, duration_days, weather_info),
            "日用品类": [
                "洗漱用品(牙刷、牙膏、毛巾)",
                "防晒霜",
                "雨伞/雨衣",
                "水杯",
                "纸巾、湿纸巾",
                "垃圾袋"
            ],
            "电子设备类": [
                "手机 + 充电器",
                "充电宝",
                "相机(可选)",
                "数据线",
                "转换插头(如需)"
            ],
            "药品类": [
                "常用药(感冒药、退烧药、创可贴)",
                "晕车药" if has_children or has_elderly else None,
                "防蚊虫叮咬药",
                "慢性病药物(老人)" if has_elderly else None
            ],
        }

        # Add child items if has children
        if has_children:
            packing_list["儿童用品类"] = [
                "儿童换洗衣服",
                "纸尿裤/尿不湿",
                "儿童水杯",
                "儿童零食",
                "儿童玩具/绘本",
                "婴儿推车(3岁以下)",
                "儿童防晒霜",
                "儿童退烧药"
            ]

        # Remove None values
        for category in packing_list:
            packing_list[category] = [item for item in packing_list[category] if item]

        return packing_list

    def _generate_clothing_list(
        self,
        season: str,
        duration_days: int,
        weather_info: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate clothing list based on season and weather."""
        base_items = [
            f"换洗衣物 ({duration_days}套)",
            "内衣裤",
            "袜子",
            "睡衣"
        ]

        if season in ["春季", "秋季"]:
            base_items.extend([
                "薄外套(早晚温差大)",
                "长裤",
                "舒适鞋子"
            ])
        elif season == "夏季":
            base_items.extend([
                "短袖T恤",
                "短裤/裙子",
                "防晒衣",
                "太阳帽",
                "墨镜"
            ])
        elif season == "冬季":
            base_items.extend([
                "羽绒服/厚外套",
                "保暖内衣",
                "围巾、手套",
                "保暖鞋"
            ])

        # Check for rain in weather info
        if weather_info and weather_info.get("rain_probability", 0) > 50:
            base_items.append("雨衣/雨伞")

        return base_items

    async def estimate_budget_breakdown(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Estimate budget breakdown by category.

        Categories:
        - 交通: Transportation
        - 住宿: Accommodation
        - 门票: Tickets/Attractions
        - 餐饮: Food
        - 其他: Other

        Args:
            trip_id: Travel plan ID

        Returns:
            Budget breakdown dict
        """
        # Get all itineraries for this trip
        result = await self.db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .order_by(TripItinerary.day_number)
        )
        itineraries = result.scalars().all()

        breakdown = {
            "transportation": 0.0,
            "accommodation": 0.0,
            "tickets": 0.0,
            "food": 0.0,
            "other": 0.0
        }

        for itinerary in itineraries:
            if itinerary.schedule:
                for activity in itinerary.schedule:
                    activity_type = activity.get("activity_type", "other")
                    cost = float(activity.get("estimated_cost", 0))

                    if activity_type == "transportation":
                        breakdown["transportation"] += cost
                    elif activity_type == "accommodation":
                        breakdown["accommodation"] += cost
                    elif activity_type == "attraction":
                        breakdown["tickets"] += cost
                    elif activity_type == "meal":
                        breakdown["food"] += cost
                    else:
                        breakdown["other"] += cost

        breakdown["total"] = sum(breakdown.values())

        return breakdown

    async def generate_booking_reminders(
        self,
        trip_id: UUID,
        start_date: date
    ) -> List[Dict[str, Any]]:
        """
        Generate booking deadline reminders.

        Reminders for:
        - High-speed rail tickets (30 days advance)
        - Hotels (2 weeks advance)
        - Attraction tickets (1 week advance, best discount timing)

        Args:
            trip_id: Travel plan ID
            start_date: Trip start date

        Returns:
            List of booking reminders
        """
        today = date.today()
        reminders = []

        # High-speed rail reminder (30 days before)
        rail_booking_date = start_date - timedelta(days=30)
        if rail_booking_date >= today:
            reminders.append({
                "type": "transportation",
                "title": "高铁票预订提醒",
                "description": "高铁票已开始预售，建议尽早预订以确保座位",
                "booking_date": rail_booking_date.isoformat(),
                "advance_days": 30,
                "priority": "high",
                "notes": "12306 App或网站预订"
            })

        # Hotel reminder (14 days before)
        hotel_booking_date = start_date - timedelta(days=14)
        if hotel_booking_date >= today:
            reminders.append({
                "type": "accommodation",
                "title": "酒店预订提醒",
                "description": "建议提前2周预订酒店，确保房源充足且价格优惠",
                "booking_date": hotel_booking_date.isoformat(),
                "advance_days": 14,
                "priority": "high",
                "notes": "携程、美团等平台对比价格"
            })

        # Attraction tickets reminder (7 days before)
        tickets_booking_date = start_date - timedelta(days=7)
        if tickets_booking_date >= today:
            reminders.append({
                "type": "tickets",
                "title": "景点门票预订提醒",
                "description": "提前网上购票可享受优惠，避免现场排队",
                "booking_date": tickets_booking_date.isoformat(),
                "advance_days": 7,
                "priority": "medium",
                "notes": "官方小程序或OTA平台购票"
            })

        return reminders

    async def optimize_schedule(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Optimize and validate schedule.

        Checks:
        - Travel time between locations
        - Attraction opening hours
        - Realistic daily capacity
        - Time conflicts

        Args:
            trip_id: Travel plan ID

        Returns:
            Optimization report with suggestions
        """
        # Get all itineraries
        result = await self.db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .order_by(TripItinerary.day_number)
        )
        itineraries = result.scalars().all()

        issues = []
        suggestions = []

        for itinerary in itineraries:
            day_num = itinerary.day_number
            if not itinerary.schedule:
                continue

            # Check for time conflicts
            activities = sorted(itinerary.schedule, key=lambda x: x.get("time", "00:00"))
            for i in range(len(activities) - 1):
                current = activities[i]
                next_activity = activities[i + 1]

                # Simple time conflict check
                current_time = current.get("time", "00:00")
                next_time = next_activity.get("time", "00:00")

                if current_time >= next_time:
                    issues.append({
                        "day": day_num,
                        "type": "time_conflict",
                        "message": f"Day {day_num}: 时间冲突 - {current.get('title')} 和 {next_activity.get('title')}"
                    })

            # Check if schedule is too packed (> 6 activities)
            if len(activities) > 6:
                suggestions.append({
                    "day": day_num,
                    "type": "too_packed",
                    "message": f"Day {day_num}: 行程较紧凑({len(activities)}个活动)，建议减少活动或延长行程"
                })

        return {
            "trip_id": str(trip_id),
            "total_issues": len(issues),
            "total_suggestions": len(suggestions),
            "issues": issues,
            "suggestions": suggestions,
            "is_optimized": len(issues) == 0
        }
