"""
Travel assistant service for pre-trip, in-trip, and post-trip services.
"""
import logging
from typing import List, Dict, Optional, Any
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.trip_plan import TripPlan
from ..models.trip_itinerary import TripItinerary
from ..models.trip_expense import TripExpense
from ....core.interfaces.llm_provider import ILLMProvider
from ....core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class TripAssistant:
    """Service for providing travel assistance throughout the journey."""

    def __init__(
        self,
        db: AsyncSession,
        llm_provider: ILLMProvider
    ):
        self.db = db
        self.llm = llm_provider

    async def send_pretrip_reminder(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Send pre-trip reminder 24h before departure.

        Includes:
        - Weather forecast
        - Packing list check
        - Important reminders

        Args:
            trip_id: Travel plan ID

        Returns:
            Reminder message dict
        """
        # Get trip details
        result = await self.db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = result.scalar_one_or_none()

        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        # Get weather info (mock for now)
        weather = await self._get_weather_forecast(trip.destination)

        # Build reminder message
        reminder = {
            "trip_id": str(trip_id),
            "type": "pretrip_reminder",
            "title": f"明天出发去{trip.destination}",
            "message": self._build_pretrip_message(trip, weather),
            "weather": weather,
            "checklist": [
                "检查证件(身份证、户口本)",
                "检查打包清单",
                "充电器、充电宝",
                "常用药品",
                "确认交通票务",
                "确认酒店预订"
            ],
            "send_at": utc_now(),
            "priority": "high"
        }

        return reminder

    def _build_pretrip_message(
        self,
        trip: TripPlan,
        weather: Dict[str, Any]
    ) -> str:
        """Build pre-trip reminder message."""
        weather_desc = weather.get("description", "天气未知")
        temp_range = weather.get("temperature_range", "")

        message = f"""明天就要出发去{trip.destination}啦!

天气预报: {weather_desc}, {temp_range}
{weather.get('rain_warning', '')}

请检查:
✓ 证件是否齐全
✓ 行李是否打包完毕
✓ 充电器、充电宝
✓ 常用药品(特别是儿童退烧药、晕车药)
✓ 交通票务确认
✓ 酒店预订确认

祝您旅途愉快!"""

        return message

    async def calculate_departure_time(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Calculate departure time on travel day.

        Considers:
        - Travel duration to station/airport
        - 30min safety buffer
        - Check-in time requirements

        Args:
            trip_id: Travel plan ID

        Returns:
            Departure time calculation
        """
        # Get trip and first day itinerary
        result = await self.db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = result.scalar_one_or_none()

        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        # Get first day itinerary
        itinerary_result = await self.db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .where(TripItinerary.day_number == 1)
        )
        first_day = itinerary_result.scalar_one_or_none()

        if not first_day or not first_day.schedule:
            return {
                "trip_id": str(trip_id),
                "error": "No departure schedule found"
            }

        # Find first transportation activity
        first_transport = None
        for activity in first_day.schedule:
            if activity.get("activity_type") == "transportation":
                first_transport = activity
                break

        if not first_transport:
            return {
                "trip_id": str(trip_id),
                "error": "No transportation found in schedule"
            }

        # Parse departure time
        departure_time_str = first_transport.get("time", "09:00")
        departure_hour, departure_min = map(int, departure_time_str.split(":"))

        # Calculate recommended leave time
        # Assume 60min travel to station + 30min buffer
        travel_duration_min = 60
        buffer_min = 30
        total_advance_min = travel_duration_min + buffer_min

        leave_hour = departure_hour - (total_advance_min // 60)
        leave_min = departure_min - (total_advance_min % 60)

        if leave_min < 0:
            leave_min += 60
            leave_hour -= 1

        recommended_leave_time = f"{leave_hour:02d}:{leave_min:02d}"

        return {
            "trip_id": str(trip_id),
            "departure_time": departure_time_str,
            "departure_location": first_transport.get("location", ""),
            "recommended_leave_time": recommended_leave_time,
            "travel_duration_min": travel_duration_min,
            "buffer_min": buffer_min,
            "notes": first_transport.get("notes", ""),
            "message": f"今天{departure_time_str}出发，建议{recommended_leave_time}出门，路上需要{travel_duration_min}分钟。"
        }

    async def send_departure_reminder(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Send departure reminder on travel day morning.

        Args:
            trip_id: Travel plan ID

        Returns:
            Reminder message dict
        """
        departure_info = await self.calculate_departure_time(trip_id)

        if "error" in departure_info:
            return departure_info

        reminder = {
            "trip_id": str(trip_id),
            "type": "departure_reminder",
            "title": "今天出发",
            "message": departure_info.get("message", ""),
            "departure_time": departure_info.get("departure_time"),
            "recommended_leave_time": departure_info.get("recommended_leave_time"),
            "checklist": [
                "最后检查证件",
                "关闭家中电源、水阀、煤气",
                "携带钥匙",
                "确认行李"
            ],
            "send_at": utc_now(),
            "priority": "high"
        }

        return reminder

    async def send_daily_itinerary_summary(
        self,
        trip_id: UUID,
        day_number: int
    ) -> Dict[str, Any]:
        """
        Send daily itinerary summary each morning.

        Args:
            trip_id: Travel plan ID
            day_number: Day number (1-indexed)

        Returns:
            Daily summary dict
        """
        # Get trip
        trip_result = await self.db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = trip_result.scalar_one_or_none()

        # Get day's itinerary
        itinerary_result = await self.db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .where(TripItinerary.day_number == day_number)
        )
        itinerary = itinerary_result.scalar_one_or_none()

        if not itinerary:
            return {
                "trip_id": str(trip_id),
                "error": f"No itinerary found for day {day_number}"
            }

        # Get weather
        weather = await self._get_weather_forecast(trip.destination)

        # Extract main activities
        main_activities = []
        if itinerary.schedule:
            for activity in itinerary.schedule:
                if activity.get("activity_type") in ["attraction", "transportation"]:
                    main_activities.append(activity.get("title", ""))

        summary = {
            "trip_id": str(trip_id),
            "day_number": day_number,
            "type": "daily_summary",
            "title": f"Day {day_number} 行程提醒",
            "message": f"""今天是{trip.destination}之行的第{day_number}天

天气: {weather.get('description', '晴朗')}

今日主要活动:
{''.join([f'• {activity}' for activity in main_activities[:3]])}

祝您玩得开心!""",
            "weather": weather,
            "activities": itinerary.schedule,
            "send_at": utc_now(),
            "priority": "medium"
        }

        return summary

    async def recommend_nearby_restaurants(
        self,
        location: str,
        meal_type: str = "lunch",
        preferences: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recommend nearby restaurants based on location.

        Uses location service plugin (Google Places, Baidu Maps, etc.)

        Args:
            location: Current location
            meal_type: Meal type (breakfast/lunch/dinner)
            preferences: User preferences (cuisine, price, child-friendly, etc.)

        Returns:
            List of restaurant recommendations
        """
        # TODO: Integrate with ILocationService plugin (Google Places, Baidu Maps, etc.)
        raise NotImplementedError(
            "餐厅推荐功能尚未接入真实数据源（需集成地图/点评 API），暂时不可用"
        )

    async def quick_expense_logging(
        self,
        trip_id: UUID,
        user_input: str,
        expense_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Quick expense logging from conversational input.

        Parses input like:
        - "刚花了120元吃饭"
        - "买门票80元"
        - "打车花了50"

        Args:
            trip_id: Travel plan ID
            user_input: User's natural language input
            expense_date: Expense date (defaults to today)

        Returns:
            Created expense record
        """
        # Parse expense from user input using LLM
        parsed = await self._parse_expense_input(user_input)

        # Get trip
        trip_result = await self.db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = trip_result.scalar_one_or_none()

        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        # Create expense record
        expense = TripExpense(
            trip_id=trip_id,
            expense_date=expense_date or date.today(),
            category=parsed.get("category", "other"),
            amount=parsed.get("amount", 0),
            description=parsed.get("description", user_input),
            location=parsed.get("location")
        )

        self.db.add(expense)

        # Update trip actual expense
        trip.actual_expense += expense.amount

        await self.db.commit()
        await self.db.refresh(expense)

        # Calculate budget status
        budget_status = ""
        if trip.budget:
            remaining = float(trip.remaining_budget or 0)
            used_pct = float(trip.budget_used_percentage or 0)
            budget_status = f"本次旅行已花费{float(trip.actual_expense)}元，剩余{remaining}元({100 - used_pct:.1f}%)"

        return {
            "expense_id": str(expense.expense_id),
            "trip_id": str(trip_id),
            "amount": float(expense.amount),
            "category": expense.category,
            "description": expense.description,
            "budget_status": budget_status,
            "message": f"已记录{expense.category}支出{float(expense.amount)}元。{budget_status}"
        }

    async def _parse_expense_input(self, user_input: str) -> Dict[str, Any]:
        """Parse expense information from natural language input."""
        import re

        # Simple regex-based parsing
        # Look for amount
        amount_match = re.search(r'(\d+(?:\.\d+)?)元?', user_input)
        amount = float(amount_match.group(1)) if amount_match else 0

        # Categorize based on keywords
        category = "other"
        if any(word in user_input for word in ["吃", "饭", "餐", "午餐", "晚餐", "早餐"]):
            category = "food"
        elif any(word in user_input for word in ["票", "门票", "景点"]):
            category = "tickets"
        elif any(word in user_input for word in ["车", "打车", "出租", "地铁", "公交", "高铁", "飞机"]):
            category = "transportation"
        elif any(word in user_input for word in ["酒店", "住宿", "宾馆"]):
            category = "accommodation"
        elif any(word in user_input for word in ["买", "购", "商店"]):
            category = "shopping"

        return {
            "amount": amount,
            "category": category,
            "description": user_input
        }

    async def send_activity_reminders(
        self,
        trip_id: UUID,
        day_number: int,
        activity_index: int,
        advance_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Send reminder for upcoming activity.

        Args:
            trip_id: Travel plan ID
            day_number: Day number
            activity_index: Activity index in schedule
            advance_minutes: Minutes before activity to send reminder

        Returns:
            Reminder message dict
        """
        # Get itinerary
        itinerary_result = await self.db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .where(TripItinerary.day_number == day_number)
        )
        itinerary = itinerary_result.scalar_one_or_none()

        if not itinerary or not itinerary.schedule:
            return {
                "trip_id": str(trip_id),
                "error": "No itinerary found"
            }

        if activity_index >= len(itinerary.schedule):
            return {
                "trip_id": str(trip_id),
                "error": "Activity index out of range"
            }

        activity = itinerary.schedule[activity_index]

        reminder = {
            "trip_id": str(trip_id),
            "day_number": day_number,
            "type": "activity_reminder",
            "title": f"{advance_minutes}分钟后: {activity.get('title', '')}",
            "message": f"""{advance_minutes}分钟后{activity.get('title', '')}

地点: {activity.get('location', '')}
{activity.get('notes', '')}

请准备出发!""",
            "activity": activity,
            "advance_minutes": advance_minutes,
            "send_at": utc_now(),
            "priority": "medium"
        }

        return reminder

    async def collect_post_trip_feedback(
        self,
        trip_id: UUID
    ) -> Dict[str, Any]:
        """
        Collect post-trip feedback.

        Asks for:
        - Rating (1-5 stars)
        - Satisfaction
        - Suggestions

        Args:
            trip_id: Travel plan ID

        Returns:
            Feedback collection request
        """
        # Get trip
        trip_result = await self.db.execute(
            select(TripPlan).where(TripPlan.trip_id == trip_id)
        )
        trip = trip_result.scalar_one_or_none()

        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        feedback_request = {
            "trip_id": str(trip_id),
            "type": "post_trip_feedback",
            "title": f"{trip.destination}之行结束了",
            "message": f"""感谢选择我们的旅行规划服务!

您的{trip.destination}之行已经结束，希望您玩得开心!

请为这次旅行打分并分享您的感受:
1. 整体满意度 (1-5星)
2. 行程安排合理性
3. 预算估算准确性
4. 您的建议和意见

您的反馈将帮助我们优化服务，为您提供更好的旅行规划!""",
            "questions": [
                {
                    "id": "overall_rating",
                    "type": "rating",
                    "question": "整体满意度",
                    "scale": 5
                },
                {
                    "id": "itinerary_reasonable",
                    "type": "rating",
                    "question": "行程安排合理性",
                    "scale": 5
                },
                {
                    "id": "budget_accurate",
                    "type": "rating",
                    "question": "预算估算准确性",
                    "scale": 5
                },
                {
                    "id": "suggestions",
                    "type": "text",
                    "question": "您的建议和意见"
                }
            ],
            "send_at": utc_now(),
            "priority": "low"
        }

        return feedback_request

    async def _get_weather_forecast(
        self,
        location: str,
        days: int = 3
    ) -> Dict[str, Any]:
        """
        Get weather forecast for location using Open-Meteo API.

        Args:
            location: Location name
            days: Number of days forecast

        Returns:
            Weather forecast dict
        """
        from .weather_service import WeatherService

        today = date.today()
        end = today + timedelta(days=days - 1)

        try:
            weather_svc = WeatherService()
            forecast = await weather_svc.get_forecast(
                destination=location,
                start_date=today,
                end_date=end,
            )
            if forecast.daily_forecasts:
                first = forecast.daily_forecasts[0]
                summary = forecast.get_overall_summary()
                rain_warning = ""
                if first.needs_rain_gear:
                    rain_warning = "注意：预计有雨，请携带雨具"
                return {
                    "location": location,
                    "description": first.description,
                    "temperature_range": f"{first.temp_low}-{first.temp_high}°C",
                    "rain_probability": first.precipitation_prob,
                    "rain_warning": rain_warning,
                    "wind": f"风速 {first.wind_speed} km/h",
                    "air_quality": "",
                    "uv_index": str(first.uv_index),
                    "suggestions": summary.get("packing_suggestions", []),
                }
            raise ValueError("No forecast data returned")
        except Exception as e:
            logger.warning("Weather forecast unavailable for %s: %s", location, e)
            return {
                "location": location,
                "description": "天气数据暂时不可用",
                "temperature_range": "",
                "rain_probability": 0,
                "rain_warning": "",
                "wind": "",
                "air_quality": "",
                "uv_index": "",
                "suggestions": [],
            }
