"""Weather Service - Fetch and cache weather data.

Provider chain:
1. QWeather (和风天气) - Primary, requires QWEATHER_API_KEY
2. OpenWeatherMap - Secondary, requires OPENWEATHER_API_KEY
3. Open-Meteo - Free backup, no API key required
"""
import logging
import os
import httpx
from datetime import datetime, timedelta
from typing import Callable, Optional
from dataclasses import dataclass

from ...core.utils.city_pinyin import CITY_PINYIN
from ...core.utils.timezone import utc_now


logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[str, str], None]]


class WeatherUnavailableError(Exception):
    """Raised when all weather providers fail."""


@dataclass
class WeatherData:
    """Weather data model."""
    temperature: int  # Current temperature in Celsius
    condition: str  # Weather condition (晴, 多云, 雨, etc.)
    high_temp: Optional[int] = None  # Today's high
    low_temp: Optional[int] = None  # Today's low
    humidity: Optional[str] = None  # Humidity percentage
    wind: Optional[str] = None  # Wind info
    location: Optional[str] = None  # Location name
    icon: Optional[str] = None  # Weather icon code
    updated_at: Optional[datetime] = None


# WMO Weather Code -> Chinese condition
WMO_CODE_MAP = {
    0: '晴',
    1: '晴', 2: '多云', 3: '阴',
    45: '雾', 48: '雾凇',
    51: '小雨', 53: '中雨', 55: '大雨',
    56: '冻雨', 57: '冻雨',
    61: '小雨', 63: '中雨', 65: '大雨',
    66: '冻雨', 67: '冻雨',
    71: '小雪', 73: '中雪', 75: '大雪',
    77: '雪粒',
    80: '阵雨', 81: '阵雨', 82: '暴雨',
    85: '阵雪', 86: '暴雪',
    95: '雷阵雨',
    96: '雷阵雨伴冰雹', 99: '雷阵雨伴冰雹',
}

WIND_DIRECTIONS = ['北', '东北', '东', '东南', '南', '西南', '西', '西北']


def _wind_direction_cn(degrees: float) -> str:
    """Convert wind direction degrees to Chinese."""
    idx = round(degrees / 45) % 8
    return f"{WIND_DIRECTIONS[idx]}风"


def _wind_speed_to_scale(speed_kmh: float) -> int:
    """Convert wind speed (km/h) to Beaufort scale (级)."""
    thresholds = [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118]
    for scale, threshold in enumerate(thresholds):
        if speed_kmh < threshold:
            return scale
    return 12


class WeatherService:
    """
    Service for fetching weather data.

    Provider chain (all real data, no mock):
    1. QWeather (和风天气) - Primary for China
    2. OpenWeatherMap - Secondary fallback
    3. Open-Meteo - Free backup, no API key required
    """

    def __init__(self):
        self.qweather_key = os.getenv('QWEATHER_API_KEY')
        self.openweather_key = os.getenv('OPENWEATHER_API_KEY')
        self._cache: dict = {}
        self._cache_ttl = timedelta(minutes=30)

    @staticmethod
    def _emit_progress(
        progress_cb: ProgressCallback,
        stage: str,
        message: str,
    ) -> None:
        """Best-effort progress reporting; never break weather flow."""
        if not progress_cb:
            return
        try:
            progress_cb(stage, message)
        except Exception:
            logger.debug("Weather progress callback failed", exc_info=True)

    async def get_weather(
        self,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        city: Optional[str] = None,
        progress_cb: ProgressCallback = None,
    ) -> WeatherData:
        """
        Get current weather data.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            city: City name (fallback if no coordinates)

        Returns:
            WeatherData object

        Raises:
            WeatherUnavailableError: When all providers fail
        """
        cache_key = f"{latitude}_{longitude}_{city}"

        if cache_key in self._cache:
            data, cached_at = self._cache[cache_key]
            if utc_now() - cached_at < self._cache_ttl:
                self._emit_progress(progress_cb, 'cache_hit', '命中天气缓存，正在返回结果...')
                return data

        self._emit_progress(progress_cb, 'start', '正在准备天气查询...')
        weather = await self._fetch_weather(
            latitude, longitude, city, progress_cb=progress_cb
        )
        self._cache[cache_key] = (weather, utc_now())
        self._emit_progress(progress_cb, 'done', '天气数据已准备完成')
        return weather

    async def _fetch_weather(
        self,
        latitude: Optional[float],
        longitude: Optional[float],
        city: Optional[str],
        progress_cb: ProgressCallback = None,
    ) -> WeatherData:
        """Fetch weather from provider chain. All providers return real data."""
        errors: list = []

        # 1. QWeather (primary, requires key)
        if self.qweather_key:
            try:
                self._emit_progress(progress_cb, 'qweather_start', '正在尝试和风天气...')
                data = await self._fetch_qweather(
                    latitude, longitude, city, progress_cb=progress_cb
                )
                self._emit_progress(progress_cb, 'qweather_ok', '和风天气查询成功')
                return data
            except Exception as e:
                errors.append(f"QWeather: {type(e).__name__}: {e}")
                self._emit_progress(progress_cb, 'qweather_fail', '和风天气不可用，切换备用源...')
                logger.warning("QWeather failed: %s: %s", type(e).__name__, e)
        else:
            self._emit_progress(progress_cb, 'qweather_skip', '未配置和风天气密钥，跳过')

        # 2. OpenWeatherMap (secondary, requires key)
        if self.openweather_key:
            try:
                self._emit_progress(progress_cb, 'openweather_start', '正在尝试 OpenWeatherMap...')
                data = await self._fetch_openweather(
                    latitude, longitude, city, progress_cb=progress_cb
                )
                self._emit_progress(progress_cb, 'openweather_ok', 'OpenWeatherMap 查询成功')
                return data
            except Exception as e:
                errors.append(f"OpenWeather: {type(e).__name__}: {e}")
                self._emit_progress(progress_cb, 'openweather_fail', 'OpenWeatherMap 不可用，切换备用源...')
                logger.warning("OpenWeatherMap failed: %s: %s", type(e).__name__, e)
        else:
            self._emit_progress(progress_cb, 'openweather_skip', '未配置 OpenWeather 密钥，跳过')

        # 3. Open-Meteo (free, no key required)
        try:
            self._emit_progress(progress_cb, 'open_meteo_start', '正在使用 Open-Meteo 查询天气...')
            data = await self._fetch_open_meteo(
                latitude, longitude, city, progress_cb=progress_cb
            )
            self._emit_progress(progress_cb, 'open_meteo_ok', 'Open-Meteo 查询成功')
            return data
        except Exception as e:
            errors.append(f"Open-Meteo: {type(e).__name__}: {e}")
            self._emit_progress(progress_cb, 'open_meteo_fail', 'Open-Meteo 查询失败')
            logger.warning("Open-Meteo failed: %s: %s", type(e).__name__, e)

        raise WeatherUnavailableError(
            f"所有天气数据源均不可用 ({city or f'{latitude},{longitude}'}): "
            + "; ".join(errors)
        )

    @staticmethod
    def _normalize_city_names(city: str) -> list:
        """
        Generate candidate city names by stripping province prefixes and
        administrative suffixes. E.g. "广东揭阳" -> ["广东揭阳", "揭阳"].
        """
        import re
        candidates = [city]
        # Strip known province/region prefixes (e.g. "广东揭阳" -> "揭阳")
        provinces = (
            '北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|'
            '福建|江西|山东|河南|湖北|湖南|广东|海南|四川|贵州|云南|陕西|'
            '甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|香港|澳门'
        )
        stripped = re.sub(rf'^(?:{provinces})(?:省|市|自治区|特别行政区)?', '', city)
        if stripped and stripped != city:
            candidates.append(stripped)
        # Strip trailing 市/县/区 (e.g. "揭阳市" -> "揭阳")
        no_suffix = re.sub(r'[市县区]$', '', stripped or city)
        if no_suffix and no_suffix not in candidates:
            candidates.append(no_suffix)
        return candidates

    async def _geocode_city(
        self,
        city: str,
        progress_cb: ProgressCallback = None,
    ) -> tuple:
        """
        Resolve city name to coordinates using Open-Meteo Geocoding API.

        Returns:
            (latitude, longitude, resolved_name)

        Raises:
            ValueError: When city cannot be geocoded
        """
        candidates = self._normalize_city_names(city)

        # Add pinyin variants for each candidate
        pinyin_candidates = []
        for candidate in candidates:
            pinyin = CITY_PINYIN.get(candidate)
            if pinyin and pinyin not in pinyin_candidates:
                pinyin_candidates.append(pinyin)

        async with httpx.AsyncClient() as client:
            # Phase 1: try Chinese names with language=zh
            for candidate in candidates:
                self._emit_progress(progress_cb, 'geocode_try', f'正在解析地点: {candidate}')
                result = await self._try_geocode(
                    client, candidate, language='zh', progress_cb=progress_cb
                )
                if result:
                    self._emit_progress(progress_cb, 'geocode_ok', f'已解析地点: {candidate}')
                    return result

            # Phase 2: try Pinyin/English names (much more reliable for GeoNames)
            for candidate in pinyin_candidates:
                self._emit_progress(progress_cb, 'geocode_try', f'正在解析地点: {candidate}')
                result = await self._try_geocode(
                    client, candidate, language='zh', progress_cb=progress_cb
                )
                if result:
                    self._emit_progress(progress_cb, 'geocode_ok', f'已解析地点: {candidate}')
                    return result

            tried = candidates + pinyin_candidates
            raise ValueError(f"无法识别城市: {city} (tried: {', '.join(tried)})")

    @staticmethod
    async def _try_geocode(
        client: httpx.AsyncClient,
        name: str,
        language: str = 'zh',
        progress_cb: ProgressCallback = None,
    ) -> Optional[tuple]:
        """Try geocoding a single name. Returns (lat, lng, display_name) or None."""
        WeatherService._emit_progress(progress_cb, 'geocode_request', f'请求地理编码: {name}')
        response = await client.get(
            'https://geocoding-api.open-meteo.com/v1/search',
            params={'name': name, 'count': 1, 'language': language},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        results = data.get('results', [])
        if not results:
            WeatherService._emit_progress(progress_cb, 'geocode_miss', f'地点未命中: {name}')
            return None

        result = results[0]
        resolved_name = result.get('name', name)
        admin1 = result.get('admin1', '')
        display_name = f"{admin1} {resolved_name}" if admin1 and admin1 != resolved_name else resolved_name
        return (result['latitude'], result['longitude'], display_name)

    async def _fetch_open_meteo(
        self,
        latitude: Optional[float],
        longitude: Optional[float],
        city: Optional[str],
        progress_cb: ProgressCallback = None,
    ) -> WeatherData:
        """Fetch weather from Open-Meteo (free, no API key required)."""
        resolved_name = city or ''

        if not (latitude and longitude):
            if not city:
                raise ValueError("Need city name or coordinates")
            self._emit_progress(progress_cb, 'resolve_city', '未提供坐标，正在解析城市坐标...')
            latitude, longitude, resolved_name = await self._geocode_city(
                city, progress_cb=progress_cb
            )

        async with httpx.AsyncClient() as client:
            self._emit_progress(progress_cb, 'forecast_request', '正在请求天气预报接口...')
            response = await client.get(
                'https://api.open-meteo.com/v1/forecast',
                params={
                    'latitude': latitude,
                    'longitude': longitude,
                    'current': 'temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m',
                    'daily': 'temperature_2m_max,temperature_2m_min',
                    'timezone': 'auto',
                    'forecast_days': 1,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            self._emit_progress(progress_cb, 'forecast_ok', '天气预报数据已返回')

            current = data.get('current', {})
            daily = data.get('daily', {})

            weather_code = current.get('weather_code', -1)
            condition = WMO_CODE_MAP.get(weather_code, '未知')

            wind_dir = _wind_direction_cn(current.get('wind_direction_10m', 0))
            wind_speed = current.get('wind_speed_10m', 0)
            wind_scale = _wind_speed_to_scale(wind_speed)

            max_temps = daily.get('temperature_2m_max', [])
            min_temps = daily.get('temperature_2m_min', [])

            return WeatherData(
                temperature=int(round(current.get('temperature_2m', 0))),
                condition=condition,
                high_temp=int(round(max_temps[0])) if max_temps else None,
                low_temp=int(round(min_temps[0])) if min_temps else None,
                humidity=f"{current.get('relative_humidity_2m', 0)}%",
                wind=f"{wind_dir} {wind_scale}级",
                location=resolved_name,
                updated_at=utc_now(),
            )

    async def _fetch_qweather(
        self,
        latitude: Optional[float],
        longitude: Optional[float],
        city: Optional[str],
        progress_cb: ProgressCallback = None,
    ) -> WeatherData:
        """Fetch weather from QWeather (和风天气) API."""
        base_url = 'https://devapi.qweather.com/v7/weather/now'

        if latitude and longitude:
            location = f"{longitude},{latitude}"
        elif city:
            location = city
        else:
            location = '101010100'  # Beijing

        async with httpx.AsyncClient() as client:
            self._emit_progress(progress_cb, 'qweather_request', '正在请求和风天气接口...')
            response = await client.get(
                base_url,
                params={
                    'location': location,
                    'key': self.qweather_key,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            self._emit_progress(progress_cb, 'qweather_response', '和风天气接口已返回')

            if data.get('code') != '200':
                raise Exception(f"QWeather API error: {data.get('code')}")

            now = data.get('now', {})

            return WeatherData(
                temperature=int(now.get('temp', 0)),
                condition=now.get('text', '未知'),
                humidity=f"{now.get('humidity', 0)}%",
                wind=f"{now.get('windDir', '')} {now.get('windScale', '')}级",
                icon=now.get('icon'),
                updated_at=utc_now(),
            )

    async def _fetch_openweather(
        self,
        latitude: Optional[float],
        longitude: Optional[float],
        city: Optional[str],
        progress_cb: ProgressCallback = None,
    ) -> WeatherData:
        """Fetch weather from OpenWeatherMap API."""
        base_url = 'https://api.openweathermap.org/data/2.5/weather'

        params = {
            'appid': self.openweather_key,
            'units': 'metric',
            'lang': 'zh_cn',
        }

        if latitude and longitude:
            params['lat'] = latitude
            params['lon'] = longitude
        elif city:
            params['q'] = city
        else:
            params['q'] = 'Beijing,CN'

        async with httpx.AsyncClient() as client:
            self._emit_progress(progress_cb, 'openweather_request', '正在请求 OpenWeatherMap 接口...')
            response = await client.get(
                base_url,
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            self._emit_progress(progress_cb, 'openweather_response', 'OpenWeatherMap 接口已返回')

            main = data.get('main', {})
            weather = data.get('weather', [{}])[0]

            return WeatherData(
                temperature=int(main.get('temp', 0)),
                condition=weather.get('description', '未知'),
                high_temp=int(main.get('temp_max', 0)),
                low_temp=int(main.get('temp_min', 0)),
                humidity=f"{main.get('humidity', 0)}%",
                location=data.get('name'),
                icon=weather.get('icon'),
                updated_at=utc_now(),
            )

    def get_weather_icon(self, condition: str) -> str:
        """Get emoji icon for weather condition."""
        condition_lower = condition.lower()

        if any(x in condition_lower for x in ['晴', 'sunny', 'clear']):
            return '☀️'
        elif any(x in condition_lower for x in ['多云', 'partly', 'cloud']):
            return '⛅'
        elif any(x in condition_lower for x in ['阴', 'overcast', 'cloudy']):
            return '☁️'
        elif any(x in condition_lower for x in ['雨', 'rain']):
            return '🌧️'
        elif any(x in condition_lower for x in ['雷', 'thunder']):
            return '⛈️'
        elif any(x in condition_lower for x in ['雪', 'snow']):
            return '❄️'
        elif any(x in condition_lower for x in ['雾', 'fog']):
            return '🌫️'
        elif any(x in condition_lower for x in ['霾', 'haze']):
            return '😷'
        else:
            return '🌤️'
