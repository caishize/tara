"""
Memory management tools for Claude Agent.

Provides tools for memory search/save/update and favor tracking.
"""

from .registry import ToolCategory, ToolRegistry
from .shared.wrap import wrap_method as _wrap_method
from .executors.memory_executor import MemoryToolExecutor
from .executors.favor_gift_executor import FavorGiftExecutor


def register_memory_tools(
    registry: ToolRegistry,
    executor: MemoryToolExecutor,
    favor_gift_executor: FavorGiftExecutor,
) -> None:
    """Register memory and favor tracking tools with the registry."""

    # Record favor (人情账本)
    registry.register(
        name="record_favor",
        description="记录人情往来。别人帮忙→收人情；自己送礼→送人情。用于跟踪人情关系。",
        parameters={
            "type": "object",
            "properties": {
                "person_name": {
                    "type": "string",
                    "description": "相关人员姓名"
                },
                "favor_type": {
                    "type": "string",
                    "enum": ["received", "given"],
                    "description": "人情类型：received(收到) / given(送出)"
                },
                "description": {
                    "type": "string",
                    "description": "人情描述，如'结婚送礼500元'"
                },
                "value": {
                    "type": "number",
                    "description": "金额或价值（可选）"
                },
                "occasion": {
                    "type": "string",
                    "description": "场合，如'结婚'、'生日'"
                },
                "date": {
                    "type": "string",
                    "description": "日期，格式: YYYY-MM-DD"
                }
            },
            "required": ["person_name", "favor_type", "description"]
        },
        executor=_wrap_method(favor_gift_executor.record_favor),
        category=ToolCategory.MEMORY,
        is_stateful=True,
    )

    # Check favor balance (spec name: check_favor_balance)
    registry.register(
        name="check_favor_balance",
        description="查询与某人的人情往来记录和余额。",
        parameters={
            "type": "object",
            "properties": {
                "person_name": {
                    "type": "string",
                    "description": "要查询的人员姓名"
                },
                "include_history": {
                    "type": "boolean",
                    "description": "是否包含历史记录",
                    "default": True
                }
            },
            "required": ["person_name"]
        },
        executor=_wrap_method(favor_gift_executor.query_favor_balance),
        category=ToolCategory.MEMORY,
    )

    # Suggest favor return
    registry.register(
        name="suggest_favor_return",
        description="建议如何回报收到的人情。",
        parameters={
            "type": "object",
            "properties": {
                "person_name": {
                    "type": "string",
                    "description": "要回报的人员姓名"
                },
                "occasion": {
                    "type": "string",
                    "description": "场合，如'生日'、'升职'"
                },
                "budget": {
                    "type": "number",
                    "description": "预算"
                }
            },
            "required": ["person_name"]
        },
        executor=_wrap_method(favor_gift_executor.suggest_favor_return),
        category=ToolCategory.MEMORY,
    )

    # Search memory (spec name: search_memory)
    registry.register(
        name="search_memory",
        description="搜索历史记忆。可以按类型、人物、时间等维度搜索。",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["emotion", "plan", "schedule", "relationship", "preference", "life_event", "location", "health", "work", "favor", "general", "all"],
                    "description": "记忆类型",
                    "default": "all"
                },
                "person": {
                    "type": "string",
                    "description": "相关人物"
                },
                "date_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "end": {"type": "string"}
                    }
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制",
                    "default": 10
                }
            }
        },
        executor=_wrap_method(executor.search_memories),
        category=ToolCategory.MEMORY,
    )

    # Save memory
    registry.register(
        name="save_memory",
        description="保存一条重要记忆。当用户提到值得记住的信息（偏好、经历、关系变化等）时使用。",
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "记忆内容（详细描述）",
                },
                "summary": {
                    "type": "string",
                    "description": "简短摘要（可选，不填则自动截取）",
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["emotion", "plan", "schedule", "relationship", "preference",
                             "life_event", "location", "health", "work", "favor", "general"],
                    "description": "记忆类型",
                    "default": "general",
                },
                "person": {
                    "type": "string",
                    "description": "相关人物（可选）",
                },
                "importance": {
                    "type": "integer",
                    "description": "重要性 1-10",
                    "default": 5,
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签列表（可选）",
                },
            },
            "required": ["content"],
        },
        executor=_wrap_method(executor.save_memory),
        category=ToolCategory.MEMORY,
        is_stateful=True,
    )

    # Update memory
    registry.register(
        name="update_memory",
        description="更新已有的记忆记录。用于修正、补充或归档记忆。",
        parameters={
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "记忆ID（通过 search_memory 获取）",
                },
                "updates": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "更新内容"},
                        "summary": {"type": "string", "description": "更新摘要"},
                        "memory_type": {"type": "string", "description": "更新类型"},
                        "importance": {"type": "integer", "description": "更新重要性 1-10"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "status": {
                            "type": "string",
                            "enum": ["active", "archived", "superseded"],
                            "description": "更新状态",
                        },
                    },
                },
            },
            "required": ["memory_id", "updates"],
        },
        executor=_wrap_method(executor.update_memory),
        category=ToolCategory.MEMORY,
        is_stateful=True,
    )

    # Recommend gift
    registry.register(
        name="recommend_gift",
        description=(
            "为家庭成员推荐个性化礼物。结合成员画像、兴趣爱好和热门趋势推荐。"
            "⚠️ 需要先通过 add_member 添加成员信息。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "收礼人姓名或称谓",
                },
                "occasion": {
                    "type": "string",
                    "enum": ["birthday", "anniversary", "festival", "thank_you",
                             "graduation", "new_year", "spring_festival", "other"],
                    "description": "送礼场合",
                    "default": "birthday",
                },
                "budget": {
                    "type": "number",
                    "description": "预算金额（元）",
                    "default": 500,
                },
            },
            "required": ["recipient"],
        },
        executor=_wrap_method(favor_gift_executor.recommend_gift),
        category=ToolCategory.SHOPPING,
        supports_progress=True,
    )

    # Create gift task
    registry.register(
        name="create_gift_task",
        description="创建礼物准备任务。用于提前规划某个场合的礼物准备，系统会在合适时间提醒。",
        parameters={
            "type": "object",
            "properties": {
                "recipient": {
                    "type": "string",
                    "description": "收礼人姓名",
                },
                "occasion": {
                    "type": "string",
                    "enum": ["birthday", "anniversary", "holiday", "graduation",
                             "wedding", "newborn", "housewarming", "promotion", "custom"],
                    "description": "场合类型",
                    "default": "birthday",
                },
                "occasion_date": {
                    "type": "string",
                    "description": "场合日期，格式: YYYY-MM-DD",
                },
                "budget_min": {
                    "type": "integer",
                    "description": "最低预算（元，可选）",
                },
                "budget_max": {
                    "type": "integer",
                    "description": "最高预算（元，可选）",
                },
                "notes": {
                    "type": "string",
                    "description": "备注（可选）",
                },
            },
            "required": ["recipient", "occasion_date"],
        },
        executor=_wrap_method(favor_gift_executor.create_gift_task),
        category=ToolCategory.SHOPPING,
        is_stateful=True,
    )

    # NOTE: view_execution_details removed — use view_tool_details
    # from recall_tools instead (avoids duplicate registration).

    # NOTE: 5 NotebookLM tools (query/list/select/health/auth) removed.
    # They were behind required_connectors=["notebooklm_mcp"] and never
    # loaded by default.
