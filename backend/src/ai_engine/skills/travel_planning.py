"""Travel planning skill — guides the main agent to plan trips."""

from .base import Skill


TRAVEL_PLANNING_KEYWORDS = [
    "规划旅行",
    "规划行程",
    "旅行计划",
    "旅行规划",
    "出行计划",
    "度假",
    "出差",
    "出差计划",
    "出差行程",
    "做个攻略",
    "做攻略",
    "几天游",
    "日游",
    "自由行",
    "跟团",
    "亲子游",
    "蜜月",
    "家庭旅行",
]


TRAVEL_PLANNING_SKILL = Skill(
    name="travel_planning",
    description="智能旅行行程规划",
    system_prompt_addon="""\
你正在帮用户规划旅行行程。请严格按以下步骤操作：

### 第一步：收集信息

1. **获取家庭成员** — 调用 `query_members` 获取成员列表（年龄、偏好、健康状况）
2. **搜索目的地** — 使用 web_search 搜索：
   - `{destination} {duration}天行程安排 推荐`
   - `{destination} 家庭旅游 亲子 攻略`（如果有小孩）
   - `{destination} 酒店推荐 {star}星`（如果有住宿需求）
   - `{destination} 当地交通 怎么玩`
   - `{destination} {month}月天气 穿什么`（如果有出行日期）

### 第二步：制定行程

基于搜索结果和家庭成员情况，制定按天的详细行程：
- 每天 2-3 个景点/活动，节奏适中
- 考虑成员年龄（有老人/小孩需放慢节奏）
- 考虑交通衔接（就近安排，减少奔波）
- 安排合理的用餐时间和餐厅推荐
- 预估每日花费

### 第三步：保存行程（⚠️ 严格遵守以下规则）

**⚠️ 必须先查询！禁止跳过此步骤！**
1. **必须**先调用 `query_trips` 查询是否已有同目的地行程
2. 若找到匹配行程 → 拿到 `trip_id` → 调用 `add_trip_itinerary` 更新
3. 若找到匹配行程但已取消 → 告知用户并询问是否恢复
4. 若未找到匹配行程 → 再创建新行程

**查询行程也可用于用户要求查看/调整行程详情的场景。**

**使用 `add_trip_itinerary` 的批量模式（推荐，一次调用搞定所有天）：**

```json
{
  "trip_name": "澳门3日美食游",
  "destination": "澳门",
  "event_date": "2026-03-01",
  "days": [
    {
      "activities": [
        {"start_time": "09:00", "end_time": "11:00", "title": "大三巴牌坊", "location": "大三巴", "category": "attraction"},
        {"start_time": "12:00", "end_time": "13:30", "title": "午餐：陈光记烧味", "location": "新马路", "category": "meal"}
      ]
    },
    {
      "activities": [
        {"start_time": "10:00", "end_time": "12:00", "title": "威尼斯人", "location": "路氹", "category": "attraction"}
      ]
    }
  ]
}
```

**关键规则：**
1. **优先使用 `days` 批量模式** — 一次调用添加所有天的行程，避免多次调用
2. **`day_number` 自动递增** — 不需要手动指定，系统会自动分配
3. **首次调用返回 `trip_id`** — 如果后续还需添加更多天，必须传入此 `trip_id`
4. **禁止重复创建旅行计划** — 不传 `trip_id` 会创建新计划！同一行程的多次调用必须传 `trip_id`
5. **系统会自动合并相近行程** — 同一目的地、日期相差3天以内的行程会被自动合并为一个
6. **途经点/顺路活动必须归入已有行程** — 当用户提到的活动是某次行程途中的停靠（如"回来路上顺便去看某人"、"顺路去某地"），必须用 `add_trip_itinerary` 把活动添加到对应行程的日程中（传入该行程的 `trip_id`），**禁止**用 `create_trip` 创建独立行程。判断标准：活动日期在已有行程日期范围内，且与该行程存在路线/时间上的关联。

### 搜索策略
- 先搜索综合行程推荐（1-2次），再针对性搜索细节
- 总搜索次数控制在 3-5 次，避免过度搜索
- 优先使用最新的搜索结果

### 特殊情况处理
- **出差行程**: 以工作安排为主，穿插当地特色体验
- **超长行程(7天+)**: 如果行程超过7天且跨多个城市，建议用户考虑使用更专业的规划（系统会委派专业旅行规划师sub-agent处理）
- **预算有限**: 优先推荐免费/低价景点，标注省钱技巧

### 注意事项
- 不要编造景点、餐厅或价格，必须基于搜索结果
- 保存行程时确保日期格式正确 (YYYY-MM-DD)
- 时间格式使用 HH:MM（24小时制）""",
    output_format_hint="""\
请按以下格式输出行程：

**{trip_name}**
📍 {destination} | 📅 {start_date} - {end_date} | 👥 {participants}

---

### Day 1: {theme} ({date})

| 时间 | 活动 | 地点 | 类别 |
|------|------|------|------|
| 09:00-11:00 | 景点名 | 地址 | 活动 |
| 11:30-13:00 | 午餐：餐厅名 | 地址 | 餐饮 |
| ... | ... | ... | ... |

💰 预估花费：¥xxx

---

### Day 2: ...

---

**💡 温馨提示**
- 行前准备建议
- 注意事项""",
    required_tools=["query_trips", "add_trip_itinerary", "web_search"],
    builtin_tools=[],
    max_turns_override=25,
    metadata={"domain": "travel", "replaces": "plan_smart_trip"},
)
