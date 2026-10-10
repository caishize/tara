"""
Geocoding utilities for location-based features.

Provides:
- geocode_city(): Resolve city name → (lat, lng) via Open-Meteo
- haversine_km(): Great-circle distance between two coordinates
- locations_within_radius(): Check if two city names are within a radius

Uses Open-Meteo Geocoding API (free, no API key required).
Results are cached in-memory (bounded LRU) to avoid redundant HTTP calls.
"""
import math
import re
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import httpx

from ...config.logging import get_logger

logger = get_logger(__name__)

# Maximum allowed proximity radius (km) — prevents absurd queries
MAX_PROXIMITY_KM = 500.0

# Default radius for "nearby" checks (km)
DEFAULT_PROXIMITY_KM = 50.0

# Bounded geocoding cache (LRU, max 1024 entries)
_CACHE_MAXSIZE = 1024
_geocode_cache_store: Dict[str, Tuple[float, float]] = {}


def _cache_get(key: str) -> Optional[Tuple[float, float]]:
    return _geocode_cache_store.get(key)


def _cache_put(key: str, value: Tuple[float, float]) -> None:
    if len(_geocode_cache_store) >= _CACHE_MAXSIZE:
        # Evict oldest entry (FIFO — good enough for this use case)
        oldest_key = next(iter(_geocode_cache_store))
        del _geocode_cache_store[oldest_key]
    _geocode_cache_store[key] = value


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _normalize_city(city: str) -> List[str]:
    """Generate candidate city names by stripping prefixes/suffixes."""
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


async def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    """
    Resolve a city name to (lat, lng) coordinates.

    Returns None if the city cannot be geocoded.
    Results are cached in-memory (bounded to 1024 entries).
    """
    # Check cache first
    normalized = city.strip()
    cached = _cache_get(normalized)
    if cached is not None:
        return cached

    candidates = _normalize_city(normalized)

    try:
        from .city_pinyin import CITY_PINYIN
    except ImportError:
        CITY_PINYIN = {}

    pinyin_candidates = []
    for c in candidates:
        p = CITY_PINYIN.get(c)
        if p and p not in pinyin_candidates:
            pinyin_candidates.append(p)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for name in candidates + pinyin_candidates:
                try:
                    response = await client.get(
                        'https://geocoding-api.open-meteo.com/v1/search',
                        params={'name': name, 'count': 1, 'language': 'zh'},
                    )
                    response.raise_for_status()
                    results = response.json().get('results', [])
                    if results:
                        lat = results[0]['latitude']
                        lng = results[0]['longitude']
                        _cache_put(normalized, (lat, lng))
                        return (lat, lng)
                except Exception:
                    continue
    except Exception as e:
        logger.debug("Geocoding failed for %s: %s", city, e)

    return None


async def locations_within_radius(
    city_a: str,
    city_b: str,
    radius_km: float = DEFAULT_PROXIMITY_KM,
) -> bool:
    """
    Check if two city names are within a given radius.

    Falls back to text containment if geocoding fails for either city.
    radius_km is capped at MAX_PROXIMITY_KM (500km) to prevent absurd queries.
    """
    # Cap radius to a sane maximum
    radius_km = min(radius_km, MAX_PROXIMITY_KM)

    # Quick text match first (cheap)
    a_lower = city_a.lower()
    b_lower = city_b.lower()
    if a_lower in b_lower or b_lower in a_lower:
        return True

    # Try geocoding
    coords_a = await geocode_city(city_a)
    coords_b = await geocode_city(city_b)

    if coords_a is None or coords_b is None:
        return False

    distance = haversine_km(coords_a[0], coords_a[1], coords_b[0], coords_b[1])
    return distance <= radius_km
