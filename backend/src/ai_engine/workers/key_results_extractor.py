"""Key results extraction for tool execution display.

Pure functions that transform raw tool results into structured
key-value pairs for the mobile ``_buildKeyResultsDisplay`` widget.
"""

from typing import Any, Dict, Optional


def extract_key_results(
    tool_name: str,
    result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Extract structured key results from a tool's return dict.

    Returns a flat dict of display-friendly key-value pairs that the
    mobile ``_buildKeyResultsDisplay`` widget can render directly.
    Each value is either a ``str`` or a short ``list`` of strings.

    Returns None when no meaningful extraction can be made.
    """
    if not result.get("success", True):
        return None

    if tool_name == "query_trips":
        trips = result.get("trips")
        if not isinstance(trips, list) or not trips:
            return None
        return {
            "行程列表": [
                f"{t.get('title', t.get('location', '未知'))} · "
                f"{t.get('start_date', '待定')} · {t.get('status', '')}"
                for t in trips[:5]
            ],
        }

    if tool_name == "search_memory":
        memories = result.get("memories")
        if not isinstance(memories, list) or not memories:
            return None
        return {
            "相关记忆": [
                f"[{m.get('memory_type', '记忆')}] "
                f"{m.get('summary') or (m.get('content', '')[:60])}"
                for m in memories[:5]
            ],
        }

    if tool_name == "query_tasks":
        tasks = result.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            return None
        return {
            "任务列表": [
                f"{t.get('title', '任务')} · "
                f"{t.get('status', '')} · {t.get('due_date', '无截止')}"
                for t in tasks[:5]
            ],
        }

    if tool_name == "add_trip_itinerary":
        out: Dict[str, Any] = {}
        trip_name = result.get("trip_name", "")
        destination = result.get("destination", "")
        days_saved = result.get("days_saved")
        if trip_name:
            out["行程"] = trip_name
        if destination:
            out["目的地"] = destination
        if isinstance(days_saved, int) and days_saved > 0:
            out["新增天数"] = str(days_saved)
        return out or None

    if tool_name == "web_search":
        results = result.get("results")
        query = result.get("query", "")
        if not isinstance(results, list) or not results:
            return None
        out: Dict[str, Any] = {}
        if query:
            out["搜索词"] = query
        out["搜索结果"] = [
            f"{r.get('title', '无标题')} · {(r.get('content', '') or '')[:60]}"
            for r in results[:5]
            if r.get("title")
        ]
        return out or None

    return None
