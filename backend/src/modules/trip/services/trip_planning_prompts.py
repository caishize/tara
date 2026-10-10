"""
Travel Planning Prompts Mixin - LLM prompt construction for itinerary generation.

Contains the prompt templates for both leisure trips and business trips.
"""

from typing import Dict, Any, Optional
from datetime import date

from .trip_planning_constants import TripStyle, TRAVEL_STYLE_PROMPT_MAP


class TripPromptMixin:
    """Mixin for LLM prompt building methods."""

    def _build_itinerary_prompt(
        self,
        destination: str,
        duration_days: int,
        start_date: date,
        user_profile: Dict[str, Any],
        trip_constraints: Dict[str, Any],
        real_time_info: Dict[str, Any],
        user_requirements: Optional[str],
        style: Optional[TripStyle],
        hotel_requirements: Optional[Dict[str, Any]] = None,
        needs_hotel: bool = True,
    ) -> str:
        """构建个性化行程生成提示"""

        # 用户画像摘要
        profile_summary = user_profile.get("summary", "暂无用户画像")

        # 酒店需求（仅当需要住宿时显示）
        hotel_info = ""
        if needs_hotel and hotel_requirements:
            hotel_parts = []
            if hotel_requirements.get("room_count"):
                hotel_parts.append(f"需要{hotel_requirements['room_count']}间房")
            if hotel_requirements.get("room_type"):
                hotel_parts.append(f"房型: {hotel_requirements['room_type']}")
            if hotel_requirements.get("special_needs"):
                hotel_parts.append(f"特殊需求: {', '.join(hotel_requirements['special_needs'])}")
            if hotel_parts:
                hotel_info = "\n## 🏨 酒店需求\n" + "\n".join(f"- {p}" for p in hotel_parts)

        # 约束摘要
        constraints_summary = trip_constraints.get("summary", "无特殊约束")

        # 实时信息
        real_time_data = real_time_info.get("search_results", {})
        attractions_info = ""
        if real_time_data.get("attractions"):
            attractions_info = "\n".join([
                f"- {a['name']}: {a.get('ticket_price', '价格未知')}, {a.get('tips', '')}"
                for a in real_time_data.get("attractions", [])[:5]
            ])

        food_info = ""
        if real_time_data.get("food"):
            food_info = "\n".join([
                f"- {f['name']}: {f.get('location', '')}, {f.get('price_range', '')}"
                for f in real_time_data.get("food", [])[:5]
            ])

        # 酒店推荐信息（仅当需要住宿时显示）
        hotels_info = ""
        if needs_hotel and real_time_data.get("hotels"):
            hotels_info = "\n".join([
                f"- {h['name']}({h.get('star', '')}) @ {h.get('location', '')}: {h.get('price_range', '')}, 适合{h.get('suitable_for', '家庭')}, {h.get('highlights', '')}"
                for h in real_time_data.get("hotels", [])[:5]
            ])

        pitfalls = real_time_data.get("pitfalls", [])
        money_tips = real_time_data.get("money_saving_tips", [])

        # Pre-compute nested expressions to avoid f-string nesting issues
        hotel_section = ""
        if needs_hotel:
            hotel_display = hotels_info or "暂无具体酒店推荐，请根据用户需求推荐适合的具体酒店"
            hotel_section = f"\n### 推荐酒店（请在行程中使用具体酒店名称）\n{hotel_display}\n"

        pitfalls_display = "\n".join(["- " + p for p in pitfalls]) if pitfalls else "暂无"
        money_tips_display = "\n".join(["- " + t for t in money_tips]) if money_tips else "暂无"

        nights_display = ""
        if needs_hotel:
            nights_count = duration_days - 1
            nights_display = f"{nights_count}晚"
        no_hotel_line = "- 住宿：不需要（当天往返）" if not needs_hotel else ""

        # 风格描述
        style_desc = ""
        if style:
            style_desc = TRAVEL_STYLE_PROMPT_MAP.get(style, "")

        prompt = f"""你是一位资深旅行规划师，拥有20年的从业经验。请根据以下详细信息，为这个家庭量身定制{destination}{duration_days}天的旅行行程。

## 👨\u200d👩\u200d👧\u200d👦 用户画像
{profile_summary}

## ⚠️ 旅行约束
{constraints_summary}

## 📊 预算信息
- 每日每人预算：{trip_constraints.get('daily_budget_per_person', 600)}元
- 总预算：{trip_constraints.get('total_budget', '不限')}元
- 每日活动时长上限：{trip_constraints.get('max_activity_hours', 8)}小时
- 每日步行上限：{trip_constraints.get('max_walking_km', 8)}公里

## 🎯 用户需求
{user_requirements or '无特殊要求'}

## 🎨 旅行风格
{style_desc or '根据家庭情况灵活安排'}
{hotel_info}

## 📍 目的地实时信息

### 热门景点及价格
{attractions_info or '暂无实时信息'}

### 美食推荐
{food_info or '暂无实时信息'}
{hotel_section}
### 避坑指南
{pitfalls_display}

### 省钱技巧
{money_tips_display}

## 📅 行程要求
- 目的地：{destination}
- 出发日期：{start_date.isoformat()}
- 行程天数：{duration_days}天{nights_display}
{no_hotel_line}

## 输出格式

请输出 JSON 格式的完整行程：

```json
{{
  "trip_overview": {{
    "theme": "行程主题",
    "style": "行程风格",
    "total_budget_estimate": 预算总额,
    "highlights": ["核心亮点1", "亮点2", "亮点3"],
    "packing_list": ["必带物品1", "物品2"],
    "special_arrangements": ["针对老人/儿童的特别安排"],
    "hotel_recommendation": {{
      "name": "具体酒店名称（如：澳门威尼斯人酒店）",
      "location": "酒店位置（如：氹仔金光大道）",
      "star_rating": "星级（如：5星）",
      "price_per_night": "每晚参考价格（如：800-1500元）",
      "room_suggestion": {{
        "room_type": "推荐房型（如：家庭房/豪华双床房）",
        "room_count": "建议房间数",
        "reason": "推荐理由（为什么适合这个家庭）"
      }},
      "why_suitable": "为什么适合本次出行（如：有老人需要电梯、无障碍设施等）",
      "facilities": ["酒店设施1", "设施2"],
      "booking_tips": "预订建议（如：提前一周预订、周末价格较高等）",
      "alternatives": [
        {{"name": "备选酒店1", "price_range": "价格区间", "note": "特点说明"}},
        {{"name": "备选酒店2", "price_range": "价格区间", "note": "特点说明"}}
      ]
    }}
  }},
  "daily_plans": [
    {{
      "day": 1,
      "date": "2024-01-15",
      "theme": "大三巴历史文化之旅",
      "weather_tip": "多云15-20度，适合户外游览",
      "activities": [
        {{
          "time": "09:00",
          "duration_minutes": 120,
          "type": "attraction",
          "title": "大三巴牌坊及恋爱巷",
          "location": "澳门大三巴街（从威尼斯人坐免费巴士到新马路下车步行10分钟）",
          "description": "澳门标志性建筑，世界文化遗产。门票免费。",
          "cost_per_person": 0,
          "tips": {{
            "why_recommend": "澳门地标，必打卡，拍照圣地",
            "best_experience": "早上10点前到人少，可以拍到无人照片",
            "avoid_pitfalls": "周末和节假日人很多，拍照需排队",
            "save_money": "门票免费，无需购买任何付费项目",
            "special_for_family": "有老人可以慢慢走，台阶不多"
          }},
          "alternatives": ["玫瑰堂（距离5分钟）", "议事亭前地"]
        }},
        {{
          "time": "12:00",
          "duration_minutes": 90,
          "type": "meal",
          "title": "午餐：玛嘉烈蛋挞店 + 大利来记猪扒包",
          "location": "新马路玛嘉烈蛋挞总店（大三巴步行8分钟）",
          "description": "澳门蛋挞鼻祖，外酥里嫩。蛋挞10澳门币/个，猪扒包45澳门币。",
          "cost_per_person": 55,
          "tips": {{
            "why_recommend": "正宗葡式蛋挞，比肯德基好吃10倍",
            "best_experience": "蛋挞趁热吃，猪扒包现烤最香",
            "avoid_pitfalls": "中午12点-13点排队最长，建议避开",
            "save_money": "买6个蛋挞有套餐优惠",
            "special_for_family": "老人和小孩都适合，不辣"
          }},
          "alternatives": ["义顺牛奶公司（双皮奶）"]
        }},
        {{
          "time": "14:00",
          "duration_minutes": 90,
          "type": "rest",
          "title": "午休 @ 澳门威尼斯人酒店",
          "location": "澳门威尼斯人酒店（氹仔）",
          "description": "回酒店休息，为老人和小孩补充体力。酒店房间宽敞舒适。",
          "cost_per_person": 0,
          "tips": {{
            "why_recommend": "威尼斯人是澳门标志性酒店，有室内运河和贡多拉",
            "best_experience": "房间可以看到酒店内部威尼斯人造天空",
            "special_for_family": "带老人出行需要午休，避免过度疲劳"
          }}
        }}
      ],
      "daily_summary": {{
        "total_cost": 200,
        "walking_km": 4,
        "activity_hours": 6,
        "energy_level": "轻松"
      }}
    }}
  ],
  "professional_advice": {{
    "best_time_to_visit": "最佳游玩时间",
    "local_customs": "当地习俗/礼仪",
    "emergency_contacts": "紧急联系方式",
    "must_try_experiences": ["必体验1", "必体验2"]
  }}
}}
```

## 🚨 重要提示（必须遵守）

### 必须使用具体信息（最重要！）
- 景点名称必须是真实的具体景点名（如"大三巴牌坊"而非"澳门景点"）
- 餐厅名称必须是真实的店铺名（如"玛嘉烈蛋挞店"而非"当地餐厅"）
- 地址必须包含具体位置（如"官也街"而非"澳门市区"）
- 门票/餐费必须给出具体数字（如"免费"或"45元"而非"价格待定"）

### 禁止使用的模糊表达（违规将导致行程无效）
❌ "当地餐厅" → ✅ "诚昌饭店（官也街）"
❌ "澳门市区" → ✅ "威尼斯人度假村3楼美食广场"
❌ "当地酒店" → ✅ "澳门威尼斯人酒店/澳门新濠影汇"
❌ "景点游览" → ✅ "参观大三巴牌坊和恋爱巷"
❌ "价格待查" → ✅ "门票免费" 或 "成人票120元"

### 其他要求
1. 每个活动必须包含详细的 tips，这是专业价值的体现
2. 如果有老人/儿童，必须在 special_for_family 中说明特别安排
3. 餐饮安排要考虑成员的饮食偏好和禁忌
4. 活动强度必须符合约束条件
5. 优先使用上面提供的"热门景点及价格"、"美食推荐"和"推荐酒店"中的真实信息
6. 休息/午休活动中的"酒店"必须使用具体酒店名称（如"威尼斯人酒店"而非"酒店"）

请直接输出 JSON，不要有其他内容。"""

        return prompt

    def _build_business_trip_prompt(
        self,
        destination: str,
        duration_days: int,
        start_date: date,
        end_date: date,
        user_requirements: Optional[str],
        needs_hotel: bool = True,
    ) -> str:
        """构建出差日程提示词（不包含旅游景点和美食推荐）"""

        # 计算日期信息
        from datetime import timedelta
        dates_info = []
        for i in range(duration_days):
            current_date = start_date + timedelta(days=i)
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            weekday = weekday_names[current_date.weekday()]
            dates_info.append(f"第{i+1}天（{current_date.month}.{current_date.day} {weekday}）")

        dates_str = "、".join(dates_info)

        prompt = f"""你是一位资深商务助理，请为用户规划一份{destination}的出差日程框架。

## 📅 出差信息
- 目的地：{destination}
- 出差时间：{start_date.isoformat()} 至 {end_date.isoformat()}
- 行程天数：{duration_days}天{"" if not needs_hotel else f"（{duration_days-1}晚）"}
- 日期详情：{dates_str}

## 📝 用户备注
{user_requirements or '无特殊说明'}

## ⚠️ 重要规则（必须遵守）

### 这是出差场景，不是旅游！
1. **绝对禁止**添加旅游景点（故宫、长城、西湖等任何景点）
2. **绝对禁止**添加美食推荐和餐厅打卡
3. **绝对禁止**添加购物、观光、打卡类活动
4. 只生成**工作日程框架**，具体工作内容由用户自己安排

### 出差日程的正确结构
- 第一天：抵达 + 简单安顿 + 晚间休息
- 中间几天：工作时间块（上午/下午）+ 晚间自由安排
- 最后一天：工作收尾 + 返程

### 活动类型限制
只允许使用以下类型：
- transportation：交通（抵达/返程）
- work：工作时间块
- meal：简单用餐（不推荐具体餐厅）
- rest：休息/酒店入住
- meeting：会议/约饭（如用户提及具体人员）

## 输出格式

请输出 JSON 格式的出差日程：

```json
{{
  "trip_overview": {{
    "theme": "{destination}出差",
    "style": "商务出差",
    "total_budget_estimate": 0,
    "highlights": ["出差日程框架", "工作时间安排"],
    "packing_list": ["工作资料", "笔记本电脑", "充电器"],
    "special_arrangements": []
  }},
  "daily_plans": [
    {{
      "day": 1,
      "date": "{start_date.isoformat()}",
      "theme": "抵达{destination}",
      "activities": [
        {{
          "time": "14:00",
          "duration_minutes": 180,
          "type": "transportation",
          "title": "抵达{destination}",
          "location": "{destination}",
          "description": "完成抵达，前往住处",
          "cost_per_person": 0,
          "tips": {{
            "why_recommend": "建议提前规划好交通路线"
          }}
        }},
        {{
          "time": "18:00",
          "duration_minutes": 60,
          "type": "meal",
          "title": "晚餐",
          "location": "酒店附近",
          "description": "简单用餐",
          "cost_per_person": 50,
          "tips": {{}}
        }},
        {{
          "time": "20:00",
          "duration_minutes": 120,
          "type": "rest",
          "title": "入住酒店，调整休息",
          "location": "酒店",
          "description": "安顿休息，为第二天工作做准备",
          "cost_per_person": 0,
          "tips": {{}}
        }}
      ],
      "daily_summary": {{"total_cost": 50}}
    }}
  ]
}}
```

### 中间工作日模板（第2天到倒数第2天）
每天结构：
- 09:00 工作时间块（上午），4小时
- 12:00 午餐，1小时
- 14:00 工作时间块（下午），4小时
- 18:00 晚餐，1小时
- 19:30 晚间自由安排（可留空或标注"整理工作资料"）

### 最后一天模板
- 09:00 工作收尾，2-3小时
- 12:00 午餐
- 14:00 返程（或如用户提到约人，可安排约饭）

请根据实际天数生成完整的出差日程。每天的 activities 都要包含完整的时间安排。

请直接输出 JSON，不要有其他内容。"""

        return prompt
