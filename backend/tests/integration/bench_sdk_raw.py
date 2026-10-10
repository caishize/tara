#!/usr/bin/env python3
"""
Standalone SDK Latency Benchmark — no DB, no Redis, no MCP tools, no context assembly.

Compares raw Claude Agent SDK performance against variables that exist in the
full Secretary pipeline to isolate whether slowness is in the Claude API itself
or in our infrastructure.

Tests:
    A. Minimal SDK      — no tools, minimal system prompt
    B. With dummy tools — 30 MCP tools registered (matching production count)
    C. Large system prompt — ~6000-token prompt (matching production context)

Each test runs twice (cold + warm) on the same client connection.

Usage:
    cd backend
    python tests/integration/bench_sdk_raw.py

Environment:
    ANTHROPIC_API_KEY   — required
    ANTHROPIC_BASE_URL  — optional (for DashScope proxy)
    CLAUDE_MODEL        — optional override for ANTHROPIC_MODEL
    ANTHROPIC_MODEL     — default: claude-sonnet-4-20250514
"""

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

# ---------------------------------------------------------------------------
# Setup: ensure backend/src is importable and .env is loaded
# ---------------------------------------------------------------------------

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _BACKEND_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BACKEND_DIR, ".env"))
except ImportError:
    pass  # dotenv is optional; env vars may be set externally


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_PROMPT = "帮我想一个周末活动计划"
MINIMAL_SYSTEM_PROMPT = "You are a helpful assistant."
THINKING_BUDGET = 5000  # matches production default in AgentRunner

# Production-realistic tool names (38 tools as in mcp_tool_server.py)
PRODUCTION_TOOL_NAMES: List[str] = [
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
    "search_events", "get_notifications", "search_web",
]

# ~6000 token system prompt matching production ContextAssembler output size
LARGE_SYSTEM_PROMPT = """你是一个智能家庭秘书助手。你的任务是帮助家庭管理日常事务、规划行程、记录重要信息。

## 核心原则
1. **主动思考**: 理解用户真实意图，不要机械执行
2. **工具调用**: 需要数据时主动调用工具查询，不要凭记忆回答
3. **简洁回复**: 用自然的中文回答，避免冗长
4. **家庭导向**: 始终站在家庭整体的角度考虑

## 工具使用指南
- 查询数据前先用对应的查询工具获取最新信息
- 修改数据前先确认目标记录存在
- 复杂任务可以分步执行多个工具
- 工具执行结果中的 [#xxxxxxxx] 是执行记录短ID，需要查看完整详情时使用 view_tool_details 传入完整 UUID
- **农历日期处理**：当用户提到农历日期（如"初二"、"正月十五"、"腊月"等），必须先调用 convert_lunar_date 工具进行阳历转换
- **天气查询**：支持当前天气和未来7天预报，自动使用用户所在城市

## 敏感操作处理
涉及支付、删除、发送消息等敏感操作时，系统会自动生成 PendingAction 待确认操作。
你需要向用户清晰说明操作内容和影响，等待用户确认后系统才会执行。
不可中断的工具包括：create_trip, book_ticket, send_message, make_payment

## 回复格式要求
- 使用自然流畅的中文
- 涉及多项信息时使用分点列举
- 时间日期使用用户时区显示
- 金额使用人民币单位
- 不要使用 markdown 代码块，除非展示技术内容

【当前时间】
2026-03-03 10:30 (Asia/Shanghai)

【用户位置】
广东省揭阳市

【家庭成员】
- 爸爸 (id: member-001): 55岁，退休工程师，爱好钓鱼和象棋
  - 健康状况：轻度高血压，服用降压药，医生建议减少钠盐摄入
  - 近期关注：学习使用微信视频通话，计划春季钓鱼比赛
- 妈妈 (id: member-002): 53岁，家庭主妇，爱好跳广场舞和种花
  - 健康状况：海鲜过敏
  - 近期关注：广场舞比赛准备，春季养生食谱
- 我 (id: member-003): 28岁，软件工程师，爱好编程和阅读
  - 近期关注：工作项目截止日期，健身计划
- 妹妹 (id: member-004): 25岁，设计师，爱好画画和摄影
  - 近期关注：个人作品展准备，搬新家装修
- 外婆 (id: member-005): 78岁，退休教师
  - 健康状况：高血压、轻度糖尿病，每月15号到市人民医院复诊
  - 近期关注：春节后身体恢复，新一季评书更新

【已连接服务】
天气查询 (OpenWeather), 日历同步 (Google Calendar), 礼物推荐, 网页搜索 (Tavily)

【数据概览】
事件: 23条, 记忆: 45条, 洞察: 12条, 行程: 3条, 重要日期: 15条

## 你对这个家庭的了解

### 日常作息与习惯
- 爸爸每天早上6点起床去公园钓鱼，周末会和老朋友下棋
- 妈妈负责家庭日常采购，每周三去菜市场，周末做家庭大餐
- 全家每月第一个周日聚餐，通常在家里做饭，偶尔去外面吃潮汕火锅
- 外婆有高血压和轻度糖尿病，每天需要按时服药（早晚各一次），每月15号到市人民医院复诊

### 重要日期
- 妹妹生日: 3月15日（下周六），去年送了画具套装，今年考虑摄影相关
- 爸妈结婚纪念日: 农历九月初九（重阳节）
- 外婆生日: 农历二月初二（龙抬头）
- 家庭年度旅行: 通常安排在国庆假期，今年计划去云南
- 清明节: 全家计划去潮汕地区短途旅行

### 家庭偏好与禁忌
- 妈妈对海鲜过敏，选择餐厅和食谱时需要注意
- 外婆饮食需要低盐低脂，不能吃太甜的食物
- 爸爸不喜欢太嘈杂的环境，偏好安静的活动
- 妹妹喜欢ins风的装饰，房间布置偏北欧简约
- 全家人都喜欢喝功夫茶，家里每天下午有茶歇时间

### 近期对话摘要
用户之前询问了关于妹妹生日礼物的建议，助手推荐了几款画具和摄影相关的礼物，
包括富士instax mini Evo拍立得和Adobe Lightroom年度订阅。用户还问了外婆下次
复诊的时间，助手提醒是3月15日，恰好与妹妹生日同一天。用户提到想计划清明节
全家去潮汕地区短途旅行，需要考虑外婆的行动能力和妈妈的海鲜过敏。

### 家庭成员画像

#### 爸爸
性格温和内敛，注重传统礼节。退休后生活规律，喜欢清静。与三位老友保持每周
固定的象棋聚会。对新科技感兴趣但学习较慢，需要耐心指导。关心子女发展但不
善表达，经常通过妈妈传话。最近在学习用智能手机拍照和发朋友圈。

#### 妈妈
热情开朗，社交活跃。是家庭的核心组织者，负责大小事务的协调和安排。对家人
健康饮食非常关注，经常研究养生食谱和中医调理方法。喜欢在朋友圈分享生活，
是广场舞队的队长。与邻居关系很好，经常互送自家种的蔬菜。

#### 外婆
慈祥和蔼，记忆力略有下降。喜欢和孙辈聊天，经常回忆年轻时当教师的往事。
需要定期服药和复诊，偶尔会忘记吃药。喜欢听评书（尤其是单田芳的作品）和看
戏曲节目。天气好的时候喜欢在小区里散步，与同龄老人聊天。

#### 妹妹
充满创意和活力，审美品味独特。工作认真负责，正在准备个人设计作品展。
搬新家后热衷于装修布置，喜欢逛宜家和各种家居店。周末经常去咖啡馆画画
或者去户外摄影。与哥哥（用户）关系亲密，经常一起讨论科技产品。

## 今日日程安排
- 09:00 团队站会（已完成）
- 14:00 项目评审会议
- 16:00 妹妹来家里喝下午茶
- 19:00 全家晚餐

## Secretary Notes
- 妹妹生日快到了（3月15日），需要提醒用户准备礼物
- 外婆3月15日复诊，需要安排陪同
- 清明节旅行计划尚未确定具体日期和行程"""


# ---------------------------------------------------------------------------
# Timing result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TimingResult:
    """Immutable timing result for a single benchmark run."""

    label: str
    connect_ms: int
    time_to_first_message_ms: Optional[int]
    time_to_first_thinking_ms: Optional[int]
    time_to_first_text_ms: Optional[int]
    total_ms: int
    message_count: int
    first_message_type: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_model() -> str:
    return (
        os.getenv("CLAUDE_MODEL")
        or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    )


def _build_env() -> dict:
    """Build env dict for the CLI subprocess (mirrors AgentRunner._build_cli_env)."""
    env = {}
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "")
    if api_key:
        env["ANTHROPIC_API_KEY"] = api_key
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    # Prevent "nested session" error when running inside Claude Code
    env["CLAUDECODE"] = ""
    return env


def _build_dummy_tools(count: int):
    """Build N dummy MCP tools matching production schema complexity."""
    from claude_agent_sdk import tool as sdk_tool, create_sdk_mcp_server

    sdk_tools = []
    for i in range(count):
        name = PRODUCTION_TOOL_NAMES[i] if i < len(PRODUCTION_TOOL_NAMES) else f"tool_{i}"
        description = (
            f"查询或操作{name}相关数据。支持按时间范围、成员ID、标签等条件筛选。"
            f"返回结构化JSON数据，包含分页信息。当用户询问相关内容时调用此工具。"
        )
        input_schema = {
            "type": "object",
            "properties": {
                "family_id": {"type": "string", "description": "家庭ID（系统自动注入）"},
                "member_id": {"type": "string", "description": "成员ID，可选"},
                "start_date": {"type": "string", "description": "开始日期 ISO 8601"},
                "end_date": {"type": "string", "description": "结束日期 ISO 8601"},
                "limit": {"type": "integer", "description": "返回数量限制", "default": 20},
                "offset": {"type": "integer", "description": "分页偏移量", "default": 0},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "标签筛选",
                },
                "query": {"type": "string", "description": "搜索关键词"},
                "sort_by": {
                    "type": "string",
                    "enum": ["created_at", "updated_at", "name"],
                    "description": "排序字段",
                },
                "include_archived": {
                    "type": "boolean",
                    "description": "是否包含已归档项",
                    "default": False,
                },
            },
            "required": ["family_id"],
        }

        async def handler(args, _n=name):
            return {"content": [{"type": "text", "text": f"{_n}: no data available"}]}

        sdk_tools.append(sdk_tool(name, description, input_schema)(handler))

    mcp_server = create_sdk_mcp_server(
        name="secretary",
        version="1.0.0",
        tools=sdk_tools,
    )
    allowed = [
        f"mcp__secretary__{PRODUCTION_TOOL_NAMES[i]}"
        if i < len(PRODUCTION_TOOL_NAMES)
        else f"mcp__secretary__tool_{i}"
        for i in range(count)
    ]
    return mcp_server, allowed


# ---------------------------------------------------------------------------
# Core benchmark runner
# ---------------------------------------------------------------------------

async def run_single_query(
    client,
    prompt: str,
    label: str,
    t_base: float,
) -> TimingResult:
    """Send one query and measure all timing milestones."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ThinkingBlock

    try:
        from claude_agent_sdk import StreamEvent
    except ImportError:
        StreamEvent = None

    t_query = time.monotonic()
    await client.query(prompt)

    first_msg_at: Optional[float] = None
    first_thinking_at: Optional[float] = None
    first_text_at: Optional[float] = None
    first_msg_type: Optional[str] = None
    msg_count = 0

    async for message in client.receive_response():
        now = time.monotonic()
        msg_count += 1

        if first_msg_at is None:
            first_msg_at = now
            first_msg_type = type(message).__name__

        # Detect thinking content
        if first_thinking_at is None:
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ThinkingBlock):
                        first_thinking_at = now
                        break
            elif StreamEvent is not None and isinstance(message, StreamEvent):
                event = getattr(message, "event", None)
                if isinstance(event, dict):
                    etype = event.get("type", "")
                    if etype == "thinking_delta":
                        first_thinking_at = now
                    elif etype == "content_block_start":
                        block = event.get("content_block", {})
                        if isinstance(block, dict) and block.get("type") == "thinking":
                            first_thinking_at = now

        # Detect text content
        if first_text_at is None:
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text.strip():
                        first_text_at = now
                        break
            elif StreamEvent is not None and isinstance(message, StreamEvent):
                event = getattr(message, "event", None)
                if isinstance(event, dict):
                    etype = event.get("type", "")
                    delta_text = event.get("text", "")
                    if etype == "text_delta" and delta_text:
                        first_text_at = now

        if isinstance(message, ResultMessage):
            break

    t_done = time.monotonic()

    def _delta_ms(t: Optional[float]) -> Optional[int]:
        if t is None:
            return None
        return int((t - t_query) * 1000)

    return TimingResult(
        label=label,
        connect_ms=int((t_query - t_base) * 1000),
        time_to_first_message_ms=_delta_ms(first_msg_at),
        time_to_first_thinking_ms=_delta_ms(first_thinking_at),
        time_to_first_text_ms=_delta_ms(first_text_at),
        total_ms=int((t_done - t_query) * 1000),
        message_count=msg_count,
        first_message_type=first_msg_type,
    )


async def run_benchmark(
    test_label: str,
    system_prompt: str,
    tool_count: int = 0,
    enable_thinking: bool = False,
) -> List[TimingResult]:
    """Run a benchmark with cold + warm queries on a single client connection."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

    model = _get_model()
    cli_env = _build_env()

    print(f"\n{'=' * 70}")
    print(f"  {test_label}")
    print(f"  model:          {model}")
    print(f"  system_prompt:  {len(system_prompt)} chars (~{len(system_prompt) // 2} tokens est.)")
    print(f"  tools:          {tool_count}")
    print(f"  thinking:       {'enabled' if enable_thinking else 'disabled'}")
    print(f"  base_url:       {os.getenv('ANTHROPIC_BASE_URL', 'default')}")
    print(f"{'=' * 70}")

    options_kwargs = {
        "model": model,
        "system_prompt": system_prompt,
        "max_turns": 1,
        "allowed_tools": [],
        "permission_mode": "bypassPermissions",
        "include_partial_messages": True,
        "env": cli_env,
    }

    if enable_thinking:
        options_kwargs["max_thinking_tokens"] = THINKING_BUDGET

    if tool_count > 0:
        mcp_server, allowed_tools = _build_dummy_tools(tool_count)
        options_kwargs["mcp_servers"] = {"secretary": mcp_server}
        options_kwargs["allowed_tools"] = allowed_tools

    options = ClaudeAgentOptions(**options_kwargs)

    results: List[TimingResult] = []

    # --- Connect ---
    t_start = time.monotonic()
    client = ClaudeSDKClient(options=options)
    await client.connect()
    t_connected = time.monotonic()
    connect_ms = int((t_connected - t_start) * 1000)
    print(f"  connect: {connect_ms}ms")

    try:
        # --- Cold query ---
        print(f"\n  [Cold] Sending: {USER_PROMPT}")
        cold = await run_single_query(client, USER_PROMPT, "cold", t_connected)
        results.append(cold)
        _print_result("Cold", cold)

        # --- Warm query ---
        print(f"\n  [Warm] Sending: {USER_PROMPT}")
        t_warm_base = time.monotonic()
        warm = await run_single_query(client, USER_PROMPT, "warm", t_warm_base)
        results.append(warm)
        _print_result("Warm", warm)

    finally:
        await client.disconnect()

    return results


def _print_result(phase: str, r: TimingResult) -> None:
    """Print a single timing result."""
    print(f"  [{phase}] Results:")
    print(f"    First message:    {_fmt(r.time_to_first_message_ms)} ({r.first_message_type})")
    print(f"    First thinking:   {_fmt(r.time_to_first_thinking_ms)}")
    print(f"    First text:       {_fmt(r.time_to_first_text_ms)}")
    print(f"    Total:            {r.total_ms}ms ({r.message_count} messages)")


def _fmt(ms: Optional[int]) -> str:
    return f"{ms}ms" if ms is not None else "N/A"


# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

def print_comparison_table(all_results: dict) -> None:
    """Print a formatted comparison table of all benchmark results."""
    print(f"\n{'=' * 100}")
    print("COMPARISON TABLE")
    print(f"{'=' * 100}")

    # Header
    header = (
        f"{'Test':<45s} | "
        f"{'Phase':<5s} | "
        f"{'1st Msg':>8s} | "
        f"{'1st Think':>10s} | "
        f"{'1st Text':>9s} | "
        f"{'Total':>8s} | "
        f"{'Msgs':>5s}"
    )
    print(header)
    print("-" * 100)

    for test_name, results in all_results.items():
        for r in results:
            row = (
                f"{test_name:<45s} | "
                f"{r.label:<5s} | "
                f"{_fmt(r.time_to_first_message_ms):>8s} | "
                f"{_fmt(r.time_to_first_thinking_ms):>10s} | "
                f"{_fmt(r.time_to_first_text_ms):>9s} | "
                f"{r.total_ms:>7d}ms | "
                f"{r.message_count:>5d}"
            )
            print(row)

    print(f"{'=' * 100}")

    # Delta analysis
    print("\nDELTA ANALYSIS (warm cold-to-warm improvement):")
    for test_name, results in all_results.items():
        if len(results) >= 2:
            cold, warm = results[0], results[1]
            cold_ttft = cold.time_to_first_text_ms or cold.time_to_first_message_ms
            warm_ttft = warm.time_to_first_text_ms or warm.time_to_first_message_ms
            if cold_ttft is not None and warm_ttft is not None:
                delta = cold_ttft - warm_ttft
                print(f"  {test_name}: cold={cold_ttft}ms, warm={warm_ttft}ms, saved={delta}ms")

    # Cross-test comparison
    test_names = list(all_results.keys())
    if len(test_names) >= 2:
        print("\nCROSS-TEST OVERHEAD (cold query, first text or first message):")
        baseline_name = test_names[0]
        baseline = all_results[baseline_name]
        baseline_ms = (
            baseline[0].time_to_first_text_ms
            or baseline[0].time_to_first_message_ms
        )
        if baseline_ms is not None:
            for name in test_names[1:]:
                other = all_results[name]
                other_ms = (
                    other[0].time_to_first_text_ms
                    or other[0].time_to_first_message_ms
                )
                if other_ms is not None:
                    overhead = other_ms - baseline_ms
                    print(f"  {name} vs {baseline_name}: +{overhead}ms overhead")


# ---------------------------------------------------------------------------
# Direct API baseline (no SDK, no CLI subprocess)
# ---------------------------------------------------------------------------

async def benchmark_direct_api() -> Optional[TimingResult]:
    """Baseline: direct Anthropic Python SDK call (no Agent SDK, no CLI)."""
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        print("\n  [SKIP] anthropic package not installed, skipping direct API baseline")
        return None

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    model = _get_model()

    if not api_key:
        print("\n  [SKIP] ANTHROPIC_API_KEY not set")
        return None

    print(f"\n{'=' * 70}")
    print(f"  TEST 0: Direct Anthropic API (baseline, no SDK)")
    print(f"  model:    {model}")
    print(f"  base_url: {base_url or 'default'}")
    print(f"{'=' * 70}")

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = AsyncAnthropic(**client_kwargs)

    t0 = time.monotonic()
    first_token_at: Optional[float] = None

    try:
        async with client.messages.stream(
            model=model,
            max_tokens=1024,
            system=MINIMAL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_PROMPT}],
        ) as stream:
            async for text in stream.text_stream:
                if first_token_at is None:
                    first_token_at = time.monotonic()
    except Exception as e:
        print(f"  FAILED: {e}")
        return None

    t_done = time.monotonic()
    ttft = int((first_token_at - t0) * 1000) if first_token_at else None
    total = int((t_done - t0) * 1000)

    result = TimingResult(
        label="api",
        connect_ms=0,
        time_to_first_message_ms=ttft,
        time_to_first_thinking_ms=None,
        time_to_first_text_ms=ttft,
        total_ms=total,
        message_count=1,
        first_message_type="text_stream",
    )
    print(f"  First text token: {_fmt(ttft)}")
    print(f"  Total:            {total}ms")
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=" * 70)
    print("  Claude Agent SDK Raw Latency Benchmark")
    print("  No DB, No Redis, No MCP Tools Infrastructure")
    print("=" * 70)

    model = _get_model()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("\nERROR: ANTHROPIC_API_KEY environment variable is required.")
        print("Set it in backend/.env or export it directly.")
        sys.exit(1)

    print(f"\nModel:    {model}")
    print(f"Base URL: {os.getenv('ANTHROPIC_BASE_URL', 'default')}")
    print(f"Prompt:   {USER_PROMPT}")

    all_results: dict = {}

    # --- Test 0: Direct API baseline ---
    try:
        api_result = await benchmark_direct_api()
        if api_result is not None:
            all_results["T0: Direct API (no SDK)"] = [api_result]
    except Exception as e:
        print(f"\n  TEST 0 FAILED: {e}")

    # --- Test A: Minimal SDK ---
    try:
        results_a = await run_benchmark(
            test_label="TEST A: Minimal SDK (no tools, minimal prompt)",
            system_prompt=MINIMAL_SYSTEM_PROMPT,
            tool_count=0,
            enable_thinking=False,
        )
        all_results["TA: Minimal SDK"] = results_a
    except Exception as e:
        print(f"\n  TEST A FAILED: {e}")
        import traceback
        traceback.print_exc()

    # --- Test B: With 30 dummy MCP tools ---
    try:
        results_b = await run_benchmark(
            test_label="TEST B: With 30 dummy MCP tools",
            system_prompt=MINIMAL_SYSTEM_PROMPT,
            tool_count=30,
            enable_thinking=False,
        )
        all_results["TB: 30 MCP tools"] = results_b
    except Exception as e:
        print(f"\n  TEST B FAILED: {e}")
        import traceback
        traceback.print_exc()

    # --- Test C: Large system prompt ---
    try:
        results_c = await run_benchmark(
            test_label="TEST C: Large system prompt (~6000 tokens)",
            system_prompt=LARGE_SYSTEM_PROMPT,
            tool_count=0,
            enable_thinking=False,
        )
        all_results["TC: Large prompt"] = results_c
    except Exception as e:
        print(f"\n  TEST C FAILED: {e}")
        import traceback
        traceback.print_exc()

    # --- Test D: Full production simulation (large prompt + 30 tools) ---
    try:
        results_d = await run_benchmark(
            test_label="TEST D: Production simulation (large prompt + 30 tools)",
            system_prompt=LARGE_SYSTEM_PROMPT,
            tool_count=30,
            enable_thinking=False,
        )
        all_results["TD: Full production sim"] = results_d
    except Exception as e:
        print(f"\n  TEST D FAILED: {e}")
        import traceback
        traceback.print_exc()

    # --- Test E: With thinking enabled (if production uses it) ---
    thinking_enabled = os.getenv("CLAUDE_AGENT_THINKING_ENABLED", "false").lower() in (
        "true", "1", "yes",
    )
    if thinking_enabled:
        try:
            results_e = await run_benchmark(
                test_label="TEST E: With extended thinking enabled",
                system_prompt=MINIMAL_SYSTEM_PROMPT,
                tool_count=0,
                enable_thinking=True,
            )
            all_results["TE: Thinking enabled"] = results_e
        except Exception as e:
            print(f"\n  TEST E FAILED: {e}")
            import traceback
            traceback.print_exc()

    # --- Print comparison ---
    if all_results:
        print_comparison_table(all_results)
    else:
        print("\nNo tests completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
