"""Weather care strategy — caring reminders based on weather conditions."""
from typing import List, Optional
from uuid import UUID

from .....config.logging import get_logger
from ..suggestion_models import Suggestion, SuggestionType
from . import SuggestionStrategy

logger = get_logger(__name__)


class WeatherCareStrategy(SuggestionStrategy):
    """Generate caring weather-based suggestions like a thoughtful parent.

    Checks the briefing weather data and generates warm reminders about
    temperature drops, rain, extreme heat/cold, etc.
    """

    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Suggestion]:
        suggestions: List[Suggestion] = []

        try:
            from ...weather_service import WeatherService
            weather_svc = WeatherService(self.db)
            weather = await weather_svc.get_weather_for_user(user_id)

            if not weather:
                return suggestions

            temp = weather.get("temperature")
            condition = weather.get("condition", "")
            temp_change = weather.get("temp_change")
            high_temp = weather.get("high_temperature")
            low_temp = weather.get("low_temperature")

            # Temperature drop care
            if temp_change is not None and temp_change <= -5:
                suggestions.append(Suggestion(
                    type=SuggestionType.WEATHER_CARE,
                    title="降温了，多穿点",
                    content=f"今天比昨天降了{abs(int(temp_change))}度，出门多穿件衣服，别冻着了。",
                    icon="thermostat",
                    action_options=["noted", "ignore"],
                    priority=75,
                    urgency="normal",
                ))

            # Rain reminder
            rain_keywords = ["雨", "rain", "shower", "storm", "drizzle", "雷"]
            if any(kw in condition.lower() for kw in rain_keywords):
                suggestions.append(Suggestion(
                    type=SuggestionType.WEATHER_CARE,
                    title="记得带伞",
                    content="今天有雨，出门别忘了带把伞，鞋子也别穿太好的。",
                    icon="umbrella",
                    action_options=["noted", "ignore"],
                    priority=70,
                    urgency="normal",
                ))

            # Extreme heat
            if high_temp is not None and high_temp >= 35:
                suggestions.append(Suggestion(
                    type=SuggestionType.WEATHER_CARE,
                    title="天热，注意防暑",
                    content=f"今天最高{int(high_temp)}度，多喝水，尽量别在大太阳下待太久。",
                    icon="wb_sunny",
                    action_options=["noted", "ignore"],
                    priority=70,
                    urgency="normal",
                ))

            # Extreme cold
            if low_temp is not None and low_temp <= 0:
                suggestions.append(Suggestion(
                    type=SuggestionType.WEATHER_CARE,
                    title="天冷，注意保暖",
                    content=f"今天最低{int(low_temp)}度，围巾手套都带上，路上小心。",
                    icon="ac_unit",
                    action_options=["noted", "ignore"],
                    priority=70,
                    urgency="normal",
                ))

        except Exception as e:
            logger.debug("WeatherCareStrategy skipped: %s", e)

        return suggestions
