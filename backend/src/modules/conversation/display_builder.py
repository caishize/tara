"""Unified display_data builder for PendingAction confirmation cards.

Single source of truth for the ``display_data`` dict that Flutter's
PendingActionBubble renders.  All creation paths MUST use
``build_display_data()``.

Output format::

    {
        "title": str,         # Action type label (e.g. "确认购买")
        "description": str,   # Contextual description text
        "details": [          # Structured key-value pairs
            {"label": str, "value": str},
            ...
        ],
    }
"""

from typing import Any, Callable, Dict, List


# ── Action Type → Chinese Title ──────────────────────────────────────

ACTION_DISPLAY_TITLES: Dict[str, str] = {
    "purchase": "确认购买",
    "book_ticket": "确认预订",
    "transfer_money": "确认转账",
    "cancel_booking": "确认取消预订",
    "delete_event": "确认删除事件",
    "send_message": "确认发送消息",
    "send_message_external": "确认发送消息",
    "create_event": "确认创建事件",
    "create_calendar_event": "确认创建日程",
    "reschedule_event": "确认调整日程",
    "suggest_meeting": "建议会面",
    "suggest_greeting": "建议问候",
    "suggest_gift": "建议祝福/礼物",
    "suggest_defer": "建议推迟",
}


# ── Per-type detail builders ─────────────────────────────────────────

_Detail = List[Dict[str, str]]


def _purchase_details(ctx: Dict[str, Any]) -> _Detail:
    return [
        {"label": "商品", "value": ctx.get("item_name", "未知")},
        {"label": "数量", "value": str(ctx.get("quantity", 1))},
        {"label": "价格", "value": f"¥{ctx.get('price', 0)}"},
    ]


def _book_ticket_details(ctx: Dict[str, Any]) -> _Detail:
    return [
        {"label": "出发地", "value": ctx.get("from", "未知")},
        {"label": "目的地", "value": ctx.get("to", "未知")},
        {"label": "日期", "value": ctx.get("date", "未知")},
    ]


def _transfer_money_details(ctx: Dict[str, Any]) -> _Detail:
    details: _Detail = [
        {"label": "收款方", "value": ctx.get("recipient", "未知")},
        {"label": "金额", "value": f"¥{ctx.get('amount', 0)}"},
    ]
    if ctx.get("note"):
        details.append({"label": "备注", "value": ctx["note"]})
    return details


def _cancel_booking_details(ctx: Dict[str, Any]) -> _Detail:
    return [
        {"label": "预订", "value": ctx.get("booking_name", ctx.get("booking_id", "未知"))},
    ]


def _delete_event_details(ctx: Dict[str, Any]) -> _Detail:
    details: _Detail = [
        {"label": "事件", "value": ctx.get("event_name", ctx.get("title", "未知"))},
    ]
    if ctx.get("event_date"):
        details.append({"label": "日期", "value": ctx["event_date"]})
    return details


def _create_event_details(ctx: Dict[str, Any]) -> _Detail:
    details: _Detail = [
        {"label": "事件", "value": ctx.get("title", ctx.get("name", "未知"))},
        {"label": "时间", "value": ctx.get("start", ctx.get("start_time", "未知"))},
    ]
    if ctx.get("location"):
        details.append({"label": "地点", "value": ctx["location"]})
    return details


def _send_message_details(ctx: Dict[str, Any]) -> _Detail:
    content = ctx.get("content", "")
    return [
        {"label": "收件人", "value": ctx.get("recipient", "未知")},
        {"label": "内容", "value": (content[:80] or "未知")},
    ]


def _reschedule_event_details(ctx: Dict[str, Any]) -> _Detail:
    """Handles two patterns: agent (event_name + new_start) and cascade (event_title + impact_type)."""
    details: _Detail = []
    event_name = ctx.get("event_name", ctx.get("event_title", ctx.get("title", "")))
    if event_name:
        label = "影响事件" if ctx.get("impact_type") else "事件"
        details.append({"label": label, "value": event_name})
    if ctx.get("impact_type"):
        details.append({"label": "影响类型", "value": ctx["impact_type"]})
    if ctx.get("detail"):
        details.append({"label": "详情", "value": ctx["detail"]})
    new_time = ctx.get("new_start", ctx.get("new_datetime", ""))
    if new_time:
        details.append({"label": "新时间", "value": new_time})
    if ctx.get("new_end"):
        details.append({"label": "结束时间", "value": ctx["new_end"]})
    return details


def _suggest_social_details(ctx: Dict[str, Any]) -> _Detail:
    """Shared builder for suggest_meeting / suggest_greeting / suggest_gift."""
    details: _Detail = []
    if ctx.get("member_name"):
        details.append({"label": "联系人", "value": ctx["member_name"]})
    if ctx.get("trip_label"):
        details.append({"label": "关联行程", "value": ctx["trip_label"]})
    if ctx.get("date_range"):
        details.append({"label": "出行时间", "value": ctx["date_range"]})
    if ctx.get("location"):
        details.append({"label": "目的地", "value": ctx["location"]})
    if ctx.get("occasion"):
        details.append({"label": "场合", "value": ctx["occasion"]})
    if ctx.get("reason"):
        details.append({"label": "洞察原因", "value": ctx["reason"]})
    if ctx.get("draft_content"):
        details.append({"label": "建议消息", "value": ctx["draft_content"]})
    return details


def _suggest_defer_details(ctx: Dict[str, Any]) -> _Detail:
    details: _Detail = []
    if ctx.get("event_title"):
        details.append({"label": "事件", "value": ctx["event_title"]})
    if ctx.get("suggested_date_display"):
        details.append({"label": "建议日期", "value": ctx["suggested_date_display"]})
    return details


_DETAIL_BUILDERS: Dict[str, Callable[[Dict[str, Any]], _Detail]] = {
    "purchase": _purchase_details,
    "book_ticket": _book_ticket_details,
    "transfer_money": _transfer_money_details,
    "cancel_booking": _cancel_booking_details,
    "delete_event": _delete_event_details,
    "create_event": _create_event_details,
    "create_calendar_event": _create_event_details,
    "send_message": _send_message_details,
    "send_message_external": _send_message_details,
    "reschedule_event": _reschedule_event_details,
    "suggest_meeting": _suggest_social_details,
    "suggest_greeting": _suggest_social_details,
    "suggest_gift": _suggest_social_details,
    "suggest_defer": _suggest_defer_details,
}


# ── Public API ───────────────────────────────────────────────────────


def build_display_data(
    action_type: str,
    context: Dict[str, Any],
    *,
    description: str = "",
) -> Dict[str, Any]:
    """Build structured display_data for a PendingAction confirmation card.

    Parameters
    ----------
    action_type:
        Action type string (matches ActionType enum values or tool names).
    context:
        Dict of fields relevant to this action type.  The builder picks
        what it needs; callers don't have to pre-filter.
    description:
        Optional human-readable description text.  Falls back to
        ``context["reason"]`` when empty.

    Returns
    -------
    dict with keys ``title``, ``description``, ``details``.
    """
    title = ACTION_DISPLAY_TITLES.get(action_type, "确认操作")
    builder = _DETAIL_BUILDERS.get(action_type)
    details = builder(context) if builder else []

    if not description:
        description = context.get("reason", "")

    return {
        "title": title,
        "description": description,
        "details": details,
    }
