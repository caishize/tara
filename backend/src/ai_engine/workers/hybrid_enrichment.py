"""
Hybrid enrichment directives for background personalization tasks.

Each entry tells the slow-path agent exactly what personal context to
cross-reference, preventing it from re-doing the fast-path query.
"""

from typing import Optional

from ..queue import TaskPayload


# Action-specific enrichment directives for hybrid background tasks.
HYBRID_ENRICHMENT_MAP: dict = {
    "weather": """\
1. 查询用户**近期日程和行程**（用 search_events / query_trips），看是否有与该天气相关的活动
2. 查询用户/家庭成员的**偏好和特征**（系统 prompt 中已有成员画像），如怕冷、过敏体质、户外爱好等
3. 结合天气 + 日程 + 个人特征，给出**个性化提醒**，例如：
   - "您后天有去澳门的行程，建议带伞"
   - "根据您怕冷的特征，室内空调场所建议带件薄外套"
   - "您本周没有户外安排，天气对您暂无特别影响"
""",
    "lookup": """\
1. 根据查询目标（日程/任务/行程/提醒），查询**关联数据**：
   - 日程 → 查是否有时间冲突、是否需要准备材料
   - 任务 → 查截止日期、优先级建议
   - 行程 → 查准备清单完成状态、天气情况
   - 提醒 → 查是否有遗漏的关联事项
2. 查询用户**记忆**（用 search_memory），看是否有相关的历史偏好或经验
3. 结合发现给出**行动建议**
""",
    "greet": """\
1. 查询用户**今日日程**（用 search_events，按今天日期过滤），看今天有什么安排
2. 查询是否有**待办任务**到期（用 query_tasks）
3. 查询用户**记忆**中是否有今天相关的事项（纪念日、习惯等）
4. 如有发现，给出简短的**今日提醒**；如无，不必输出
""",
    "chat": """\
1. 查询用户**记忆**（用 search_memory），看对话主题是否与用户的经历、偏好相关
2. 查询**家庭成员画像**（系统 prompt 中已有），看是否有成员相关的建议
3. 如果聊天内容涉及地点/时间，查询相关**日程或行程**
4. 只有发现有价值的关联时才输出
""",
    "time": """\
1. 查询用户在该时间点前后的**日程安排**
2. 查询是否有**提醒或任务**与该时间相关
3. 如有时间紧凑或冲突，给出提醒
""",
    "_default": """\
1. 查询用户**日程、行程、任务**，看是否与用户的问题相关
2. 查询用户/家庭成员的**偏好和记忆**
3. 只有发现个性化关联时才输出建议
""",
}


def format_hybrid_section(task: TaskPayload) -> str:
    """Format the hybrid background instruction section.

    Provides action-specific enrichment directives so the slow path
    agent cross-references user context (schedules, trips, memories,
    preferences) rather than re-doing the same query.
    """
    fast_action = task.context_snapshot.get("fast_action", "")
    fast_filter = task.context_snapshot.get("fast_lookup_filter", "")
    fast_location = task.context_snapshot.get("fast_location", "")

    enrichment = HYBRID_ENRICHMENT_MAP.get(
        fast_action,
        HYBRID_ENRICHMENT_MAP["_default"],
    )

    section = f"""

## 重要：这是一个后台个性化洞察任务

用户已经收到了快速回答（{fast_action}），你**绝对不能**重复查询同样的信息。

### 你的唯一职责
将用户的问题与他/她的**个人情境**交叉分析，发现快速回答中没有提到的个性化洞察。

### 具体操作
{enrichment}

### 关键规则
1. **禁止重复查询** — 不要再次搜索"{fast_filter or fast_action}"相关信息，快速回答已提供
2. **交叉分析** — 用工具查询用户的日程、行程、记忆、偏好等，与快速回答内容做关联
3. **有洞察才输出** — 如果交叉分析后没有发现有价值的关联（如用户没有相关行程、日程或偏好），就简短输出"暂无额外建议"即可，不要凑字数
4. **不要反问用户** — 直接给出分析结果
5. **简洁有用** — 只输出与用户个人情况直接相关的建议，2-4句话足够
6. **利用会话已知信息** — 快速回答已经在会话上下文中，不要复述已有结论
"""
    if fast_location:
        section += f"\n用户所在城市: {fast_location}"

    return section
