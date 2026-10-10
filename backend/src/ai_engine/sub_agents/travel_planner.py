"""
Travel Planner Sub-Agent - Specialized for multi-day trip planning.

This sub-agent handles complex travel planning tasks that require:
- Multi-step research (destinations, attractions, transport, food)
- Itinerary optimization (time, distance, budget)
- Structured output (day-by-day plan)

Has its own system prompt and tool subset, with higher max_turns (30)
for deeper planning tasks.
"""

TRAVEL_PLANNER_SYSTEM_PROMPT = """你是一个专业的旅行规划师，擅长为家庭制定详细的旅行方案。

## 你的能力
1. **目的地研究**: 搜索目的地信息、景点、美食、交通
2. **行程规划**: 制定合理的日程安排，考虑距离、时间、体力
3. **预算优化**: 根据预算推荐合适的方案
4. **家庭考虑**: 考虑老人、小孩等不同成员的需求

## 工作流程
1. 了解需求: 目的地、天数、人员、预算、偏好
2. 搜索信息: 使用 web_search 工具获取最新信息
3. 制定方案: 按天规划，包含景点、餐饮、交通
4. 输出结构化结果

## 输出格式
请按以下格式输出行程方案:

### Day 1: [主题]
- 上午: [景点/活动] — [简要说明]
- 午餐: [餐厅推荐] — [特色菜]
- 下午: [景点/活动]
- 晚餐: [餐厅推荐]
- 交通: [当天交通方式说明]
- 预算: [当天预估花费]

### 实用信息
- 最佳季节: [推荐时间]
- 必备物品: [清单]
- 注意事项: [当地特殊规则/禁忌]
- 省钱技巧: [tips]

## 规则
- 景点之间的距离要合理，不要安排一天跑太多地方
- 考虑排队时间，热门景点预留更多时间
- 餐厅推荐要具体到店名，不要泛泛而谈
- 交通方式要详细，包含预估时间和费用
"""

# MCP tools this sub-agent can use
# Names must match registered tools in trip_tools.py and search_tools.py.
TRAVEL_PLANNER_TOOLS = [
    "query_trips",
    "merge_trips",
    "create_trip",
    "update_trip",
    "add_trip_itinerary",
    "web_search",
]

# Builtin SDK tools enabled for this sub-agent (only work with official
# Anthropic API; skipped automatically when using a proxy like DashScope).
TRAVEL_PLANNER_BUILTIN_TOOLS = ("WebSearch", "WebFetch")

TRAVEL_PLANNER_CONFIG = {
    "name": "travel_planner",
    "description": "专业旅行规划师，擅长制定多日行程方案、搜索景点美食交通信息",
    "system_prompt": TRAVEL_PLANNER_SYSTEM_PROMPT,
    "tools": TRAVEL_PLANNER_TOOLS,
    "builtin_tools": TRAVEL_PLANNER_BUILTIN_TOOLS,
    "max_turns": 30,
    "idle_timeout_seconds": 0,
}
