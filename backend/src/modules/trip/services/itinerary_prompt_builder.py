"""
Itinerary prompt builder - constructs LLM prompts for smart itinerary generation.

Extracted from smart_itinerary_planner.py for file size management.
"""
from typing import Dict, Optional, Any, List
from datetime import date

from .weather_service import WeatherService, WeatherForecast


def build_weather_context(
    weather_service: WeatherService,
    weather_forecast: Optional[WeatherForecast],
    start_date: Optional[date],
    duration_days: int,
) -> str:
    """构建天气预报上下文"""
    if not weather_forecast or not start_date:
        return "暂无天气预报数据，请根据季节特点安排室内外活动"

    lines: List[str] = []
    for day_num in range(1, duration_days + 1):
        context = weather_service.get_itinerary_weather_context(
            weather_forecast, day_num, start_date
        )

        if not context.get("available"):
            lines.append(f"- 第{day_num}天: 无预报数据")
            continue

        condition_desc = context.get("description", "未知")
        temp_high = context.get("temp_high", "?")
        temp_low = context.get("temp_low", "?")
        precip_prob = context.get("precipitation_prob", 0)
        outdoor_friendly = "适合户外" if context.get("is_outdoor_friendly") else "建议室内"
        suggestion = context.get("activity_suggestion", "")

        lines.append(
            f"- 第{day_num}天: {condition_desc}, {temp_low}\u00b0C-{temp_high}\u00b0C, "
            f"降水概率{precip_prob}%, {outdoor_friendly}"
        )
        if suggestion:
            lines.append(f"  建议: {suggestion}")

    # 添加总体摘要
    summary = weather_forecast.get_overall_summary()
    packing = summary.get("packing_suggestions", [])

    weather_str = "\n".join(lines)
    if packing:
        weather_str += f"\n\n携带建议: {', '.join(packing)}"

    return weather_str


def build_search_context(destination_info: Optional[Dict[str, Any]]) -> str:
    """构建搜索结果上下文"""
    if not destination_info:
        return "暂无网络参考资料，请根据专业知识规划"

    # 检查是否有任何搜索结果
    has_content = (
        destination_info.get("attractions")
        or destination_info.get("restaurants")
        or destination_info.get("tips")
        or destination_info.get("sources")
    )
    if not has_content:
        return "暂无网络参考资料，请根据专业知识规划"

    lines: List[str] = []

    # 景点攻略
    attractions = destination_info.get("attractions", [])
    if attractions:
        lines.append("### 景点攻略（来自真实旅行网站）")
        for i, attr in enumerate(attractions[:8], 1):
            title = attr.get("title", "")
            url = attr.get("url", "")
            platform = attr.get("platform", "")
            content = attr.get("content", "")[:150] if attr.get("content") else ""
            lines.append(f"{i}. **{title}** [{platform}]")
            if url:
                lines.append(f"   链接: {url}")
            if content:
                lines.append(f"   摘要: {content}...")

    # 美食推荐
    restaurants = destination_info.get("restaurants", [])
    if restaurants:
        lines.append("\n### 美食推荐（来自点评网站）")
        for i, rest in enumerate(restaurants[:5], 1):
            title = rest.get("title", "")
            url = rest.get("source", "")
            snippet = rest.get("snippet", "")[:100] if rest.get("snippet") else ""
            lines.append(f"{i}. **{title}**")
            if url:
                lines.append(f"   链接: {url}")
            if snippet:
                lines.append(f"   推荐: {snippet}...")

    # 避坑提示
    tips = destination_info.get("tips", [])
    if tips:
        lines.append("\n### 避坑提示")
        for tip in tips[:3]:
            title = tip.get("title", "")
            content = tip.get("content", "")[:100] if tip.get("content") else ""
            lines.append(f"- **{title}**: {content}...")

    # 来源ID映射（供 LLM 引用）
    sources = destination_info.get("sources", [])
    if sources:
        lines.append("\n### 来源ID映射（请在 sources 和 source_refs 中使用这些真实来源）")
        for src in sources:
            src_id = src.get("id", 0)
            src_title = src.get("title", "")
            src_platform = src.get("platform", "")
            src_url = src.get("url", "")
            lines.append(f"- ID {src_id}: {src_title} ({src_platform}) - {src_url}")

    return "\n".join(lines)


def build_smart_prompt(
    destination: str,
    duration_days: int,
    style_config: Dict[str, Any],
    family_constraints: Dict[str, Any],
    budget: Optional[float],
    preferences: Optional[Dict[str, Any]],
    weather_str: str,
    search_context: str,
) -> str:
    """构建智能行程生成的 LLM Prompt"""

    # 构建家庭约束描述
    family_desc: List[str] = []
    nap_enabled = family_constraints.get("nap_time_enabled", True)
    nap_start = family_constraints.get("nap_time_start", "14:00")
    nap_end = family_constraints.get("nap_time_end", "16:00")

    if family_constraints["has_toddlers"]:
        if nap_enabled:
            family_desc.append(
                f"有0-3岁婴幼儿，需要午休时间({nap_start}-{nap_end})，避免人多拥挤场所"
            )
        else:
            family_desc.append("有0-3岁婴幼儿，避免人多拥挤场所，行程需要宽松")
    if family_constraints["has_young_children"]:
        family_desc.append("有4-6岁儿童，推荐儿童友好景点，每天步行不超过8km")
    if family_constraints["has_elderly"]:
        family_desc.append("有65岁以上老人，避免爬山和长距离步行，需要休息时间")
    if family_constraints["needs_nap_time"] and nap_enabled:
        family_desc.append(f"需要在{nap_start}-{nap_end}安排午休或轻松活动")

    family_str = (
        "\n".join([f"- {d}" for d in family_desc]) if family_desc else "无特殊约束"
    )

    prompt = f"""你是一位资深旅行规划师，拥有10年以上的旅行策划经验。
请根据以下真实的旅行攻略和用户需求，生成专业级的详细行程。

## 基本信息
- 目的地: {destination}
- 行程天数: {duration_days}天{duration_days-1}夜
- 总预算: {budget or '不限'}元
- 行程风格: {style_config['description']}

## 家庭约束
{family_str}

## 风格要求
{chr(10).join([f'- {c}' for c in style_config['constraints']])}

## 时间安排
- 每日开始时间: {style_config['wake_time']}
- 每日结束时间: {style_config['end_time']}
- 每日最大步行: {family_constraints['max_walking_km']}km
- 每日活动时长: {family_constraints['activity_hours']}小时

## 天气预报
{weather_str}

## 【重要】参考资料（来自真实旅行攻略网站）
{search_context}

## 输出要求

**【最重要】**: 必须使用**具体的景点/餐厅名称和地址**，禁止使用泛化表述。

请生成**简洁**的JSON响应（只包含必要字段）：

```json
{{
  "daily_schedules": [
    {{
      "day": 1,
      "date_label": "第1天",
      "theme": "西湖经典游",
      "summary": "游览西湖北线核心景点",
      "activities": [
        {{
          "time": "09:00",
          "duration_minutes": 90,
          "activity_type": "attraction",
          "title": "断桥残雪",
          "location": {{
            "name": "断桥",
            "address": "杭州市西湖区北山街84号",
            "coordinates": {{"lat": 30.259, "lng": 120.152}}
          }},
          "description": "西湖十景之一",
          "estimated_cost": 0,
          "tips": "建议8点前到，人少拍照好"
        }},
        {{
          "time": "12:00",
          "duration_minutes": 90,
          "activity_type": "meal",
          "title": "楼外楼(孤山店)",
          "location": {{
            "name": "楼外楼",
            "address": "杭州市西湖区孤山路30号"
          }},
          "description": "百年老字号杭帮菜",
          "estimated_cost": 150,
          "tips": "招牌西湖醋鱼，人均100-150元"
        }}
      ]
    }}
  ],
  "sources": [
    {{"id": 1, "platform": "马蜂窝", "title": "攻略标题", "url": "https://..."}}
  ],
  "budget_total": 数字,
  "tips": ["小贴士1", "小贴士2"]
}}
```

## 注意
1. 每天安排3-5个活动（景点+餐饮）
2. 使用具体景点名和地址
3. 合理安排用餐时间
4. 简洁输出，不要冗余字段

请直接输出JSON。"""

    return prompt
