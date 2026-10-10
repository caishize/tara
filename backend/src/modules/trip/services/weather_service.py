"""
Weather Service - Provides weather forecast data for travel planning.

Uses a free weather API to get forecasts for destinations.
Weather data is used to:
1. Recommend indoor/outdoor activities based on conditions
2. Suggest backup plans for rainy days
3. Provide packing suggestions
"""
from typing import Dict, List, Optional, Any
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import httpx
import json

from ....config.logging import get_logger
from ....core.utils.city_pinyin import CITY_PINYIN
from ....core.utils.timezone import utc_now, local_today, DEFAULT_TIMEZONE_NAME

logger = get_logger(__name__)


class WeatherCondition(str, Enum):
    """Weather condition classifications"""
    SUNNY = "sunny"          # 晴天
    CLOUDY = "cloudy"        # 多云
    RAINY = "rainy"          # 雨天
    STORMY = "stormy"        # 暴风雨
    SNOWY = "snowy"          # 雪天
    FOGGY = "foggy"          # 雾天
    WINDY = "windy"          # 大风
    HOT = "hot"              # 高温 (>35°C)
    COLD = "cold"            # 低温 (<5°C)


@dataclass
class DailyForecast:
    """Daily weather forecast data"""
    date: date
    condition: WeatherCondition
    temp_high: float          # 最高温度 °C
    temp_low: float           # 最低温度 °C
    humidity: int             # 湿度 %
    wind_speed: float         # 风速 km/h
    precipitation_prob: int   # 降水概率 %
    uv_index: int             # 紫外线指数
    description: str          # 天气描述
    sunrise: str              # 日出时间
    sunset: str               # 日落时间

    @property
    def is_outdoor_friendly(self) -> bool:
        """Whether conditions are good for outdoor activities"""
        return (
            self.condition in [WeatherCondition.SUNNY, WeatherCondition.CLOUDY]
            and self.precipitation_prob < 40
            and self.wind_speed < 30
            and self.temp_high < 38
            and self.temp_low > 0
        )

    @property
    def needs_rain_gear(self) -> bool:
        """Whether rain gear is recommended"""
        return self.precipitation_prob >= 40 or self.condition in [
            WeatherCondition.RAINY, WeatherCondition.STORMY
        ]

    @property
    def activity_recommendations(self) -> Dict[str, str]:
        """Get activity recommendations based on weather"""
        recommendations = {
            "suggestion": "",
            "indoor_backup": "",
            "packing_tips": [],
        }

        if self.condition == WeatherCondition.SUNNY and self.temp_high > 35:
            recommendations["suggestion"] = "高温天气，建议选择室内或阴凉处活动，避开11:00-15:00户外"
            recommendations["indoor_backup"] = "可选择购物中心、博物馆、水族馆等室内场所"
            recommendations["packing_tips"] = ["防晒霜", "遮阳帽", "太阳镜", "充足饮用水"]
        elif self.condition == WeatherCondition.SUNNY:
            recommendations["suggestion"] = "晴朗天气，适合户外观光、拍照"
            recommendations["indoor_backup"] = "无需备选，尽情享受户外"
            recommendations["packing_tips"] = ["防晒霜", "太阳镜"]
        elif self.condition == WeatherCondition.RAINY:
            recommendations["suggestion"] = "雨天出行，建议优先安排室内景点"
            recommendations["indoor_backup"] = "博物馆、美术馆、购物中心、室内游乐场"
            recommendations["packing_tips"] = ["雨伞", "雨衣", "防水鞋", "备用衣物"]
        elif self.condition == WeatherCondition.STORMY:
            recommendations["suggestion"] = "暴风雨天气，强烈建议取消户外活动"
            recommendations["indoor_backup"] = "待在酒店或室内场所，注意安全"
            recommendations["packing_tips"] = ["雨具", "备用衣物", "充电宝"]
        elif self.condition == WeatherCondition.COLD:
            recommendations["suggestion"] = "低温天气，注意保暖，适当减少户外时间"
            recommendations["indoor_backup"] = "温泉、室内景点、商场"
            recommendations["packing_tips"] = ["保暖衣物", "暖宝宝", "保温杯"]
        elif self.condition == WeatherCondition.CLOUDY:
            recommendations["suggestion"] = "多云天气，适合户外活动，光线柔和适合拍照"
            recommendations["indoor_backup"] = "如有降雨可改去室内景点"
            recommendations["packing_tips"] = ["薄外套", "备用雨具"]
        else:
            recommendations["suggestion"] = "天气状况需关注，随时调整行程"
            recommendations["indoor_backup"] = "准备备选室内活动方案"
            recommendations["packing_tips"] = ["根据实际情况准备"]

        return recommendations


@dataclass
class WeatherForecast:
    """Weather forecast for a destination"""
    destination: str
    forecast_date: datetime
    daily_forecasts: List[DailyForecast]

    def get_forecast_for_date(self, target_date: date) -> Optional[DailyForecast]:
        """Get forecast for a specific date"""
        for forecast in self.daily_forecasts:
            if forecast.date == target_date:
                return forecast
        return None

    def get_overall_summary(self) -> Dict[str, Any]:
        """Get overall weather summary for the trip"""
        if not self.daily_forecasts:
            return {"summary": "无法获取天气预报"}

        outdoor_days = sum(1 for f in self.daily_forecasts if f.is_outdoor_friendly)
        rainy_days = sum(1 for f in self.daily_forecasts if f.needs_rain_gear)
        avg_high = sum(f.temp_high for f in self.daily_forecasts) / len(self.daily_forecasts)
        avg_low = sum(f.temp_low for f in self.daily_forecasts) / len(self.daily_forecasts)

        return {
            "summary": f"{len(self.daily_forecasts)}天行程中，{outdoor_days}天适合户外活动",
            "outdoor_friendly_days": outdoor_days,
            "rainy_days": rainy_days,
            "avg_temp_high": round(avg_high, 1),
            "avg_temp_low": round(avg_low, 1),
            "packing_suggestions": self._get_packing_suggestions(),
        }

    def _get_packing_suggestions(self) -> List[str]:
        """Generate packing suggestions based on forecast"""
        suggestions = set()

        for forecast in self.daily_forecasts:
            suggestions.update(forecast.activity_recommendations.get("packing_tips", []))

        return list(suggestions)


class WeatherService:
    """
    Weather service for travel planning.

    Uses Open-Meteo API (free, no API key required) for weather forecasts.
    Falls back to mock data if API is unavailable.
    """

    # City coordinates for common Chinese destinations
    CITY_COORDINATES = {
        "杭州": (30.2741, 120.1551),
        "北京": (39.9042, 116.4074),
        "上海": (31.2304, 121.4737),
        "广州": (23.1291, 113.2644),
        "深圳": (22.5431, 114.0579),
        "成都": (30.5728, 104.0668),
        "重庆": (29.4316, 106.9123),
        "西安": (34.3416, 108.9398),
        "南京": (32.0603, 118.7969),
        "苏州": (31.2990, 120.5853),
        "厦门": (24.4798, 118.0894),
        "三亚": (18.2528, 109.5119),
        "青岛": (36.0671, 120.3826),
        "大连": (38.9140, 121.6147),
        "桂林": (25.2736, 110.2907),
        "丽江": (26.8721, 100.2253),
        "昆明": (24.8801, 102.8329),
        "张家界": (29.1170, 110.4794),
        "黄山": (29.7147, 118.3375),
        "敦煌": (40.1421, 94.6618),
    }

    def __init__(self, api_timeout: int = 10):
        self.api_timeout = api_timeout
        self.api_base_url = "https://api.open-meteo.com/v1/forecast"

    async def get_forecast(
        self,
        destination: str,
        start_date: date,
        end_date: date
    ) -> WeatherForecast:
        """
        Get weather forecast for a destination.

        Args:
            destination: Destination city name
            start_date: Trip start date
            end_date: Trip end date

        Returns:
            WeatherForecast with daily forecasts
        """
        # Try to get coordinates from hardcoded list
        coords = self._get_coordinates(destination)

        # If not in hardcoded list, try geocoding
        if not coords:
            coords = await self._geocode_city(destination)

        if not coords:
            raise ValueError(f"无法获取{destination}的地理坐标，天气预报不可用")

        return await self._fetch_from_api(destination, coords, start_date, end_date)

    def _get_coordinates(self, destination: str) -> Optional[tuple]:
        """Get coordinates for a destination"""
        # Check exact match
        if destination in self.CITY_COORDINATES:
            return self.CITY_COORDINATES[destination]

        # Check partial match
        for city, coords in self.CITY_COORDINATES.items():
            if city in destination or destination in city:
                return coords

        return None

    @staticmethod
    def _normalize_city_names(city: str) -> List[str]:
        """Generate candidate names by stripping province prefixes / suffixes."""
        import re
        candidates = [city]
        provinces = (
            '北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|'
            '福建|江西|山东|河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|'
            '甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|香港|澳门'
        )
        stripped = re.sub(rf'^(?:{provinces})(?:省|市|自治区|特别行政区)?', '', city)
        if stripped and stripped != city:
            candidates.append(stripped)
        no_suffix = re.sub(r'[市县区]$', '', stripped or city)
        if no_suffix and no_suffix not in candidates:
            candidates.append(no_suffix)
        return candidates

    async def _geocode_city(self, city: str) -> Optional[tuple]:
        """Resolve city name to coordinates using Open-Meteo Geocoding API.

        Strategy:
        1. Try Chinese name variants (original, stripped province/suffix)
        2. If all fail, try Pinyin/English from CITY_PINYIN lookup table

        Open-Meteo uses GeoNames which indexes Latin names reliably but
        Chinese search is hit-or-miss.
        """
        candidates = self._normalize_city_names(city)

        # Build pinyin fallback list
        pinyin_candidates = []
        for candidate in candidates:
            pinyin = CITY_PINYIN.get(candidate)
            if pinyin and pinyin not in pinyin_candidates:
                pinyin_candidates.append(pinyin)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Phase 1: try Chinese names
                for candidate in candidates:
                    response = await client.get(
                        'https://geocoding-api.open-meteo.com/v1/search',
                        params={'name': candidate, 'count': 1, 'language': 'zh'},
                    )
                    response.raise_for_status()
                    results = response.json().get('results', [])
                    if results:
                        return (results[0]['latitude'], results[0]['longitude'])

                # Phase 2: try Pinyin/English (much more reliable for GeoNames)
                for candidate in pinyin_candidates:
                    response = await client.get(
                        'https://geocoding-api.open-meteo.com/v1/search',
                        params={'name': candidate, 'count': 1, 'language': 'zh'},
                    )
                    response.raise_for_status()
                    results = response.json().get('results', [])
                    if results:
                        return (results[0]['latitude'], results[0]['longitude'])
        except Exception as e:
            logger.warning("Geocoding failed for %s: %s: %s", city, type(e).__name__, e)
        return None

    async def _fetch_from_api(
        self,
        destination: str,
        coords: tuple,
        start_date: date,
        end_date: date
    ) -> WeatherForecast:
        """Fetch weather from Open-Meteo API"""
        lat, lon = coords

        # Open-Meteo API only provides 16-day forecast
        forecast_days = min((end_date - start_date).days + 1, 16)

        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "weathercode",
                "windspeed_10m_max",
                "uv_index_max",
                "sunrise",
                "sunset",
            ],
            "timezone": DEFAULT_TIMEZONE_NAME,
            "forecast_days": forecast_days,
        }

        async with httpx.AsyncClient(timeout=self.api_timeout) as client:
            response = await client.get(self.api_base_url, params=params)
            response.raise_for_status()
            data = response.json()

        daily_forecasts = self._parse_api_response(data, start_date, end_date)

        return WeatherForecast(
            destination=destination,
            forecast_date=utc_now(),
            daily_forecasts=daily_forecasts
        )

    def _parse_api_response(
        self,
        data: Dict,
        start_date: date,
        end_date: date
    ) -> List[DailyForecast]:
        """Parse Open-Meteo API response"""
        forecasts = []
        daily_data = data.get("daily", {})

        dates = daily_data.get("time", [])
        temp_max = daily_data.get("temperature_2m_max", [])
        temp_min = daily_data.get("temperature_2m_min", [])
        precip_prob = daily_data.get("precipitation_probability_max", [])
        weather_codes = daily_data.get("weathercode", [])
        wind_speed = daily_data.get("windspeed_10m_max", [])
        uv_index = daily_data.get("uv_index_max", [])
        sunrise = daily_data.get("sunrise", [])
        sunset = daily_data.get("sunset", [])

        for i, date_str in enumerate(dates):
            forecast_date = date.fromisoformat(date_str)

            # Only include dates within trip range
            if forecast_date < start_date or forecast_date > end_date:
                continue

            condition = self._weather_code_to_condition(
                weather_codes[i] if i < len(weather_codes) else 0,
                temp_max[i] if i < len(temp_max) else 20,
                temp_min[i] if i < len(temp_min) else 10,
            )

            forecasts.append(DailyForecast(
                date=forecast_date,
                condition=condition,
                temp_high=temp_max[i] if i < len(temp_max) else 20,
                temp_low=temp_min[i] if i < len(temp_min) else 10,
                humidity=65,  # API doesn't provide daily humidity
                wind_speed=wind_speed[i] if i < len(wind_speed) else 10,
                precipitation_prob=precip_prob[i] if i < len(precip_prob) else 0,
                uv_index=int(uv_index[i]) if i < len(uv_index) else 5,
                description=self._get_weather_description(condition),
                sunrise=sunrise[i].split("T")[1][:5] if i < len(sunrise) else "06:00",
                sunset=sunset[i].split("T")[1][:5] if i < len(sunset) else "18:00",
            ))

        return forecasts

    def _weather_code_to_condition(
        self,
        code: int,
        temp_high: float,
        temp_low: float
    ) -> WeatherCondition:
        """Convert WMO weather code to condition"""
        # WMO Weather interpretation codes
        # https://open-meteo.com/en/docs
        if code in [0, 1]:  # Clear, mainly clear
            if temp_high > 35:
                return WeatherCondition.HOT
            return WeatherCondition.SUNNY
        elif code in [2, 3]:  # Partly cloudy, overcast
            return WeatherCondition.CLOUDY
        elif code in [45, 48]:  # Fog
            return WeatherCondition.FOGGY
        elif code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:  # Drizzle, rain, showers
            return WeatherCondition.RAINY
        elif code in [71, 73, 75, 77, 85, 86]:  # Snow
            return WeatherCondition.SNOWY
        elif code in [95, 96, 99]:  # Thunderstorm
            return WeatherCondition.STORMY
        elif temp_low < 5:
            return WeatherCondition.COLD

        return WeatherCondition.CLOUDY

    def _get_weather_description(self, condition: WeatherCondition) -> str:
        """Get Chinese description for weather condition"""
        descriptions = {
            WeatherCondition.SUNNY: "晴朗",
            WeatherCondition.CLOUDY: "多云",
            WeatherCondition.RAINY: "有雨",
            WeatherCondition.STORMY: "雷暴",
            WeatherCondition.SNOWY: "有雪",
            WeatherCondition.FOGGY: "有雾",
            WeatherCondition.WINDY: "大风",
            WeatherCondition.HOT: "高温",
            WeatherCondition.COLD: "低温",
        }
        return descriptions.get(condition, "未知")


    def get_itinerary_weather_context(
        self,
        forecast: WeatherForecast,
        day_number: int,
        trip_start_date: date
    ) -> Dict[str, Any]:
        """
        Get weather context for a specific day to include in LLM prompt.

        Args:
            forecast: Weather forecast data
            day_number: Day number in the trip (1-indexed)
            trip_start_date: Start date of the trip

        Returns:
            Weather context dict for the day
        """
        target_date = trip_start_date + timedelta(days=day_number - 1)
        daily_forecast = forecast.get_forecast_for_date(target_date)

        if not daily_forecast:
            return {
                "available": False,
                "message": "无法获取当天天气预报",
            }

        recommendations = daily_forecast.activity_recommendations

        return {
            "available": True,
            "date": str(target_date),
            "condition": daily_forecast.condition.value,
            "description": daily_forecast.description,
            "temp_high": daily_forecast.temp_high,
            "temp_low": daily_forecast.temp_low,
            "precipitation_prob": daily_forecast.precipitation_prob,
            "is_outdoor_friendly": daily_forecast.is_outdoor_friendly,
            "needs_rain_gear": daily_forecast.needs_rain_gear,
            "activity_suggestion": recommendations["suggestion"],
            "indoor_backup": recommendations["indoor_backup"],
            "sunrise": daily_forecast.sunrise,
            "sunset": daily_forecast.sunset,
        }
