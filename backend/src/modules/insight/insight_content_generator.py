"""Shared LLM content generation for insight/briefing text.

Replaces hardcoded Chinese template strings with Haiku LLM calls.
Pattern: assemble context XML -> call Haiku -> parse JSON output -> fallback.

Used by:
- insight_service.py (holiday insights, birthday/anniversary insights)
- proactive_insight_service.py (stress suggestion)
- briefing suggestion_service.py (self-care, fallback suggestions)
- briefing briefing_service.py (secretary summary)
"""

import json
import re
from typing import Any, Dict, Optional

from ...config.logging import get_logger
from ...config.settings import settings
from .constants import SECRETARY_PERSONA_PROMPT

logger = get_logger(__name__)

# Maximum number of LLM attempts (initial + retries) before falling back.
_MAX_LLM_ATTEMPTS = 2

# Re-export for backward compatibility with any internal callers.
_SECRETARY_TONE_PREFIX = SECRETARY_PERSONA_PROMPT

_INSIGHT_SYSTEM_PROMPT = SECRETARY_PERSONA_PROMPT + """根据提供的上下文，生成一条温馨提醒。

## 要求
1. 语气像家人叮嘱，不要用"建议您"、"请确认"等公文词
2. 内容具体、温暖、可执行
3. 一两句话即可，不要太长
4. 如果上下文中有人物关系信息，自然融入

## 好的例子
{"title": "记得联系姑姑", "content": "这次又去北京了，上两次都去看了姑姑，这次也别忘了。"}
{"title": "妈妈生日快到了", "content": "下周二是妈妈生日，想好送什么了吗？趁这两天有空准备一下。"}
{"title": "出差回来歇一歇", "content": "这周连着跑了三个城市，回来好好休息一天吧。"}

## 不好的例子（禁止）
{"title": "日程提醒", "content": "建议您关注即将到来的重要日程。"} — 太笼统，公文体
{"title": "行程通知", "content": "请注意您的出行安排。"} — 没有具体内容，像系统通知

## 输出格式（严格JSON）
{"title": "标题（10字以内）", "content": "提醒内容（50字以内）"}"""

_SUMMARY_SYSTEM_PROMPT = SECRETARY_PERSONA_PROMPT + """用一两句温暖的话概括今天的安排。
直接返回纯文本，不要JSON格式。

## 严格规则
- **禁止编造人名**：只能使用上下文中明确出现的人名，绝对不能自己编造或猜测任何人名
- 如果不知道同行人是谁，就不要提人名，用"你们"或省略即可

## 好的例子
- 忙碌的一天："今天排得挺满的，中午记得吃饭，下午那个会议别迟到。"
- 轻松的一天："今天就两件小事，安排完还能喝杯咖啡，挺好的。"
- 有出行："今天要去上海，东西都收拾好了吗？路上注意安全。"
- 有特殊日子："今天是妈妈生日，别的事都不急，这个最重要。"

## 不好的例子（禁止）
- "今天有3个日程，忙碌度适中。" — 像仪表盘读数
- "为您整理了今天的安排。" — 公文体，没有信息量
- "今天是和小林的出游" — 编造了上下文中不存在的人名"""

_STRESS_SYSTEM_PROMPT = SECRETARY_PERSONA_PROMPT + """根据用户最近的压力状况，生成一条关怀提醒。

## 要求
1. 不要直接说"你很焦虑"、"你压力大"，而是委婉关怀
2. 语气像家人叮嘱
3. 给出一个具体的、可执行的建议

## 输出格式（严格JSON）
{"title": "标题（10字以内）", "content": "关怀内容（60字以内）"}"""


def _build_contextual_fallback(
    fallback_title: str,
    fallback_content: str,
    person_name: Optional[str] = None,
    event_type: Optional[str] = None,
    days_until: Optional[int] = None,
) -> Dict[str, str]:
    """Build a contextual fallback when LLM attempts are exhausted.

    When at least one of ``person_name``, ``event_type``, ``days_until`` is
    available the generated string is more specific than the generic default.
    """
    parts = []
    if person_name:
        parts.append(person_name)
    if event_type:
        parts.append(f"的{event_type}")
    if days_until is not None and days_until >= 0:
        parts.append(f"还有{days_until}天")

    if parts:
        contextual = "".join(parts) + "，别忘了准备。"
        title = fallback_title if fallback_title != "温馨提醒" else "日程提醒"
        return {"title": title, "content": contextual}

    return {"title": fallback_title, "content": fallback_content}


def _extract_context_fields(context_xml: str) -> Dict[str, Any]:
    """Best-effort extraction of person_name / event_type / days_until from XML context."""
    fields: Dict[str, Any] = {}

    name_match = re.search(r"<person_name>(.*?)</person_name>", context_xml)
    if name_match:
        fields["person_name"] = name_match.group(1).strip()

    type_match = re.search(r"<event_type>(.*?)</event_type>", context_xml)
    if type_match:
        fields["event_type"] = type_match.group(1).strip()

    days_match = re.search(r"<days_until>(\d+)</days_until>", context_xml)
    if days_match:
        fields["days_until"] = int(days_match.group(1))

    return fields


async def generate_insight_content(
    context_xml: str,
    insight_type: str,
    system_prompt: Optional[str] = None,
    fallback_title: str = "温馨提醒",
    fallback_content: str = "有件事想提醒你一下。",
    person_name: Optional[str] = None,
    event_type: Optional[str] = None,
    days_until: Optional[int] = None,
) -> Dict[str, str]:
    """Generate insight title + content via Haiku LLM call.

    Makes up to ``_MAX_LLM_ATTEMPTS`` LLM calls (initial + retry with reduced
    prompt) before falling back to a contextual fallback that incorporates
    ``person_name``, ``event_type``, and ``days_until`` when available.

    Args:
        context_xml: Assembled context (events, person profiles, etc.)
        insight_type: Type of insight for prompt customization
        system_prompt: Override system prompt (defaults to _INSIGHT_SYSTEM_PROMPT)
        fallback_title: Title to use if LLM fails
        fallback_content: Content to use if LLM fails
        person_name: Person name for contextual fallback
        event_type: Event type label for contextual fallback
        days_until: Days remaining until the event for contextual fallback

    Returns:
        Dict with "title" and "content" keys
    """
    # Auto-extract context fields from XML when not explicitly provided
    if person_name is None or event_type is None or days_until is None:
        extracted = _extract_context_fields(context_xml)
        if person_name is None:
            person_name = extracted.get("person_name")
        if event_type is None:
            event_type = extracted.get("event_type")
        if days_until is None:
            days_until = extracted.get("days_until")

    last_error: Optional[Exception] = None

    for attempt in range(_MAX_LLM_ATTEMPTS):
        try:
            from ...core.llm.haiku_client import get_haiku_client

            client = get_haiku_client()

            # On retry, use a simplified prompt to reduce chance of failure
            prompt_text = context_xml
            if attempt > 0:
                # Build a minimal retry prompt from available fields
                minimal_parts = [f"insight_type: {insight_type}"]
                if person_name:
                    minimal_parts.append(f"person_name: {person_name}")
                if event_type:
                    minimal_parts.append(f"event_type: {event_type}")
                if days_until is not None:
                    minimal_parts.append(f"days_until: {days_until}")
                prompt_text = "\n".join(minimal_parts)

            response = await client.messages.create(
                model=settings.fast_worker_model,
                max_tokens=200,
                temperature=0.5,
                system=system_prompt or _INSIGHT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt_text}],
            )

            text_parts = [
                block.text for block in response.content
                if hasattr(block, "text")
            ]
            if not text_parts:
                last_error = ValueError("empty text blocks")
                continue

            raw = text_parts[0].strip()
            parsed = json.loads(raw)
            return {
                "title": parsed.get("title", fallback_title),
                "content": parsed.get("content", fallback_content),
            }
        except json.JSONDecodeError as exc:
            logger.warning(
                "LLM returned non-JSON for %s insight (attempt %d/%d)",
                insight_type, attempt + 1, _MAX_LLM_ATTEMPTS,
            )
            last_error = exc
        except Exception as exc:
            logger.warning(
                "LLM content generation failed for %s (attempt %d/%d): %s",
                insight_type, attempt + 1, _MAX_LLM_ATTEMPTS, exc,
            )
            last_error = exc

    # All attempts exhausted — use contextual fallback
    logger.warning(
        "All %d LLM attempts failed for %s insight, using contextual fallback: %s",
        _MAX_LLM_ATTEMPTS, insight_type, last_error,
    )
    return _build_contextual_fallback(
        fallback_title=fallback_title,
        fallback_content=fallback_content,
        person_name=person_name,
        event_type=event_type,
        days_until=days_until,
    )


async def generate_summary_text(
    context_xml: str,
    fallback: str = "今天的安排已经为你整理好了。",
) -> str:
    """Generate narrative summary text via Haiku LLM call.

    Returns plain text (not JSON).
    """
    try:
        from ...core.llm.haiku_client import get_haiku_client

        client = get_haiku_client()
        response = await client.messages.create(
            model=settings.fast_worker_model,
            max_tokens=150,
            temperature=0.5,
            system=_SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context_xml}],
        )

        text_parts = [
            block.text for block in response.content
            if hasattr(block, "text")
        ]
        if text_parts:
            return text_parts[0].strip()
        return fallback
    except Exception as e:
        logger.warning("Summary generation failed: %s", e)
        return fallback


async def generate_stress_suggestion(
    context_xml: str,
    fallback_title: str = "最近安排比较密",
    fallback_content: str = "最近事情不少，别忘了好好吃饭休息。有什么能帮你分担的随时说。",
) -> Dict[str, str]:
    """Generate caring stress suggestion via Haiku LLM call."""
    return await generate_insight_content(
        context_xml=context_xml,
        insight_type="stress_suggestion",
        system_prompt=_STRESS_SYSTEM_PROMPT,
        fallback_title=fallback_title,
        fallback_content=fallback_content,
    )
