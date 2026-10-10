#!/usr/bin/env python3
"""
Detailed SDK message-level latency benchmark.

Logs every message type yielded by receive_response() with timestamps,
to precisely identify what corresponds to production's "first_thinking_delta".
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


# Realistic production system prompt (~3000 chars)
LARGE_SYSTEM_PROMPT = """你是一个智能家庭秘书助手。你的任务是帮助家庭管理日常事务、规划行程、记录重要信息。

## 核心原则
1. **主动思考**: 理解用户真实意图，不要机械执行
2. **工具调用**: 需要数据时主动调用工具查询，不要凭记忆回答
3. **简洁回复**: 用自然的中文回答，避免冗长
4. **家庭导向**: 始终站在家庭整体的角度考虑

## 工具使用指南
- 查询数据前先用对应的查询工具
- 修改数据前先确认目标存在
- 复杂任务可以分步执行多个工具
- 工具上下文中 [#xxxxxxxx] 是执行记录短ID，需要详情时用 view_tool_details 传入完整 UUID
- **农历日期**：当用户提到农历日期时必须调用 convert_lunar_date 工具

## 敏感操作
涉及支付、删除等敏感操作时，系统会自动生成待确认操作。

【当前时间】
2026-02-14 00:48 (Asia/Shanghai)

【用户位置】
广东省揭阳市

【家庭成员】
- 爸爸 (id: member-001): 55岁，退休工程师，爱好钓鱼和象棋
- 妈妈 (id: member-002): 53岁，家庭主妇，爱好跳广场舞和种花
- 我 (id: member-003): 28岁，软件工程师，爱好编程和阅读
- 妹妹 (id: member-004): 25岁，设计师，爱好画画和摄影
- 外婆 (id: member-005): 78岁，退休教师

【已连接服务】
天气查询, 日历同步, 礼物推荐

【数据概览】
事件: 23条, 记忆: 45条, 洞察: 12条, 行程: 3条, 重要日期: 15条

## 你对这个家庭的了解
- 爸爸每天早上6点起床去公园钓鱼，周末会和老朋友下棋
- 妈妈负责家庭日常采购，每周三去菜市场
- 全家每月第一个周日聚餐，通常在家里做饭
- 外婆有高血压，每天需要按时服药，每月15号复诊
- 妹妹下个月生日(3月15日)，去年送了画具套装
- 爸妈结婚纪念日是农历九月初九
- 家庭年度旅行通常安排在国庆假期
- 妈妈对海鲜过敏
- 爸爸最近在学习智能手机使用
- 外婆喜欢听评书和看戏曲节目
- 妹妹喜欢ins风的装饰，房间布置偏北欧简约
- 爸爸血压最近偏高，医生建议减少钠盐摄入

## 家庭成员画像
### 爸爸
性格温和内敛，注重传统礼节。退休后生活规律，喜欢清静。
对新科技感兴趣但学习较慢。关心子女发展但不善表达。
健康状况：轻度高血压，服用降压药

### 妈妈
热情开朗，社交活跃。家庭核心组织者。
对家人健康饮食很关注。健康状况：海鲜过敏

### 外婆
慈祥和蔼，记忆力略有下降。
健康状况：高血压、轻度糖尿病，每月15号复诊

## 本次会话之前的对话摘要
用户之前询问了妹妹生日礼物建议，还问了外婆下次复诊时间。
用户提到想计划清明节全家去潮汕地区短途旅行。"""

SIMPLE_PROMPT = "你好"
COMPLEX_PROMPT = "帮我看看外婆下次复诊是什么时候？还有妹妹生日快到了，有什么新的礼物推荐吗？"


async def run_detailed_benchmark(
    label: str,
    system_prompt: str,
    user_prompt: str,
    tool_count: int = 0,
    max_turns: int = 1,
):
    """Run a benchmark and log every SDK message with timestamps."""
    from claude_agent_sdk import (
        ClaudeAgentOptions, ClaudeSDKClient,
        AssistantMessage, ResultMessage,
    )

    # Try to import StreamEvent for partial messages
    try:
        from claude_agent_sdk import StreamEvent
    except ImportError:
        StreamEvent = None

    model = os.getenv("CLAUDE_MODEL") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    options_kwargs = {
        "model": model,
        "system_prompt": system_prompt,
        "max_turns": max_turns,
        "allowed_tools": [],
        "permission_mode": "bypassPermissions",
        "include_partial_messages": True,
    }

    # Add tools if requested
    if tool_count > 0:
        from claude_agent_sdk import tool as sdk_tool, create_sdk_mcp_server

        sdk_tools = []
        tool_names_list = [
            "get_family_members", "get_member_profile", "update_member_profile",
            "get_events", "create_event", "update_event", "delete_event",
            "get_reminders", "create_reminder", "get_memories", "save_memory",
            "get_insights", "get_relationships", "update_relationship",
            "get_trips", "create_trip", "update_trip", "get_trip_itinerary",
            "get_important_dates", "create_important_date", "get_holidays",
            "get_weather", "get_gift_suggestions", "search_gifts",
            "get_kanban_board", "get_timeline", "get_event_graph",
            "convert_lunar_date", "view_tool_details", "get_briefing",
            "get_care_suggestions", "get_curated_events", "get_smart_groups",
            "get_conversation_context", "query_schedule", "query_tasks",
            "search_events", "get_notifications",
        ]

        for i in range(tool_count):
            name = tool_names_list[i] if i < len(tool_names_list) else f"tool_{i}"
            desc = f"查询或操作{name}相关数据。支持按时间范围、成员、标签筛选。返回结构化JSON。"
            schema = {
                "type": "object",
                "properties": {
                    "family_id": {"type": "string", "description": "家庭ID"},
                    "member_id": {"type": "string", "description": "成员ID"},
                    "start_date": {"type": "string", "description": "开始日期 ISO8601"},
                    "end_date": {"type": "string", "description": "结束日期 ISO8601"},
                    "limit": {"type": "integer", "description": "返回数量", "default": 20},
                    "offset": {"type": "integer", "description": "偏移量", "default": 0},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "query": {"type": "string", "description": "搜索关键词"},
                    "sort_by": {"type": "string", "enum": ["created_at", "updated_at", "name"]},
                    "include_archived": {"type": "boolean", "default": False},
                },
                "required": ["family_id"],
            }

            async def handler(args, _n=name):
                return {"content": [{"type": "text", "text": f"{_n}: 暂无数据"}]}

            sdk_tools.append(sdk_tool(name, desc, schema)(handler))

        mcp_server = create_sdk_mcp_server("secretary", "0.1.0", sdk_tools)
        options_kwargs["mcp_servers"] = {"secretary": mcp_server}
        options_kwargs["allowed_tools"] = [f"mcp__secretary__{tool_names_list[i]}" for i in range(min(tool_count, len(tool_names_list)))]

    options = ClaudeAgentOptions(**options_kwargs)

    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"  model: {model}")
    print(f"  system_prompt: {len(system_prompt)} chars")
    print(f"  tools: {tool_count}")
    print(f"  user_prompt: {user_prompt[:50]}...")
    print(f"{'='*60}")

    # Connect
    t0 = time.monotonic()
    client = ClaudeSDKClient(options=options)
    await client.connect()
    t_connected = time.monotonic()
    print(f"  connect: {_ms(t0)}ms")

    # Query
    t_query = time.monotonic()
    await client.query(user_prompt)

    print(f"\n  --- Messages received ---")
    msg_idx = 0
    first_thinking = None
    first_text = None
    first_assistant = None

    async for message in client.receive_response():
        elapsed = _ms(t_query)
        msg_type = type(message).__name__

        # Detect StreamEvent subtypes
        detail = ""
        if StreamEvent and isinstance(message, StreamEvent):
            event_type = getattr(message, "type", "?")
            detail = f" (event_type={event_type})"
            if event_type == "thinking_delta" and first_thinking is None:
                thinking_text = getattr(message, "thinking", "")
                first_thinking = elapsed
                detail += f" thinking_len={len(thinking_text)}"
            elif event_type == "text_delta" and first_text is None:
                first_text = elapsed
        elif isinstance(message, AssistantMessage):
            if first_assistant is None:
                first_assistant = elapsed
            blocks = getattr(message, "content", [])
            detail = f" (blocks={len(blocks)})"
        elif isinstance(message, ResultMessage):
            subtype = getattr(message, "subtype", "?")
            turns = getattr(message, "num_turns", 0)
            cost = getattr(message, "total_cost_usd", None)
            detail = f" (subtype={subtype}, turns={turns}, cost={cost})"

        if msg_idx < 20 or isinstance(message, ResultMessage):
            print(f"    [{msg_idx:3d}] +{elapsed:6d}ms  {msg_type:25s}{detail}")

        msg_idx += 1
        if isinstance(message, ResultMessage):
            break

    total = _ms(t_query)
    print(f"\n  --- Timing Summary ---")
    print(f"    Connect:                  {int((t_connected - t0) * 1000)}ms")
    print(f"    First thinking_delta:     {first_thinking}ms" if first_thinking else "    First thinking_delta:     N/A")
    print(f"    First text_delta:         {first_text}ms" if first_text else "    First text_delta:         N/A")
    print(f"    First AssistantMessage:   {first_assistant}ms" if first_assistant else "    First AssistantMessage:   N/A")
    print(f"    Total messages:           {msg_idx}")
    print(f"    Total query time:         {total}ms")
    print(f"    End-to-end:               {_ms(t0)}ms")

    await client.disconnect()

    return {
        "connect_ms": int((t_connected - t0) * 1000),
        "first_thinking_ms": first_thinking,
        "first_text_ms": first_text,
        "first_assistant_ms": first_assistant,
        "total_ms": total,
        "msg_count": msg_idx,
    }


async def main():
    print("=" * 60)
    print("Detailed SDK Message-Level Latency Benchmark")
    print("=" * 60)

    # Test A: Simple prompt, no tools (baseline)
    await run_detailed_benchmark(
        label="TEST A: Simple prompt, no tools",
        system_prompt="你是一个简洁的助手。",
        user_prompt="你好",
        tool_count=0,
    )

    # Test B: Large prompt, 38 tools, simple query (production-like, no tool calls)
    await run_detailed_benchmark(
        label="TEST B: Large prompt + 38 tools, simple query",
        system_prompt=LARGE_SYSTEM_PROMPT,
        user_prompt="你好",
        tool_count=38,
    )

    # Test C: Large prompt, 38 tools, complex query (will trigger tool calls)
    await run_detailed_benchmark(
        label="TEST C: Large prompt + 38 tools, complex query (tool calls)",
        system_prompt=LARGE_SYSTEM_PROMPT,
        user_prompt=COMPLEX_PROMPT,
        tool_count=38,
        max_turns=3,
    )


if __name__ == "__main__":
    asyncio.run(main())
