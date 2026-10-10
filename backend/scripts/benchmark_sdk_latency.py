#!/usr/bin/env python3
"""
Benchmark: Claude Agent SDK latency breakdown.

Measures:
  1. CLI subprocess connect time
  2. First query (cold) — includes MCP tool discovery + API TTFT
  3. Second query (warm/reuse) — no MCP discovery overhead
  4. Baseline: direct Anthropic API call (no SDK, no MCP)

Usage:
    cd backend
    python scripts/benchmark_sdk_latency.py
"""

import asyncio
import os
import sys
import time

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


SIMPLE_PROMPT = "回复'你好'两个字即可，不要多说。"
SYSTEM_PROMPT = "你是一个简洁的助手。只按用户要求回复，不要多说。"


# ---------------------------------------------------------------------------
# Test 1: Direct Anthropic API (baseline, no SDK, no MCP)
# ---------------------------------------------------------------------------

async def benchmark_direct_api():
    """Baseline: direct Anthropic Python SDK call."""
    from anthropic import AsyncAnthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", None)
    model = os.getenv("CLAUDE_MODEL") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = AsyncAnthropic(**client_kwargs)

    print(f"\n{'='*60}")
    print(f"TEST 1: Direct Anthropic API (baseline)")
    print(f"  model: {model}")
    print(f"  base_url: {base_url or 'default'}")
    print(f"{'='*60}")

    t0 = time.monotonic()
    first_token_at = None

    async with client.messages.stream(
        model=model,
        max_tokens=50,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": SIMPLE_PROMPT}],
    ) as stream:
        async for text in stream.text_stream:
            if first_token_at is None:
                first_token_at = time.monotonic()
                print(f"  First token: {_ms(t0)}ms")
            # consume rest
    total = _ms(t0)
    print(f"  Total:       {total}ms")
    return {"first_token_ms": _ms(t0) if first_token_at is None else int((first_token_at - t0) * 1000), "total_ms": total}


# ---------------------------------------------------------------------------
# Test 2: SDK cold start (new client + first query)
# ---------------------------------------------------------------------------

async def benchmark_sdk_cold():
    """SDK cold start: connect + first query."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, AssistantMessage, ResultMessage

    model = os.getenv("CLAUDE_MODEL") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    print(f"\n{'='*60}")
    print(f"TEST 2: SDK cold start (no MCP, no tools)")
    print(f"  model: {model}")
    print(f"{'='*60}")

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        max_turns=1,
        permission_mode="bypassPermissions",
        allowed_tools=[],
        include_partial_messages=True,
    )

    # Phase 1: Connect
    t_start = time.monotonic()
    client = ClaudeSDKClient(options=options)
    t_init = time.monotonic()
    print(f"  Client init:    {_ms(t_start)}ms")

    await client.connect()
    t_connected = time.monotonic()
    print(f"  Connect:        {int((t_connected - t_init) * 1000)}ms")

    # Phase 2: First query (cold)
    t_query = time.monotonic()
    await client.query(SIMPLE_PROMPT)

    first_token_at = None
    async for message in client.receive_response():
        if first_token_at is None:
            first_token_at = time.monotonic()
        if isinstance(message, ResultMessage):
            break

    t_done = time.monotonic()
    first_token_ms = int((first_token_at - t_query) * 1000) if first_token_at else None
    print(f"  First token (cold query):  {first_token_ms}ms")
    print(f"  Query total (cold):        {int((t_done - t_query) * 1000)}ms")
    print(f"  End-to-end (cold):         {_ms(t_start)}ms")

    # Phase 3: Second query (warm — CLI process already running)
    t_query2 = time.monotonic()
    await client.query(SIMPLE_PROMPT)

    first_token_at2 = None
    async for message in client.receive_response():
        if first_token_at2 is None:
            first_token_at2 = time.monotonic()
        if isinstance(message, ResultMessage):
            break

    t_done2 = time.monotonic()
    first_token_ms2 = int((first_token_at2 - t_query2) * 1000) if first_token_at2 else None
    print(f"  First token (warm query):  {first_token_ms2}ms")
    print(f"  Query total (warm):        {int((t_done2 - t_query2) * 1000)}ms")

    await client.disconnect()

    return {
        "connect_ms": int((t_connected - t_start) * 1000),
        "cold_first_token_ms": first_token_ms,
        "warm_first_token_ms": first_token_ms2,
    }


# ---------------------------------------------------------------------------
# Test 3: SDK with MCP tools (simulates production)
# ---------------------------------------------------------------------------

async def benchmark_sdk_with_mcp():
    """SDK with MCP tools — simulates production setup."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, AssistantMessage, ResultMessage

    model = os.getenv("CLAUDE_MODEL") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # Build a minimal MCP server with N dummy tools to measure tool discovery overhead
    from claude_agent_sdk import tool as sdk_tool, create_sdk_mcp_server

    # Create dummy tools to simulate the 38-tool production setup
    TOOL_COUNT = 38
    sdk_tools = []
    for i in range(TOOL_COUNT):
        name = f"dummy_tool_{i}"
        description = f"A dummy tool number {i} that does nothing. Used for benchmarking MCP tool discovery overhead."
        input_schema = {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": f"Parameter 1 for tool {i}"},
                "param2": {"type": "integer", "description": f"Parameter 2 for tool {i}"},
            },
            "required": ["param1"],
        }

        async def handler(args, _name=name):
            return {"content": [{"type": "text", "text": f"Tool {_name} executed"}]}

        decorated = sdk_tool(name, description, input_schema)(handler)
        sdk_tools.append(decorated)

    mcp_server = create_sdk_mcp_server(
        name="benchmark",
        version="0.1.0",
        tools=sdk_tools,
    )

    print(f"\n{'='*60}")
    print(f"TEST 3: SDK with {TOOL_COUNT} MCP tools")
    print(f"  model: {model}")
    print(f"{'='*60}")

    allowed_tools = [f"mcp__benchmark__{f'dummy_tool_{i}'}" for i in range(TOOL_COUNT)]

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        max_turns=1,
        mcp_servers={"benchmark": mcp_server},
        allowed_tools=allowed_tools,
        permission_mode="bypassPermissions",
        include_partial_messages=True,
    )

    # Phase 1: Connect
    t_start = time.monotonic()
    client = ClaudeSDKClient(options=options)
    t_init = time.monotonic()
    print(f"  Client init:    {_ms(t_start)}ms")

    await client.connect()
    t_connected = time.monotonic()
    print(f"  Connect:        {int((t_connected - t_init) * 1000)}ms")

    # Phase 2: First query (cold — MCP handshake here)
    t_query = time.monotonic()
    await client.query(SIMPLE_PROMPT)

    first_token_at = None
    async for message in client.receive_response():
        if first_token_at is None:
            first_token_at = time.monotonic()
        if isinstance(message, ResultMessage):
            break

    t_done = time.monotonic()
    first_token_ms = int((first_token_at - t_query) * 1000) if first_token_at else None
    print(f"  First token (cold, {TOOL_COUNT} tools): {first_token_ms}ms")
    print(f"  Query total (cold):           {int((t_done - t_query) * 1000)}ms")
    print(f"  End-to-end (cold):            {_ms(t_start)}ms")

    # Phase 3: Second query (warm)
    t_query2 = time.monotonic()
    await client.query(SIMPLE_PROMPT)

    first_token_at2 = None
    async for message in client.receive_response():
        if first_token_at2 is None:
            first_token_at2 = time.monotonic()
        if isinstance(message, ResultMessage):
            break

    t_done2 = time.monotonic()
    first_token_ms2 = int((first_token_at2 - t_query2) * 1000) if first_token_at2 else None
    print(f"  First token (warm):           {first_token_ms2}ms")
    print(f"  Query total (warm):           {int((t_done2 - t_query2) * 1000)}ms")

    await client.disconnect()

    return {
        "connect_ms": int((t_connected - t_start) * 1000),
        "cold_first_token_ms": first_token_ms,
        "warm_first_token_ms": first_token_ms2,
    }


# ---------------------------------------------------------------------------
# Test 3b: SDK with large system prompt (simulates production)
# ---------------------------------------------------------------------------

async def benchmark_sdk_large_prompt():
    """SDK with a production-sized system prompt + 38 tools with full schemas."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage
    from claude_agent_sdk import tool as sdk_tool, create_sdk_mcp_server

    model = os.getenv("CLAUDE_MODEL") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    # Build realistic tool definitions (matching production schema complexity)
    TOOL_COUNT = 38
    sdk_tools = []
    TOOL_NAMES = [
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
    for i in range(TOOL_COUNT):
        name = TOOL_NAMES[i] if i < len(TOOL_NAMES) else f"tool_{i}"
        description = (
            f"查询或操作{name}相关数据。支持按时间范围、成员ID、标签等条件筛选。"
            f"返回结构化JSON数据，包含分页信息。当用户询问相关内容时调用此工具。"
            f"注意：调用前确认必需参数已提供，可选参数使用默认值。"
        )
        input_schema = {
            "type": "object",
            "properties": {
                "family_id": {"type": "string", "description": "家庭ID（系统自动注入）"},
                "member_id": {"type": "string", "description": "成员ID，可选"},
                "start_date": {"type": "string", "description": "开始日期，ISO 8601格式"},
                "end_date": {"type": "string", "description": "结束日期，ISO 8601格式"},
                "limit": {"type": "integer", "description": "返回数量限制，默认20", "default": 20},
                "offset": {"type": "integer", "description": "分页偏移量", "default": 0},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "标签筛选"},
                "query": {"type": "string", "description": "搜索关键词"},
                "sort_by": {"type": "string", "enum": ["created_at", "updated_at", "name"], "description": "排序字段"},
                "include_archived": {"type": "boolean", "description": "是否包含已归档项", "default": False},
            },
            "required": ["family_id"],
        }

        async def handler(args, _n=name):
            return {"content": [{"type": "text", "text": f"Tool {_n} executed"}]}

        sdk_tools.append(sdk_tool(name, description, input_schema)(handler))

    mcp_server = create_sdk_mcp_server("secretary", "0.1.0", sdk_tools)

    # Build a production-sized system prompt (~4000 chars)
    large_system_prompt = """你是一个智能家庭秘书助手。你的任务是帮助家庭管理日常事务、规划行程、记录重要信息。

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
- 农历日期：当用户提到农历日期（如"初二"、"正月十五"等），必须调用 convert_lunar_date 工具进行转换

## 敏感操作
涉及支付、删除等敏感操作时，系统会自动生成待确认操作，由用户确认后执行。

【当前时间】
2026-02-14 00:48 (Asia/Shanghai)

【用户位置】
广东省揭阳市

【家庭成员】
- 爸爸 (id: member-001): 55岁，退休工程师，爱好钓鱼和象棋
- 妈妈 (id: member-002): 53岁，家庭主妇，爱好跳广场舞和种花
- 我 (id: member-003): 28岁，软件工程师，爱好编程和阅读
- 妹妹 (id: member-004): 25岁，设计师，爱好画画和摄影
- 外婆 (id: member-005): 78岁，退休教师，需要关注健康状况

【已连接服务】
天气查询, 日历同步, 礼物推荐

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

## 家庭成员画像
### 爸爸
性格温和内敛，注重传统礼节。退休后生活规律，喜欢清静。与老友保持定期联系。
对新科技感兴趣但学习较慢，需要耐心指导。关心子女发展但不善表达。
最近关注：学习使用微信视频通话、计划春季钓鱼比赛

### 妈妈
热情开朗，社交活跃。是家庭的核心组织者，负责大小事务安排。
对家人健康饮食很关注，经常研究养生食谱。喜欢在朋友圈分享生活。
最近关注：广场舞比赛准备、春季养生食谱、外婆健康状况

### 外婆
慈祥和蔼，记忆力略有下降。喜欢和孙辈聊天，经常回忆往事。
需要定期服药和复诊，饮食需要低盐低脂。偶尔会忘记吃药。
最近关注：春节后身体恢复、新一季评书更新

## 本次会话之前的对话摘要
用户之前询问了关于妹妹生日礼物的建议，助手推荐了几款画具和摄影相关的礼物。
用户还问了外婆下次复诊的时间，助手提醒是2月15日。
用户提到想计划清明节全家去潮汕地区短途旅行。"""

    prompt_len = len(large_system_prompt)
    est_tokens = prompt_len // 2  # rough estimate for Chinese

    print(f"\n{'='*60}")
    print(f"TEST 3b: SDK with {TOOL_COUNT} tools + large system prompt")
    print(f"  model: {model}")
    print(f"  system prompt: ~{prompt_len} chars (~{est_tokens} tokens est.)")
    print(f"{'='*60}")

    allowed_tools = [f"mcp__secretary__{TOOL_NAMES[i]}" for i in range(TOOL_COUNT)]

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=large_system_prompt,
        max_turns=1,
        mcp_servers={"secretary": mcp_server},
        allowed_tools=allowed_tools,
        permission_mode="bypassPermissions",
        include_partial_messages=True,
    )

    # Phase 1: Connect
    t_start = time.monotonic()
    client = ClaudeSDKClient(options=options)
    await client.connect()
    t_connected = time.monotonic()
    connect_ms = int((t_connected - t_start) * 1000)
    print(f"  Connect:        {connect_ms}ms")

    # Phase 2: First query (cold)
    t_query = time.monotonic()
    await client.query("帮我看看外婆下次复诊是什么时候？还有妹妹生日快到了，有什么新的礼物推荐吗？")

    first_token_at = None
    msg_count = 0
    async for message in client.receive_response():
        msg_count += 1
        if first_token_at is None:
            first_token_at = time.monotonic()
            msg_type = type(message).__name__
            print(f"  First msg type:   {msg_type}")
        if isinstance(message, ResultMessage):
            break

    t_done = time.monotonic()
    first_token_ms = int((first_token_at - t_query) * 1000) if first_token_at else None
    total_ms = int((t_done - t_query) * 1000)
    print(f"  First msg (cold):  {first_token_ms}ms")
    print(f"  Query total (cold): {total_ms}ms  ({msg_count} messages)")
    print(f"  End-to-end (cold):  {_ms(t_start)}ms")

    # Phase 3: Warm query
    t_query2 = time.monotonic()
    await client.query("好的，谢谢！")

    first_token_at2 = None
    async for message in client.receive_response():
        if first_token_at2 is None:
            first_token_at2 = time.monotonic()
        if isinstance(message, ResultMessage):
            break

    t_done2 = time.monotonic()
    first_token_ms2 = int((first_token_at2 - t_query2) * 1000) if first_token_at2 else None
    print(f"  First msg (warm):  {first_token_ms2}ms")
    print(f"  Query total (warm): {int((t_done2 - t_query2) * 1000)}ms")

    await client.disconnect()

    return {
        "connect_ms": connect_ms,
        "cold_first_token_ms": first_token_ms,
        "cold_total_ms": total_ms,
        "warm_first_token_ms": first_token_ms2,
    }


# ---------------------------------------------------------------------------
# Test 4: SDK with 0 tools vs 38 tools (isolate tool discovery cost)
# ---------------------------------------------------------------------------

async def benchmark_tool_count_impact():
    """Compare 0 tools vs 10 tools vs 38 tools to isolate MCP overhead."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

    model = os.getenv("CLAUDE_MODEL") or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    from claude_agent_sdk import tool as sdk_tool, create_sdk_mcp_server

    print(f"\n{'='*60}")
    print(f"TEST 4: Tool count impact (0 vs 10 vs 38)")
    print(f"{'='*60}")

    for tool_count in [0, 10, 38]:
        sdk_tools = []
        for i in range(tool_count):
            name = f"tool_{i}"
            desc = f"Tool {i} description for benchmarking."
            schema = {
                "type": "object",
                "properties": {"p": {"type": "string"}},
            }

            async def handler(args, _n=name):
                return {"content": [{"type": "text", "text": "ok"}]}

            sdk_tools.append(sdk_tool(name, desc, schema)(handler))

        options_kwargs = {
            "model": model,
            "system_prompt": SYSTEM_PROMPT,
            "max_turns": 1,
            "allowed_tools": [],
            "permission_mode": "bypassPermissions",
            "include_partial_messages": True,
        }
        if tool_count > 0:
            mcp = create_sdk_mcp_server("bench", "0.1", sdk_tools)
            options_kwargs["mcp_servers"] = {"bench": mcp}
            options_kwargs["allowed_tools"] = [f"mcp__bench__tool_{i}" for i in range(tool_count)]

        options = ClaudeAgentOptions(**options_kwargs)

        t_start = time.monotonic()
        client = ClaudeSDKClient(options=options)
        await client.connect()
        t_connected = time.monotonic()

        await client.query(SIMPLE_PROMPT)
        first_token_at = None
        async for message in client.receive_response():
            if first_token_at is None:
                first_token_at = time.monotonic()
            if isinstance(message, ResultMessage):
                break

        t_done = time.monotonic()
        connect_ms = int((t_connected - t_start) * 1000)
        ftk = int((first_token_at - t_connected) * 1000) if first_token_at else None
        total = int((t_done - t_start) * 1000)

        print(f"  {tool_count:2d} tools => connect={connect_ms}ms, query_to_first_token={ftk}ms, total={total}ms")

        await client.disconnect()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("=" * 60)
    print("Claude Agent SDK Latency Benchmark")
    print("=" * 60)

    # Test 1: Baseline
    try:
        r1 = await benchmark_direct_api()
    except Exception as e:
        print(f"  FAILED: {e}")
        r1 = None

    # Test 2: SDK without MCP
    try:
        r2 = await benchmark_sdk_cold()
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback; traceback.print_exc()
        r2 = None

    # Test 3: SDK with 38 MCP tools
    try:
        r3 = await benchmark_sdk_with_mcp()
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback; traceback.print_exc()
        r3 = None

    # Test 3b: SDK with large system prompt (production simulation)
    r3b = None
    try:
        r3b = await benchmark_sdk_large_prompt()
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback; traceback.print_exc()

    # Test 4: Tool count comparison (skip to save time — already proven not a factor)
    # try:
    #     await benchmark_tool_count_impact()
    # except Exception as e:
    #     print(f"  FAILED: {e}")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    if r1:
        print(f"  Direct API first token:              {r1['first_token_ms']}ms")
    if r2:
        print(f"  SDK (no tools) connect:               {r2['connect_ms']}ms")
        print(f"  SDK (no tools) cold 1st msg:          {r2['cold_first_token_ms']}ms")
        print(f"  SDK (no tools) warm 1st msg:          {r2['warm_first_token_ms']}ms")
    if r3:
        print(f"  SDK (38 tools, tiny prompt) connect:  {r3['connect_ms']}ms")
        print(f"  SDK (38 tools, tiny prompt) cold msg: {r3['cold_first_token_ms']}ms")
        print(f"  SDK (38 tools, tiny prompt) warm msg: {r3['warm_first_token_ms']}ms")
    if r3b:
        print(f"  SDK (38 tools, LARGE prompt) connect: {r3b['connect_ms']}ms")
        print(f"  SDK (38 tools, LARGE prompt) cold msg:{r3b['cold_first_token_ms']}ms")
        print(f"  SDK (38 tools, LARGE prompt) cold tot:{r3b['cold_total_ms']}ms")
        print(f"  SDK (38 tools, LARGE prompt) warm msg:{r3b['warm_first_token_ms']}ms")

    if r3 and r3b:
        prompt_impact = (r3b['cold_first_token_ms'] or 0) - (r3['cold_first_token_ms'] or 0)
        print(f"\n  Large prompt overhead vs tiny:        ~{prompt_impact}ms")
    if r1 and r3b:
        total_overhead = (r3b['cold_first_token_ms'] or 0) - (r1['first_token_ms'] or 0)
        print(f"  SDK+MCP+large prompt vs direct API:   ~{total_overhead}ms")


if __name__ == "__main__":
    asyncio.run(main())
