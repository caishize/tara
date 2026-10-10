"""
Prompt Templates for Agentic Extraction.

This module contains optimized prompts for LLM-based extraction tasks.
Prompts are designed to:
- Extract all information in a single LLM call
- Provide clear output schemas
- Handle Chinese language nuances
- Support multi-turn dialogue context
"""

# All supported intent types with descriptions
INTENT_TYPES = """
## 支持的意图类型

### 成员管理
- add_member: 添加家庭成员（如"我老婆叫小红"、"记一下我儿子的信息"）
- query_member: 查询成员信息（如"我家有谁"、"我老婆是谁"）
- update_member: 更新成员信息（如"我老婆住在北京"、"更新一下我妈的电话"）

### 重要日期
- add_date: 添加重要日期（如"我老婆生日是5月20日"、"记住我们结婚纪念日"）
- query_date: 查询日期（如"我老婆生日是哪天"）
- query_upcoming: 查询即将到来的日期（如"最近有什么重要日期"）

### 提醒相关
- set_reminder: 设置提醒（如"提醒我明天开会"、"3点钟叫我起床"）
- query_reminder: 查询提醒（如"我有什么提醒"）
- cancel_reminder: 取消提醒

### 购物相关
- add_shopping: 添加购物清单（如"要买牛奶"、"需要买些水果"）
- query_shopping: 查询购物清单（如"购物清单有什么"、"要买什么"）
- complete_shopping: 完成购物项

### 礼物推荐
- recommend_gift: 推荐礼物（如"老婆生日送什么好"、"给爸爸买什么礼物"）
- query_gift: 查询礼物建议

### 健康管理
- log_health: 记录健康信息（如"今天血压140/90"、"体重70公斤"）
- query_health: 查询健康记录
- set_health_reminder: 设置健康提醒

### 财务管理
- log_expense: 记录支出（如"今天买菜花了50块"、"加油200元"）
- query_expense: 查询支出（如"这个月花了多少钱"）
- set_budget: 设置预算

### 任务管理
- create_task: 创建任务（如"添加一个任务"）
- query_task: 查询任务
- complete_task: 完成任务
- assign_task: 分配任务

### 节日准备
- plan_holiday: 规划节日（如"春节怎么过"）
- query_holiday_plan: 查询节日计划

### 日程视图
- query_today: 查询今日安排（如"今天有什么事"）
- query_schedule: 查询日程

### 通用意图
- greeting: 打招呼（如"你好"、"早上好"）
- thanks: 感谢（如"谢谢"、"多谢"）
- help: 帮助（如"你能做什么"）
- unknown: 无法确定意图或需要进一步处理
"""

# Family relationship mappings (Chinese to English)
RELATIONSHIP_MAPPINGS = """
## 家庭关系映射

常见中文称谓及其标准化表示：
- 爸爸/父亲/爸 → father
- 妈妈/母亲/妈 → mother
- 老婆/妻子/太太/媳妇 → wife
- 老公/丈夫 → husband
- 儿子 → son
- 女儿 → daughter
- 哥哥 → brother
- 姐姐 → sister
- 弟弟 → younger_brother
- 妹妹 → younger_sister
- 爷爷/祖父 → grandfather
- 奶奶/祖母 → grandmother
- 外公/外祖父 → grandfather_maternal
- 外婆/外祖母 → grandmother_maternal
- 叔叔/伯伯 → uncle
- 阿姨/姑姑 → aunt
- 舅舅 → uncle_maternal
- 公公 → father_in_law
- 婆婆 → mother_in_law
- 岳父 → father_in_law_wife
- 岳母 → mother_in_law_wife
"""

# Main unified extraction prompt
UNIFIED_EXTRACTION_PROMPT = """你是一个智能家庭助手的意图理解引擎。请像人一样理解用户的真实意图。

## 对话上下文
{context}

## 用户输入
"{text}"

{intent_types}

{relationship_mappings}

## 理解要求
1. **像人一样理解**：关注用户的真实意图，而不只是字面意思
2. **上下文关联**：如果用户在补充之前对话的信息，标记 is_continuation: true
3. **完整提取**：提取所有相关的结构化信息（人物、日期、时间、地点、金额等）
4. **关系推断**：从用户表述中推断人物之间的关系
5. **置信度**：对于模糊或复杂的请求，设置较低的 confidence

## 输出格式（JSON）
```json
{{
    "intent": {{
        "type": "意图类型（使用上面列出的英文标识）",
        "confidence": 0.0-1.0,
        "is_continuation": false
    }},
    "entities": {{
        "persons": [
            {{
                "name": "名字（如果提到）",
                "role": "称谓（如：老婆、儿子、妈妈）",
                "relationship": "标准化关系（如：wife、son、mother）"
            }}
        ],
        "locations": ["北京", "朝阳区", "xxx公司"],
        "datetime": {{
            "date": "5月20日",
            "time": "下午3点",
            "is_lunar": false,
            "relative": "明天/下周二"
        }},
        "amounts": [
            {{
                "value": 100,
                "unit": "元"
            }}
        ],
        "items": ["牛奶", "面包"],
        "content": "任务或提醒的具体内容"
    }},
    "slots": {{
        "date_type": "birthday/anniversary/other",
        "location_type": "home/work/school",
        "category": "餐饮/交通/购物/娱乐/医疗",
        "holiday_type": "spring_festival/mid_autumn/...",
        "recipient": "送礼对象",
        "budget": 500,
        "quantity": 2,
        "unit": "斤"
    }},
    "relationships": [
        {{
            "from": "我",
            "to": "小红",
            "type": "wife"
        }}
    ],
    "reasoning": "简短的理解推理过程"
}}
```

请直接输出 JSON，不要有其他内容。只包含有值的字段，省略空字段。"""

# Simplified extraction prompt for Haiku (cost optimization)
HAIKU_EXTRACTION_PROMPT = """分析用户输入，提取意图和关键信息。

输入: "{text}"

上下文: {context}

意图类型: add_member, query_member, update_member, add_date, query_date, query_upcoming, set_reminder, query_reminder, cancel_reminder, add_shopping, query_shopping, complete_shopping, recommend_gift, query_gift, log_health, query_health, set_health_reminder, log_expense, query_expense, set_budget, create_task, query_task, complete_task, assign_task, plan_holiday, query_holiday_plan, query_today, query_schedule, greeting, thanks, help, unknown

直接输出JSON:
{{"intent":"{{type}}","confidence":0.X,"persons":[{{"role":"X","name":"Y"}}],"datetime":"X","location":"X","amount":X,"items":["X"],"content":"X"}}"""

# Slot filling prompt for specific intents
SLOT_FILLING_PROMPT = """用户正在{intent_description}。

已收集的信息:
{collected_slots}

用户最新输入: "{text}"

请从用户输入中提取以下缺失的信息:
{missing_slots}

直接输出JSON格式的提取结果:"""

# Intent descriptions for slot filling
INTENT_DESCRIPTIONS = {
    "add_member": "添加家庭成员",
    "update_member": "更新成员信息",
    "add_date": "添加重要日期",
    "set_reminder": "设置提醒",
    "create_task": "创建任务",
    "recommend_gift": "推荐礼物",
    "log_expense": "记录支出",
    "add_shopping": "添加购物清单",
    "plan_holiday": "规划节日",
}

# Required slots for each intent
INTENT_REQUIRED_SLOTS = {
    "add_member": ["name", "relationship"],
    "update_member": ["person", "update_field", "update_value"],
    "add_date": ["person", "date_type", "date_value"],
    "set_reminder": ["time", "content"],
    "create_task": ["content"],
    "recommend_gift": ["recipient"],
    "log_expense": ["amount"],
    "add_shopping": ["item_name"],
    "plan_holiday": ["holiday_type"],
}


def build_extraction_prompt(
    text: str,
    context: str = "无",
    use_haiku: bool = False,
) -> str:
    """
    Build the extraction prompt.

    Args:
        text: User input text
        context: Conversation context string
        use_haiku: Whether to use simplified Haiku prompt

    Returns:
        Formatted prompt string
    """
    if use_haiku:
        return HAIKU_EXTRACTION_PROMPT.format(
            text=text,
            context=context if context else "无",
        )

    return UNIFIED_EXTRACTION_PROMPT.format(
        text=text,
        context=context if context else "无",
        intent_types=INTENT_TYPES,
        relationship_mappings=RELATIONSHIP_MAPPINGS,
    )


def build_slot_filling_prompt(
    text: str,
    intent: str,
    collected_slots: dict,
    missing_slots: list,
) -> str:
    """
    Build a slot filling prompt for incomplete intents.

    Args:
        text: User input text
        intent: Current intent type
        collected_slots: Already collected slot values
        missing_slots: List of missing slot names

    Returns:
        Formatted prompt string
    """
    intent_desc = INTENT_DESCRIPTIONS.get(intent, intent)

    collected_str = "\n".join(
        f"- {k}: {v}" for k, v in collected_slots.items()
    ) or "暂无"

    missing_str = "\n".join(f"- {s}" for s in missing_slots)

    return SLOT_FILLING_PROMPT.format(
        intent_description=intent_desc,
        collected_slots=collected_str,
        text=text,
        missing_slots=missing_str,
    )
