"""Memory module utilities.

Text extraction (locations, persons, plan keywords), SQL LIKE escaping,
and JSON extraction helpers used by memory services.
"""

import json
import re
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# JSON extraction from LLM responses
# ---------------------------------------------------------------------------


def extract_json_from_response(
    content: str,
    expect_array: bool = False,
) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
    """Safely extract JSON from LLM response, handling code blocks and extra text."""
    content = content.strip()

    json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(json_pattern, content)
    if match:
        content = match.group(1).strip()

    try:
        obj_start = content.find('{')
        arr_start = content.find('[')

        if obj_start == -1 and arr_start == -1:
            return None

        if expect_array:
            if arr_start == -1:
                return None
            start = arr_start
            open_char, close_char = '[', ']'
        else:
            if obj_start == -1:
                if arr_start != -1:
                    start = arr_start
                    open_char, close_char = '[', ']'
                else:
                    return None
            elif arr_start == -1:
                start = obj_start
                open_char, close_char = '{', '}'
            else:
                start = min(obj_start, arr_start)
                open_char = content[start]
                close_char = '}' if open_char == '{' else ']'

        content = content[start:]

        bracket_count = 0
        end = 0
        for i, char in enumerate(content):
            if char == open_char:
                bracket_count += 1
            elif char == close_char:
                bracket_count -= 1
                if bracket_count == 0:
                    end = i + 1
                    break

        if end > 0:
            content = content[:end]

        result = json.loads(content)

        if expect_array:
            return result if isinstance(result, list) else None
        return result if isinstance(result, dict) else result

    except (json.JSONDecodeError, ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# SQL LIKE escaping
# ---------------------------------------------------------------------------


def escape_like_pattern(value: str) -> str:
    """Escape special SQL LIKE/ILIKE pattern characters."""
    return re.sub(r'([%_\\])', r'\\\1', value)


# ---------------------------------------------------------------------------
# Location extraction
# ---------------------------------------------------------------------------

CHINESE_CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "成都", "重庆", "武汉",
    "西安", "天津", "青岛", "大连", "厦门", "长沙", "沈阳", "哈尔滨", "济南", "郑州",
    "福州", "昆明", "贵阳", "南宁", "海口", "三亚", "珠海", "东莞", "佛山", "无锡",
]


def extract_locations(text: str, max_results: int = 10) -> List[str]:
    """Extract location names from text using regex (sync version)."""
    text = text[:2000]
    locations = []

    for city in CHINESE_CITIES:
        if city in text:
            locations.append(city)

    patterns = [
        r"[去到在来回](\w{2,4})[市省]?(?:[玩出住工]|$)",
        r"出差[去到]?(\w{2,4})",
        r"(\w{2,4})(?:出差|旅[行游]|办公)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) >= 2 and match not in locations:
                locations.append(match)

    return locations[:max_results]


# ---------------------------------------------------------------------------
# Person extraction
# ---------------------------------------------------------------------------

PERSON_PATTERNS = [
    r"(找|见|约|联系|拜访)\s*(\w{2,4})",
    r"(\w{2,4})\s*(在|住|工作)",
    r"和\s*(\w{2,4})\s*(一起|聊|吃|玩)",
]

FAMILY_KEYWORDS = [
    "老婆", "老公", "妈妈", "爸爸", "妈", "爸", "母亲", "父亲",
    "儿子", "女儿", "哥哥", "姐姐", "弟弟", "妹妹",
    "爷爷", "奶奶", "外公", "外婆", "叔叔", "阿姨", "舅舅", "姑姑",
]


def extract_persons(text: str, max_results: int = 10) -> List[str]:
    """Extract person names/roles from text using regex (sync version)."""
    text = text[:2000]
    persons = []

    for keyword in FAMILY_KEYWORDS:
        if keyword in text and keyword not in persons:
            persons.append(keyword)

    for pattern in PERSON_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                for group in match:
                    if len(group) >= 2 and not any(c.isdigit() for c in group):
                        if group not in persons:
                            persons.append(group)
            elif len(match) >= 2:
                if match not in persons:
                    persons.append(match)

    return persons[:max_results]


# ---------------------------------------------------------------------------
# Async extraction with LLM fallback
# ---------------------------------------------------------------------------


async def _extract_with_llm_fallback(
    text: str,
    extract_fn,
    fallback_fn,
    max_results: int = 10,
) -> List[str]:
    """Generic async extraction with LLM, falling back to regex."""
    import asyncio
    import logging

    logger = logging.getLogger(__name__)

    try:
        from .extraction import get_extractor

        extractor = get_extractor()
        result = await extractor.extract(text)
        extracted = extract_fn(result)

        if extracted:
            return extracted[:max_results]

        return fallback_fn(text, max_results)

    except asyncio.TimeoutError:
        logger.debug("LLM extraction timed out, falling back to regex")
        return fallback_fn(text, max_results)
    except ImportError:
        return fallback_fn(text, max_results)
    except Exception as e:
        logger.warning("Unexpected error in async extraction: %s", e)
        return fallback_fn(text, max_results)


async def extract_locations_async(text: str, max_results: int = 10) -> List[str]:
    """Extract location names from text using LLM (async version)."""
    def extract_locations_from_result(result):
        return result.entities.locations

    return await _extract_with_llm_fallback(
        text, extract_locations_from_result, extract_locations, max_results
    )


async def extract_persons_async(text: str, max_results: int = 10) -> List[str]:
    """Extract person names/roles from text using LLM (async version)."""
    def extract_persons_from_result(result):
        persons = []
        for person in result.entities.persons:
            if person.role and person.role not in persons:
                persons.append(person.role)
            elif person.name and person.name not in persons:
                persons.append(person.name)
        return persons

    return await _extract_with_llm_fallback(
        text, extract_persons_from_result, extract_persons, max_results
    )


# ---------------------------------------------------------------------------
# Plan keyword detection
# ---------------------------------------------------------------------------


def contains_plan_keywords(text: str) -> bool:
    """Check if text contains plan-related keywords."""
    plan_keywords = [
        "计划", "打算", "准备", "想要", "想去", "要去",
        "出差", "旅行", "旅游", "见面", "约", "聚",
        "下周", "下月", "下次", "以后", "将来",
    ]
    return any(kw in text for kw in plan_keywords)


# ---------------------------------------------------------------------------
# Person profile lookup
# ---------------------------------------------------------------------------


async def find_person_profile_by_name(db, user_id, person_name: str):
    """Find a person profile by name or alias."""
    from sqlalchemy import and_, func, or_, select

    from ..member.models import PersonProfile, ProfileStatus

    name_lower = person_name.lower()

    query = select(PersonProfile).where(
        and_(
            PersonProfile.user_id == user_id,
            PersonProfile.status == ProfileStatus.ACTIVE.value,
            or_(
                func.lower(PersonProfile.name) == name_lower,
                PersonProfile.aliases.contains([person_name]),
            ),
        )
    )

    result = await db.execute(query)
    return result.scalar_one_or_none()
