"""Tool summary generator -- produces Layer 1 summaries and Layer 2 key_results.

Each tool type has a handler that returns (summary_text, key_results_dict).
"""

from typing import Any, Dict, Tuple

# Preview limits for Layer 2 key_results
MAX_ITINERARY_PREVIEW_ITEMS = 7
MAX_MEMBER_PREVIEW_ITEMS = 10
MAX_EVENT_PREVIEW_ITEMS = 7
MAX_BOOKING_PREVIEW_ITEMS = 5
MAX_RECOMMENDATION_PREVIEW_ITEMS = 5


def generate_summary_for_tool(
    tool_name: str, result: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    """Generate a summary and key results for a tool execution."""
    success = result.get("success", False)
    data = result

    if not success:
        error = result.get("message") or result.get("error") or "未知错误"
        return f"执行失败: {error[:100]}", {"error": error}

    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is not None:
        return handler(data)
    return _summarize_default(tool_name, data)


# --------------- Individual tool summarizers ---------------


def _summarize_recommend_gift(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    recommendations = data.get("recommendations", [])
    count = len(recommendations)
    if count > 0:
        first = recommendations[0]
        name = first.get("name", "礼物")
        price = first.get("price", "")
        price_str = f"(¥{price})" if price else ""
        summary = f"推荐了{count}个礼物，首选: {name}{price_str}"
        key_results = {
            "total_count": count,
            "recommendations": [
                {
                    "name": r.get("name"),
                    "price": r.get("price"),
                    "reason": r.get("reason", "")[:150],
                    "category": r.get("category"),
                    "rating": r.get("rating"),
                }
                for r in recommendations[:MAX_RECOMMENDATION_PREVIEW_ITEMS]
            ],
        }
        return summary, key_results
    return "已生成礼物推荐（无结果）", {}


def _summarize_add_important_date(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    title = data.get("title", "日期")
    date_val = data.get("date", "")
    summary = f"已添加重要日期: {title} ({date_val})"
    key_results = {
        "title": title,
        "date": date_val,
        "type": data.get("type"),
        "reminder": data.get("reminder"),
    }
    return summary, key_results


def _summarize_query_upcoming_dates(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    dates = data.get("dates", [])
    summary = f"查询到{len(dates)}个近期日期"
    key_results = {
        "count": len(dates),
        "dates": [
            {
                "title": d.get("title"),
                "date": d.get("date"),
                "type": d.get("type"),
                "days_until": d.get("days_until"),
            }
            for d in dates[:MAX_EVENT_PREVIEW_ITEMS]
        ],
    }
    return summary, key_results


def _summarize_add_member(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    name = data.get("name", "成员")
    summary = f"已添加成员: {name}"
    key_results = {
        "id": data.get("id"),
        "name": name,
        "nickname": data.get("nickname"),
        "relationship": data.get("relationship"),
        "relation_type": data.get("relation_type"),
        "age": data.get("age"),
        "gender": data.get("gender"),
        "date_of_birth": data.get("date_of_birth"),
        "occupation": data.get("occupation"),
    }
    return summary, key_results


def _summarize_update_member_info(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    member_name = data.get("member_name", data.get("name", "成员"))
    updated_fields = data.get("updated_fields", [])
    summary = f"已更新 {member_name} 的信息"
    if updated_fields:
        summary += f"（{', '.join(updated_fields[:3])}）"
    key_results = {
        "member_id": data.get("member_id"),
        "member_name": member_name,
        "updated_fields": updated_fields,
        "new_values": {
            k: v
            for k, v in data.items()
            if k
            not in ("member_id", "member_name", "updated_fields", "success")
            and v is not None
        },
    }
    return summary, key_results


def _summarize_query_members(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    members = data.get("members", [])
    summary = f"查询到{len(members)}位家庭成员"
    key_results = {
        "count": len(members),
        "_showing": min(MAX_MEMBER_PREVIEW_ITEMS, len(members)),
        "members": [
            {
                "id": m.get("id"),
                "name": m.get("name", ""),
                "nickname": m.get("nickname"),
                "relation_type": m.get("relation_type"),
                "age": m.get("age"),
                "gender": m.get("gender"),
                "date_of_birth": m.get("date_of_birth"),
                "health_notes": (
                    (m.get("health_notes") or "")[:200]
                    if m.get("health_notes")
                    else None
                ),
                "preferences": (
                    (m.get("preferences") or "")[:150]
                    if m.get("preferences")
                    else None
                ),
                "occupation": m.get("occupation"),
            }
            for m in members[:MAX_MEMBER_PREVIEW_ITEMS]
        ],
    }
    return summary, key_results


def _summarize_create_task(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    title = data.get("title", "任务")
    summary = f"已创建任务: {title}"
    key_results = {
        "id": data.get("id"),
        "title": title,
        "status": data.get("status", "pending"),
        "due_date": data.get("due_date"),
        "priority": data.get("priority"),
    }
    return summary, key_results


def _summarize_record_favor(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    contact = data.get("contact_name", "")
    direction = "收到" if data.get("direction") == "receive" else "送出"
    summary = f"已记录{direction}人情: {contact}"
    key_results = {
        "id": data.get("id"),
        "contact": contact,
        "direction": direction,
        "event_type": data.get("event_type"),
        "description": data.get("description", "")[:100],
        "amount": data.get("amount"),
        "weight": data.get("weight"),
    }
    return summary, key_results


def _summarize_update_trip(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    trip_name = data.get("trip_name", data.get("name", "行程"))
    trip_id = data.get("trip_id", data.get("id"))
    summary = f"已更新行程计划: {trip_name}"

    activities_count = None
    itinerary = data.get("itinerary")
    if isinstance(itinerary, list):
        activities_count = len(itinerary)
    elif isinstance(itinerary, dict):
        daily_plans = itinerary.get("daily_plans", [])
        if isinstance(daily_plans, list):
            activities_count = sum(
                len(day.get("activities", []))
                if isinstance(day, dict)
                else 0
                for day in daily_plans
            )

    key_results = {
        "trip_id": trip_id,
        "trip_name": trip_name,
        "destination": data.get("destination"),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "participants_count": (
            len(data.get("participants", []))
            if data.get("participants")
            else None
        ),
        "activities_count": activities_count,
    }
    return summary, key_results


def _summarize_create_trip(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    event_title = data.get("title", "活动")
    event_id = data.get("event_id", data.get("id"))
    summary = f"已创建旅行计划: {event_title}"
    key_results = {
        "event_id": event_id,
        "title": event_title,
        "date": data.get("date"),
        "time": data.get("time"),
        "location": data.get("location"),
        "type": data.get("type"),
    }
    return summary, key_results


def _summarize_add_trip_itinerary(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    items = data.get("items", data.get("itinerary", []))
    itinerary_count = len(items)
    trip_name = data.get("trip_name", "行程")
    summary = f"已添加{itinerary_count}个行程项目到 {trip_name}"
    key_results = {
        "trip_id": data.get("trip_id"),
        "trip_name": trip_name,
        "items_added": itinerary_count,
        "first_item": items[0] if items else None,
    }
    return summary, key_results


def _summarize_get_member_details(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    name = data.get("name", data.get("nickname", "成员"))
    summary = f"查询到 {name} 的详细信息"
    key_results = {
        "id": data.get("id"),
        "name": data.get("name"),
        "nickname": data.get("nickname"),
        "relation_type": data.get("relation_type"),
        "age": data.get("age"),
        "gender": data.get("gender"),
        "occupation": data.get("occupation"),
        "health_notes": (
            (data.get("health_notes") or "")[:200]
            if data.get("health_notes")
            else None
        ),
        "preferences": (
            (data.get("preferences") or "")[:150]
            if data.get("preferences")
            else None
        ),
        "blood_type": data.get("blood_type"),
    }
    return summary, key_results


def _summarize_delete_member(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    name = data.get("member_name", data.get("name", "成员"))
    summary = f"已删除成员: {name}"
    key_results = {
        "member_id": data.get("member_id", data.get("id")),
        "member_name": name,
        "action": "deleted",
    }
    return summary, key_results


def _summarize_query_external_calendar(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    events = data.get("events", [])
    source = data.get("source", "外部日历")
    summary = f"从{source}查询到{len(events)}个日历事件"
    key_results = {
        "source": source,
        "count": len(events),
        "events": [
            {
                "title": e.get("title", e.get("summary")),
                "start": e.get("start"),
                "end": e.get("end"),
                "location": e.get("location"),
            }
            for e in events[:MAX_EVENT_PREVIEW_ITEMS]
        ],
    }
    return summary, key_results


def _summarize_query_trip_bookings(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    bookings = data.get("bookings", [])
    summary = f"查询到{len(bookings)}个旅行预订"
    key_results = {
        "count": len(bookings),
        "bookings": [
            {
                "type": b.get("type"),
                "confirmation_code": b.get("confirmation_code"),
                "date": b.get("date"),
                "destination": b.get("destination"),
                "status": b.get("status"),
            }
            for b in bookings[:MAX_BOOKING_PREVIEW_ITEMS]
        ],
    }
    return summary, key_results


def _summarize_set_reminder(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    reminder_time = data.get("time", data.get("reminder_time", ""))
    content = data.get("content", data.get("message", "提醒"))
    if len(content) > 50:
        summary = f"已设置提醒: {content[:50]}..."[:60]
    else:
        summary = f"已设置提醒: {content}"
    key_results = {
        "id": data.get("id"),
        "time": reminder_time,
        "content": content[:100],
        "recurring": data.get("recurring"),
    }
    return summary, key_results


def _summarize_view_tool_details(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    exec_id = data.get("execution_id", "")
    viewed_tool = data.get("tool_name", "工具")
    summary = f"已获取 {viewed_tool} 的执行详情 (#{exec_id})"
    key_results = {
        "execution_id": exec_id,
        "tool_name": viewed_tool,
        "status": data.get("status"),
        "has_full_result": bool(data.get("full_result")),
        "has_logs": bool(data.get("logs")),
    }
    return summary, key_results


def _summarize_query_trips(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    trips = data.get("trips", [])
    count = len(trips)
    summary = f"查询到{count}个旅行计划"
    key_results = {
        "count": count,
        "trips": [
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "destination": t.get("destination") or t.get("location"),
                "start_date": t.get("start_date"),
                "end_date": t.get("end_date"),
                "status": t.get("status"),
            }
            for t in trips[:MAX_ITINERARY_PREVIEW_ITEMS]
        ],
    }
    return summary, key_results


def _summarize_merge_trips(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    merged_count = int(data.get("merged_count", 0) or 0)
    primary_trip_id = data.get("primary_trip_id")
    summary = f"已合并{merged_count}个重复行程"
    key_results = {
        "primary_trip_id": primary_trip_id,
        "merged_count": merged_count,
        "merged_trip_ids": data.get("merged_trip_ids", []),
    }
    return summary, key_results


def _summarize_search_memory(
    data: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    memories = data.get("memories", [])
    query = data.get("query", "")
    count = len(memories)
    summary = f"查询到{count}条相关记忆"
    if query:
        summary += f" (关键词: {query[:30]})"
    key_results = {
        "query": query,
        "count": count,
        "memories": [
            {
                "content": m.get("content", "")[:150],
                "category": m.get("category"),
                "relevance": m.get("relevance_score"),
            }
            for m in memories[:MAX_EVENT_PREVIEW_ITEMS]
        ],
    }
    return summary, key_results


def _summarize_save_memory(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    content = data.get("content", "")
    category = data.get("category", "general")
    summary = f"已保存记忆 [{category}]: {content[:50]}"
    key_results = {
        "id": data.get("id"),
        "category": category,
        "content": content[:200],
    }
    return summary, key_results


def _summarize_default(
    tool_name: str, data: Dict[str, Any]
) -> Tuple[str, Dict[str, Any]]:
    summary = f"工具 {tool_name} 执行成功"

    if isinstance(data, dict):
        key_results: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str):
                key_results[key] = value[:200] if len(value) > 200 else value
            elif isinstance(value, (int, float, bool, type(None))):
                key_results[key] = value
            elif isinstance(value, list):
                key_results[key] = {
                    "_count": len(value),
                    "_sample": value[:3] if len(value) > 3 else value,
                }
            elif isinstance(value, dict):
                key_results[key] = {"_keys": list(value.keys())[:5]}
        return summary, key_results

    return summary, {"result": str(data)[:500] if data else None}


# Handler dispatch table
_TOOL_HANDLERS = {
    "recommend_gift": _summarize_recommend_gift,
    "add_important_date": _summarize_add_important_date,
    "query_upcoming_dates": _summarize_query_upcoming_dates,
    "add_member": _summarize_add_member,
    "update_member_info": _summarize_update_member_info,
    "query_members": _summarize_query_members,
    "create_task": _summarize_create_task,
    "record_favor": _summarize_record_favor,
    "update_trip": _summarize_update_trip,
    "create_trip": _summarize_create_trip,
    "add_trip_itinerary": _summarize_add_trip_itinerary,
    "get_member_details": _summarize_get_member_details,
    "delete_member": _summarize_delete_member,
    "query_external_calendar": _summarize_query_external_calendar,
    "query_trip_bookings": _summarize_query_trip_bookings,
    "set_reminder": _summarize_set_reminder,
    "view_tool_details": _summarize_view_tool_details,
    "query_trips": _summarize_query_trips,
    "merge_trips": _summarize_merge_trips,
    "search_memory": _summarize_search_memory,
    "save_memory": _summarize_save_memory,
}
