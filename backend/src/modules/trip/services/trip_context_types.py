"""
Trip context planner data types and prompt templates.

Extracted from trip_context_planner_service.py for file size management.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date
from dataclasses import dataclass


# PRD 4.2 卡片样式格式
# 支持动态主题：{trip_type} 可以是"出差"、"旅行"、"商旅"等
PRD_CARD_TEMPLATE = """┌─ 📍 {destination}{trip_type} · 智能建议 ─────────────┐
{items}
└─────────────────────────────────────┘"""

PRD_CARD_ITEM_TEMPLATE = "│ {icon} {content:<35}│"


@dataclass
class TripPlanItem:
    """A single item in the trip plan"""
    category: str  # "meeting", "task", "reminder", "suggestion"
    title: str
    description: str
    priority: int  # 1-10
    person: Optional[str] = None
    location: Optional[str] = None
    time_hint: Optional[str] = None
    source_memory_id: Optional[UUID] = None


@dataclass
class TripContextPlan:
    """Comprehensive trip plan generated from memories"""
    destination: str
    trip_start: Optional[date]
    trip_end: Optional[date]
    summary: str  # LLM-generated summary
    items: List[TripPlanItem]
    people_to_meet: List[str]
    tasks: List[str]
    reminders: List[str]
    raw_context: str  # Context string for LLM
    trip_type: str = "出差"  # 动态行程类型：出差/旅行/商旅（由 LLM 意图理解确定）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "destination": self.destination,
            "trip_start": self.trip_start.isoformat() if self.trip_start else None,
            "trip_end": self.trip_end.isoformat() if self.trip_end else None,
            "summary": self.summary,
            "trip_type": self.trip_type,
            "items": [
                {
                    "category": item.category,
                    "title": item.title,
                    "description": item.description,
                    "priority": item.priority,
                    "person": item.person,
                    "location": item.location,
                    "time_hint": item.time_hint,
                }
                for item in self.items
            ],
            "people_to_meet": self.people_to_meet,
            "tasks": self.tasks,
            "reminders": self.reminders,
        }


TRIP_PLANNING_PROMPT = """你是一个智能行程规划助手。根据用户提到的关于目的地的所有信息，生成一个综合的行程规划建议。

【目的地】
{destination}

【行程时间】
{trip_dates}

【用户提到的相关信息】
{memories_context}

【任务】
请根据以上信息，生成一个综合的行程规划，包括：
1. 需要见的人（如果有）🔴 重点：仔细识别所有提到的人名
2. 需要做的事情
3. 提醒事项
4. 综合建议

🔴 **人物识别要求**（非常重要）：
- 从【用户提到的相关信息】和【当前对话上下文】中识别所有人名
- 如果用户说"约思远、孙浩吃饭"，需要识别出两个人：思远、孙浩
- 把所有识别到的人都加入 people_to_meet 数组
- 每个人创建一个 category="meeting" 的 item

【输出格式】
返回JSON格式：
```json
{{
  "summary": "简洁的行程概要（2-3句话）",
  "items": [
    {{
      "category": "meeting/task/reminder/suggestion",
      "title": "事项标题",
      "description": "详细描述",
      "priority": 8,
      "person": "相关人物（如有）",
      "time_hint": "时间建议（如有）"
    }}
  ],
  "people_to_meet": ["人物1", "人物2"],
  "tasks": ["任务1", "任务2"],
  "reminders": ["提醒1", "提醒2"]
}}
```

注意：
- 只返回JSON，不要其他内容
- priority使用1-10分制，越高越重要
- 如果某个字段没有内容，使用空数组[]或null
- 综合考虑所有信息，给出合理的建议
"""
