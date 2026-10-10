"""
Member management tools for Claude Agent.

Provides tools for adding, updating, and querying members
(family, friends, colleagues, business contacts, etc.).
"""

from .registry import ToolCategory, ToolRegistry
from .shared.wrap import wrap_method as _wrap_method
from .executors.member_executor import MemberToolExecutor


def register_member_tools(
    registry: ToolRegistry,
    executor: MemberToolExecutor,
) -> None:
    """Register member management tools with the registry."""

    # Add member
    registry.register(
        name="add_member",
        description=(
            "添加新成员（家人、朋友、同事、商务联系人等）。"
            "当用户提到一个新的人物且系统中没有记录时使用。"
            "人脉/联系人信息也用此工具。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "成员姓名。如果用户没有提供具体名字，可以使用称谓（如'老婆'、'儿子'）"
                },
                "nickname": {
                    "type": "string",
                    "description": "昵称/称谓，如'老婆'、'宝贝'、'小明'"
                },
                "relation_type": {
                    "type": "string",
                    "enum": [
                        "spouse", "parent", "child", "sibling",
                        "grandparent", "grandchild", "in_law",
                        "friend", "colleague", "client", "other",
                    ],
                    "description": "与用户的关系类型"
                },
                "gender": {
                    "type": "string",
                    "enum": ["male", "female"],
                    "description": "性别"
                },
                "age": {
                    "type": "integer",
                    "description": "年龄"
                },
                "date_of_birth": {
                    "type": "string",
                    "description": "出生日期，格式: YYYY-MM-DD"
                },
                "occupation": {
                    "type": "string",
                    "description": "职业（写入工作履历表）"
                },
                "current_company": {
                    "type": "string",
                    "description": "当前所在公司/组织名称（纯名称，禁止附加'已离职'等状态后缀，写入工作履历表）"
                },
                "current_position": {
                    "type": "string",
                    "description": "当前职位（写入工作履历表）"
                },
                "address": {
                    "type": "string",
                    "description": "住址"
                },
                "notes": {
                    "type": "string",
                    "description": "备注信息，如'all in 企业大脑建设'、'下次去北京约饭'"
                },
            },
            "required": ["name"]
        },
        executor=_wrap_method(executor.add_member),
        category=ToolCategory.FAMILY,
        is_stateful=True,
    )

    # Update member info
    registry.register(
        name="update_member_info",
        description=(
            "更新成员信息。支持同时更新多项信息：基本信息、工作履历、与用户的关系等。"
            "work_history 数组可一次录入完整工作经历（如: 顺丰→字节→B站）。"
            "relation_type 设置此成员与用户的关系（boss=上级, subordinate=下属, peer=同事等）。"
            "member_relations 数组可录入成员与其他成员的关系（如: 周明是强哥的部下）。"
            "设置 current_company 会自动同步到工作履历表。\n"
            "【重要】尽量一次调用完整录入所有可推断的字段：\n"
            "- gender: 从称呼（哥/姐/先生/女士）、代词（他/她）、名字特征推断性别\n"
            "- relation_type: 从对话语境推断关系（如'老领导'→mentor, '同事'→peer）\n"
            "- work_history: 录入完整履历时间线，注意区分在职时间段，不要把离职后的空窗期算入下一家公司\n"
            "- 日期务必准确：用户说'2023年加入'则 start_date 为 2023-01-01，不要与离职日期混淆\n"
            "- is_current 必须显式设置：在职=true，已离职=false。已离职的人所有条目都应为 false\n"
            "\n【company_name 纯净规则 — 违反此规则会导致 UI 显示错误】\n"
            "company_name / current_company 字段只能填写纯公司名称。\n"
            "在职状态完全由 is_current 字段控制，绝对不能编码在公司名里。\n"
            "✗ 错误: '字节跳动 (已离职)'、'Google（在职）'、'腾讯-已辞职'\n"
            "✓ 正确: '字节跳动' + is_current=false\n"
            "✓ 正确: 'Google' + is_current=true"
        ),
        parameters={
            "type": "object",
            "properties": {
                "member_name": {
                    "type": "string",
                    "description": "成员姓名或称谓，用于查找成员"
                },
                "updates": {
                    "type": "object",
                    "description": "要更新的信息",
                    "properties": {
                        "name": {"type": "string", "description": "成员全名/真实姓名"},
                        "nickname": {"type": "string", "description": "新昵称/称谓"},
                        "gender": {
                            "type": "string",
                            "enum": ["male", "female"],
                            "description": "性别"
                        },
                        "date_of_birth": {
                            "type": "string",
                            "description": "出生日期，格式: YYYY-MM-DD"
                        },
                        "age": {"type": "integer", "description": "年龄"},
                        "relation_type": {
                            "type": "string",
                            "enum": [
                                "spouse", "parent", "child", "sibling",
                                "grandparent", "grandchild", "in_law",
                                "friend", "colleague", "classmate",
                                "neighbor", "other",
                                # Professional relation subtypes
                                "boss", "subordinate", "peer",
                                "mentor", "mentee", "client",
                            ],
                            "description": "与用户的关系类型"
                        },
                        "occupation": {"type": "string", "description": "职业/行业（写入工作履历表）"},
                        "current_company": {
                            "type": "string",
                            "description": "当前所在公司/组织名称（纯名称，禁止附加'已离职'等状态后缀，写入工作履历表）"
                        },
                        "current_position": {
                            "type": "string",
                            "description": "当前职位/头衔（写入工作履历表）"
                        },
                        "phone": {"type": "string", "description": "手机号"},
                        "email": {"type": "string", "description": "邮箱"},
                        "address": {"type": "string", "description": "住址（家庭地址）"},
                        "location": {
                            "type": "object",
                            "description": "结构化的地址信息",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["home", "work", "school", "other"],
                                    "description": "位置类型"
                                },
                                "address": {"type": "string", "description": "具体地址"}
                            }
                        },
                        "preferences": {
                            "type": "object",
                            "description": "偏好信息",
                            "properties": {
                                "food": {"type": "array", "items": {"type": "string"}},
                                "hobbies": {"type": "array", "items": {"type": "string"}},
                                "gifts": {"type": "array", "items": {"type": "string"}}
                            }
                        },
                        "health_notes": {"type": "string", "description": "健康注意事项"},
                        "notes": {"type": "string", "description": "备注信息"},
                        "work_history": {
                            "type": "array",
                            "description": (
                                "工作履历列表，按时间从远到近排列。"
                                "每条包含公司、职位、起止时间等。"
                                "【重要】必须为每条记录显式设置 is_current：在职=true，已离职=false。"
                                "如果此人已从所有公司离职，则所有条目的 is_current 都应为 false。"
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "company_name": {
                                        "type": "string",
                                        "description": (
                                            "公司/组织名称。只填纯名称，"
                                            "禁止附加任何状态后缀如'(已离职)'。"
                                            "在职状态用 is_current 字段表示"
                                        ),
                                    },
                                    "position": {"type": "string", "description": "职位/头衔"},
                                    "start_date": {"type": "string", "description": "入职日期 YYYY-MM-DD"},
                                    "end_date": {"type": "string", "description": "离职日期 YYYY-MM-DD，当前工作不填"},
                                    "is_current": {"type": "boolean", "description": "是否为当前工作（在职=true，已离职=false，必填）"},
                                },
                                "required": ["company_name"],
                            },
                        },
                        "member_relations": {
                            "type": "array",
                            "description": (
                                "此成员与其他成员的关系列表。"
                                "用于录入成员间关系，如'周明之前是强哥的部下'。"
                                "relation_type 指此成员相对于 target_member 的角色。"
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "target_member": {
                                        "type": "string",
                                        "description": "另一位成员的姓名或称谓",
                                    },
                                    "relation_type": {
                                        "type": "string",
                                        "enum": [
                                            "boss", "subordinate", "peer",
                                            "mentor", "mentee", "client",
                                        ],
                                        "description": (
                                            "此成员相对于 target_member 的角色。"
                                            "如'周明是强哥的部下'→ target_member=强哥, relation_type=subordinate"
                                        ),
                                    },
                                    "company_name": {
                                        "type": "string",
                                        "description": "关系所在公司名称（纯名称，禁止附加状态后缀，可选）",
                                    },
                                    "is_current": {
                                        "type": "boolean",
                                        "description": "是否为当前关系（默认 true）",
                                    },
                                },
                                "required": ["target_member", "relation_type"],
                            },
                        },
                    }
                }
            },
            "required": ["member_name", "updates"]
        },
        executor=_wrap_method(executor.update_member_info),
        category=ToolCategory.FAMILY,
        is_stateful=True,
        sequential_only=True,
    )

    # Query members
    registry.register(
        name="query_members",
        description=(
            "查询成员列表及其信息。支持查询家人、朋友、同事等所有类型成员。"
            "默认返回所有成员（家人+朋友+同事等），设置 category='family' 仅返回家人。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["family", "all"],
                    "description": "查询范围：'all'=所有成员（默认），'family'=仅家人",
                    "default": "all"
                },
                "name_filter": {
                    "type": "string",
                    "description": "可选：按姓名或称谓筛选"
                },
                "include_preferences": {
                    "type": "boolean",
                    "description": "是否包含偏好信息",
                    "default": False
                }
            }
        },
        executor=_wrap_method(executor.query_members),
        category=ToolCategory.FAMILY,
    )

    # Get member details
    registry.register(
        name="get_member_details",
        description="获取成员的详细信息，包括偏好、健康状况、年龄等。用于安排活动时了解成员特点。",
        parameters={
            "type": "object",
            "properties": {
                "member_name": {
                    "type": "string",
                    "description": "成员姓名或称谓"
                }
            },
            "required": ["member_name"]
        },
        executor=_wrap_method(executor.get_member_details),
        category=ToolCategory.FAMILY,
    )

    # Delete member
    registry.register(
        name="delete_member",
        description="删除成员。⚠️ 此操作不可逆，请谨慎使用。",
        parameters={
            "type": "object",
            "properties": {
                "member_name": {
                    "type": "string",
                    "description": "要删除的成员姓名或称谓"
                },
                "confirm": {
                    "type": "boolean",
                    "description": "确认删除",
                    "default": False
                }
            },
            "required": ["member_name", "confirm"]
        },
        executor=_wrap_method(executor.delete_member),
        category=ToolCategory.FAMILY,
        is_stateful=True,
        sequential_only=True,
    )
