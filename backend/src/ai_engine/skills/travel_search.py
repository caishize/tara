"""Travel search skill — guides the main agent to search destination info."""

from .base import Skill


TRAVEL_SEARCH_KEYWORDS = [
    "旅游信息",
    "旅游攻略",
    "景点",
    "美食推荐",
    "避坑",
    "出行攻略",
    "好玩的",
    "哪里好玩",
    "怎么玩",
    "玩什么",
    "吃什么",
    "旅行攻略",
]


TRAVEL_SEARCH_SKILL = Skill(
    name="travel_search",
    description="目的地旅游信息搜索",
    system_prompt_addon="""\
你正在帮用户搜索目的地旅游信息。请按以下步骤操作：

### 工作流程

1. **搜索目的地信息**
   使用 web_search 工具搜索以下内容（根据用户需求选择性搜索）：
   - `{destination} 必去景点 推荐 2025`
   - `{destination} 美食 特色小吃 推荐`
   - `{destination} 交通攻略 怎么去`
   - `{destination} 旅游避坑指南`
   - `{destination} 天气 最佳旅游季节`

2. **获取家庭成员信息**（如果相关）
   调用 `query_members` 了解成员年龄、偏好，以便给出针对性建议。

3. **整理并输出**
   将搜索结果整理为结构化的中文回复。

### 搜索策略
- 优先搜索最新信息（加上年份关键词）
- 每个类别搜索 1-2 次即可，不要过度搜索
- 如果用户只问某一类信息（如美食），只搜索该类别
- 搜索结果中提取关键信息，去掉广告和无关内容

### 注意事项
- 不要编造景点或餐厅名称，必须基于搜索结果
- 给出实用的建议（价格、开放时间、交通方式）
- 如果家庭有老人或小孩，特别标注适合度""",
    output_format_hint="""\
请按以下格式组织回复：

**{destination} 旅游攻略**

🏞 **必去景点**
1. 景点名 — 简介 | 门票/开放时间 | 适合人群

🍜 **美食推荐**
1. 美食名 — 推荐餐厅/地点 | 人均价格

🚗 **交通指南**
- 如何到达 / 市内交通建议

⚠️ **避坑提醒**
- 实用的避坑建议

🌤 **最佳旅游时间**
- 气候特点和推荐季节""",
    required_tools=["web_search"],
    builtin_tools=[],
    metadata={"domain": "travel", "replaces": "search_travel_info"},
)
