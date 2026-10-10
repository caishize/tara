#!/usr/bin/env python3
"""
Benchmark: thinking enabled vs disabled.

Proves whether CLAUDE_AGENT_THINKING_ENABLED=true is the root cause of 42s delay.
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


SYSTEM_PROMPT = """你是一个智能家庭秘书助手。你的任务是帮助家庭管理日常事务。

## 核心原则
1. 主动思考：理解用户真实意图
2. 工具调用：需要数据时主动调用工具
3. 简洁回复：用自然的中文回答

【当前时间】2026-02-14 00:48 (Asia/Shanghai)
【用户位置】广东省揭阳市
【家庭成员】
- 爸爸 (55岁)，妈妈 (53岁)，我 (28岁)，妹妹 (25岁)，外婆 (78岁)

## 已知信息
- 外婆有高血压，每月15号复诊
- 妹妹下个月生日(3月15日)
- 爸妈结婚纪念日是农历九月初九"""

USER_PROMPT = "帮我看看外婆下次复诊是什么时候？"


async def benchmark_with_thinking(thinking_enabled: bool):
    """Run a benchmark with thinking on or off."""
    from claude_agent_sdk import (
        ClaudeAgentOptions, ClaudeSDKClient,
        AssistantMessage, ResultMessage,
    )
    try:
        from claude_agent_sdk import StreamEvent
    except ImportError:
        StreamEvent = None

    from claude_agent_sdk import tool as sdk_tool, create_sdk_mcp_server

    model = os.getenv("CLAUDE_MODEL") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # 10 tools (lighter than 38, still representative)
    sdk_tools = []
    tool_names = [
        "get_family_members", "get_events", "get_reminders",
        "get_memories", "get_important_dates", "get_holidays",
        "get_weather", "convert_lunar_date", "view_tool_details",
        "get_briefing",
    ]
    for name in tool_names:
        desc = f"查询{name}相关数据"
        schema = {
            "type": "object",
            "properties": {
                "family_id": {"type": "string"},
                "member_id": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["family_id"],
        }

        async def handler(args, _n=name):
            return {"content": [{"type": "text", "text": f"{_n}: 暂无数据"}]}

        sdk_tools.append(sdk_tool(name, desc, schema)(handler))

    mcp_server = create_sdk_mcp_server("secretary", "0.1.0", sdk_tools)
    allowed = [f"mcp__secretary__{n}" for n in tool_names]

    options_kwargs = {
        "model": model,
        "system_prompt": SYSTEM_PROMPT,
        "max_turns": 1,
        "mcp_servers": {"secretary": mcp_server},
        "allowed_tools": allowed,
        "permission_mode": "bypassPermissions",
        "include_partial_messages": True,
    }

    if thinking_enabled:
        options_kwargs["max_thinking_tokens"] = 5000

    # Also set the cli settings
    cli_settings = {"alwaysThinkingEnabled": thinking_enabled}
    options_kwargs["settings"] = json.dumps(cli_settings)

    options = ClaudeAgentOptions(**options_kwargs)

    label = "THINKING ON" if thinking_enabled else "THINKING OFF"
    print(f"\n{'='*60}")
    print(f"  {label} (max_thinking_tokens={'5000' if thinking_enabled else 'N/A'})")
    print(f"  model: {model}")
    print(f"{'='*60}")

    # Connect
    t0 = time.monotonic()
    client = ClaudeSDKClient(options=options)
    await client.connect()
    t_conn = time.monotonic()
    print(f"  connect: {int((t_conn - t0) * 1000)}ms")

    # Query
    t_query = time.monotonic()
    await client.query(USER_PROMPT)

    first_thinking = None
    first_text = None
    first_assistant = None
    msg_idx = 0

    async for message in client.receive_response():
        elapsed = _ms(t_query)
        msg_type = type(message).__name__

        if StreamEvent and isinstance(message, StreamEvent):
            event_type = getattr(message, "type", None)
            # Check for thinking
            thinking = getattr(message, "thinking", None)
            text = getattr(message, "text", None)

            if thinking and first_thinking is None:
                first_thinking = elapsed
                print(f"    [{msg_idx:3d}] +{elapsed:6d}ms  FIRST THINKING DELTA (len={len(thinking)})")
            elif text and first_text is None:
                first_text = elapsed
                print(f"    [{msg_idx:3d}] +{elapsed:6d}ms  FIRST TEXT DELTA (len={len(text)})")
            elif msg_idx < 5:
                print(f"    [{msg_idx:3d}] +{elapsed:6d}ms  StreamEvent type={event_type} think={bool(thinking)} text={bool(text)}")
        elif isinstance(message, AssistantMessage):
            if first_assistant is None:
                first_assistant = elapsed
                blocks = getattr(message, "content", [])
                print(f"    [{msg_idx:3d}] +{elapsed:6d}ms  FIRST AssistantMessage (blocks={len(blocks)})")
        elif isinstance(message, ResultMessage):
            cost = getattr(message, "total_cost_usd", None)
            turns = getattr(message, "num_turns", 0)
            print(f"    [{msg_idx:3d}] +{elapsed:6d}ms  ResultMessage (turns={turns}, cost={cost})")
        elif msg_idx < 3:
            print(f"    [{msg_idx:3d}] +{elapsed:6d}ms  {msg_type}")

        msg_idx += 1
        if isinstance(message, ResultMessage):
            break

    total = _ms(t_query)
    print(f"\n  Summary:")
    print(f"    First thinking:    {first_thinking}ms" if first_thinking else "    First thinking:    N/A")
    print(f"    First text:        {first_text}ms" if first_text else "    First text:        N/A")
    print(f"    First assistant:   {first_assistant}ms" if first_assistant else "    First assistant:   N/A")
    print(f"    Total messages:    {msg_idx}")
    print(f"    Total time:        {total}ms")

    await client.disconnect()
    return {
        "thinking_enabled": thinking_enabled,
        "connect_ms": int((t_conn - t0) * 1000),
        "first_thinking_ms": first_thinking,
        "first_text_ms": first_text,
        "first_assistant_ms": first_assistant,
        "total_ms": total,
    }


async def main():
    print("=" * 60)
    print("Thinking Enabled vs Disabled Benchmark")
    print("=" * 60)

    # Test 1: Thinking OFF
    r_off = await benchmark_with_thinking(False)

    # Test 2: Thinking ON
    r_on = await benchmark_with_thinking(True)

    # Comparison
    print(f"\n{'='*60}")
    print("COMPARISON")
    print(f"{'='*60}")
    print(f"  Thinking OFF: first_msg={r_off.get('first_text_ms') or r_off.get('first_assistant_ms')}ms, total={r_off['total_ms']}ms")
    print(f"  Thinking ON:  first_think={r_on.get('first_thinking_ms')}ms, first_text={r_on.get('first_text_ms')}ms, total={r_on['total_ms']}ms")

    if r_on.get('first_thinking_ms') and r_off.get('first_assistant_ms'):
        delta = r_on['first_thinking_ms'] - r_off['first_assistant_ms']
        print(f"\n  Thinking overhead on first response: ~{delta}ms")


if __name__ == "__main__":
    asyncio.run(main())
