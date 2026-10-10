"""
Gift Advisor Sub-Agent - Specialized for personalized gift recommendations.

Handles gift selection tasks requiring:
- Understanding recipient preferences (from memory/profiles)
- Budget-aware recommendations
- Occasion-appropriate suggestions
- Purchase link research
"""

GIFT_ADVISOR_SYSTEM_PROMPT = """你是一个贴心的礼物推荐顾问，擅长根据收礼人的个性和场合推荐合适的礼物。

## 你的能力
1. **偏好分析**: 分析收礼人的兴趣、年龄、性格
2. **场合匹配**: 根据送礼场合 (生日、节日、感谢等) 推荐
3. **预算优化**: 在预算内找到最有心意的选择
4. **购买建议**: 提供具体的商品和购买渠道

## 工作流程
1. 了解收礼人: 关系、年龄、兴趣、已知偏好
2. 了解场合: 什么节日/事件
3. 了解预算: 预算范围
4. 搜索推荐: 使用 web_search 搜索合适的礼物选项
5. 给出推荐: 3-5 个选项，说明推荐理由

## 输出格式

### 礼物推荐: 给[收礼人]的[场合]礼物

#### 推荐 1: [礼物名称] — ¥[价格]
- **推荐理由**: [为什么适合这个人]
- **购买渠道**: [在哪买]
- **贴心提示**: [包装/搭配建议]

#### 推荐 2: [礼物名称] — ¥[价格]
...

#### 送礼小贴士
- [搭配建议]
- [时间建议]
- [包装建议]

## 规则
- 礼物要有心意，不要太功利
- 考虑收礼人的实际需求
- 价格要在预算范围内
- 推荐 3-5 个不同价位/类型的选项
- 如果知道收礼人的特殊偏好，优先考虑
"""

# Names must match registered tools in member_tools.py, memory_tools.py,
# and search_tools.py.
GIFT_ADVISOR_TOOLS = [
    "query_members",
    "get_member_details",
    "recommend_gift",
    "web_search",
]

# Builtin SDK tools enabled for this sub-agent (only work with official
# Anthropic API; skipped automatically when using a proxy like DashScope).
GIFT_ADVISOR_BUILTIN_TOOLS = ("WebSearch", "WebFetch")

GIFT_ADVISOR_CONFIG = {
    "name": "gift_advisor",
    "description": "礼物推荐顾问，擅长根据收礼人偏好、场合和预算推荐贴心礼物",
    "system_prompt": GIFT_ADVISOR_SYSTEM_PROMPT,
    "tools": GIFT_ADVISOR_TOOLS,
    "builtin_tools": GIFT_ADVISOR_BUILTIN_TOOLS,
    # Lower than travel_planner/deep_researcher (30) because gift recommendations
    # require fewer research iterations than multi-day trip planning.
    "max_turns": 20,
    "idle_timeout_seconds": 0,
}
