"""Live LLM test: Can the LLM handle seasonal greetings without per-person duplicates?

Core question: If holiday signals are included in the batch prompt, does the LLM
generate ONE merged greeting or N per-person duplicates?

Currently, holiday signals are NOT in the signal collector — they only exist in
rule_engine_insights._seasonal_obligations(). This test verifies whether moving
holiday logic to the LLM path would work.

Test plan:
1. Build a realistic scheduled prompt WITH holiday+member signals
2. Call the real LLM (qwen-flash via DashScope) 5 times
3. Count how many times it produces 1 merged insight vs N duplicates
4. Also test the ACTUAL current prompt (no holiday signals) to show the gap

Run: cd backend && python -m tests.manual.test_llm_dedup_live
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


# The actual system prompt from insight_pipeline.py
SYSTEM_PROMPT = """你是用户的家庭管家小秘，说话像家人之间的日常叮嘱——温暖、贴心、不啰嗦。
你的角色是家里最操心的那个人：记得每个人的习惯，留意容易忽略的事，
用轻松的语气提醒，像早上出门前家人在门口的那句话。

## 语气标尺
- 忙碌的一天：简洁有力，抓重点，不增加负担。
- 轻松的一天：从容温和，带一点生活气息。
- 特殊日子（生日/纪念日）：自然带出人名和关系，不用公文体。

你的任务是根据以下信号为用户生成洞察提醒。

## 规则
1. 每条洞察必须基于至少一条信号，不要编造
2. 优先处理 protected 信号（社交义务、承诺），这些不可忽略
3. 语气温暖自然，像家人叮嘱
4. 用"记得"、"别忘了"、"注意"而非"建议"、"请注意"
5. 每条洞察简洁，标题10字以内，内容50字以内
6. 合理设置 importance (0-100): >=80 重要, 50-79 一般, <50 低优先
7. 合理设置 urgency (0-100): >=80 紧急, 50-79 一般, <50 低优先
8. suggested_action: 具体可操作的建议步骤
9. action_options: 可选操作按钮列表（如适用）
10. 合并同类义务：如果多笔人情/义务涉及同一个人，合并为一条洞察（例如不要既生成"A大额人情"又生成"A和B人情待还"，应该只保留合并版本）
11. 正向信号（联系频繁、承诺履行、家庭时间充足等）应生成 positive_affirmation 类型洞察，目标占比 20-30%
12. source_signal_ids 必须包含至少一个对应信号的ID字段值（如 event_id、favor_record_id、commitment_id 等）

## 洞察类型说明
- time: 时间和行程提醒
- relationship: 关系维护提醒
- favor: 人情往来义务
- efficiency: 效率和习惯
- health: 健康相关
- finance: 财务相关
- memory: 重要记忆
- social_obligation: 节日/社交义务问候
- positive_affirmation: 正向确认和鼓励

## 输出格式（严格JSON数组，不含 markdown 代码块）
[
  {
    "insight_type": "time|relationship|favor|efficiency|health|finance|memory|social_obligation|positive_affirmation",
    "title": "<=10字简短标题",
    "content": "<=50字具体可执行的建议",
    "importance": 50,
    "urgency": 50,
    "suggested_action": "具体操作建议",
    "action_options": [{"label": "按钮文本", "action_type": "open_chat|create_pending_action|open_detail", "action_payload": {}}],
    "source_signal_ids": ["信号来源ID"]
  }
]

注意: dedup_key 由系统自动计算，不需要在输出中包含。

## 重要：节日问候合并规则
同一个节日的问候必须合并为一条洞察，包含所有需要问候的人。
不要为每个人分别生成独立的节日问候洞察。"""


def _build_realistic_signals_with_holidays() -> str:
    """Build signal payload that mimics what signal collector + holiday data would produce."""
    signals = {
        "protected": [
            {
                "signal_type": "favor",
                "favor_record_id": "fav-001",
                "direction": "owed_by_user",
                "counterpart_name": "老张",
                "counterpart_id": "person-zhang",
                "description": "老张帮忙搬家，人情未还",
                "amount_estimate": 2000,
                "occurred_at": "2025-12-15",
            },
        ],
        "events": [
            {
                "event_id": "evt-001",
                "title": "龙抬头 (二月二)",
                "event_type": "holiday",
                "start": "2026-03-21T00:00:00Z",
                "priority": "high",
                "life_context_hint": "传统节日，适合向亲友问候",
                "associated_persons": [
                    {"person_id": "person-zhouming", "name": "周明", "relationship": "朋友"},
                    {"person_id": "person-qiangge", "name": "强哥", "relationship": "朋友"},
                    {"person_id": "person-wife", "name": "用户太太", "relationship": "配偶"},
                ],
            },
            {
                "event_id": "evt-002",
                "title": "部门周会",
                "event_type": "meeting",
                "start": "2026-03-20T10:00:00Z",
                "priority": "medium",
            },
        ],
        "relationships": [
            {
                "person_id": "person-mom",
                "person_name": "妈妈",
                "relationship": "母亲",
                "days_since_contact": 2,
                "importance": 10,
                "contact_tier": "core",
            },
            {
                "person_id": "person-zhouming",
                "person_name": "周明",
                "relationship": "朋友",
                "days_since_contact": 30,
                "importance": 7,
                "contact_tier": "important",
            },
        ],
        "memories": [],
        "associations": [],
    }
    return json.dumps(signals, ensure_ascii=False)


def _build_actual_current_signals() -> str:
    """Build signal payload as it ACTUALLY is today (no holiday signals)."""
    signals = {
        "protected": [
            {
                "signal_type": "favor",
                "favor_record_id": "fav-001",
                "direction": "owed_by_user",
                "counterpart_name": "老张",
                "counterpart_id": "person-zhang",
                "description": "老张帮忙搬家，人情未还",
                "amount_estimate": 2000,
                "occurred_at": "2025-12-15",
            },
        ],
        "events": [
            {
                "event_id": "evt-002",
                "title": "部门周会",
                "event_type": "meeting",
                "start": "2026-03-20T10:00:00Z",
                "priority": "medium",
            },
        ],
        "relationships": [
            {
                "person_id": "person-mom",
                "person_name": "妈妈",
                "relationship": "母亲",
                "days_since_contact": 2,
                "importance": 10,
                "contact_tier": "core",
            },
            {
                "person_id": "person-zhouming",
                "person_name": "周明",
                "relationship": "朋友",
                "days_since_contact": 30,
                "importance": 7,
                "contact_tier": "important",
            },
        ],
        "memories": [],
        "associations": [],
    }
    return json.dumps(signals, ensure_ascii=False)


async def call_llm(user_prompt: str) -> list:
    """Call real LLM and parse JSON response."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    model = os.environ.get("FAST_WORKER_MODEL", "qwen-flash")

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = AsyncAnthropic(**client_kwargs)

    response = await client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    return json.loads(raw)


def _count_dragon_head_insights(candidates: list) -> dict:
    """Count how many dragon-head related insights were generated."""
    dragon_insights = [
        c for c in candidates
        if "龙抬头" in c.get("title", "") or "龙抬头" in c.get("content", "")
    ]
    return {
        "total": len(candidates),
        "dragon_head_count": len(dragon_insights),
        "is_merged": len(dragon_insights) <= 1,
        "dragon_insights": dragon_insights,
    }


async def main():
    model = os.environ.get("FAST_WORKER_MODEL", "qwen-flash")
    print("=" * 70)
    print(f"LLM Seasonal Greeting Test (model: {model})")
    print("=" * 70)

    # ── Test 1: WITH holiday signals in prompt (proposed approach) ──
    print("\n" + "─" * 70)
    print("Test 1: WITH holiday signals (5 runs)")
    print("  Question: Can LLM generate 1 merged '龙抬头问候' for all persons?")
    print("─" * 70)

    signal_payload = _build_realistic_signals_with_holidays()
    user_prompt = f"今天是 2026-03-19。\n\n以下是收集到的信号：\n{signal_payload}"

    merged_count = 0
    total_runs = 5

    for i in range(total_runs):
        try:
            result = await call_llm(user_prompt)
            analysis = _count_dragon_head_insights(result)

            status = "✅ MERGED" if analysis["is_merged"] else f"❌ SPLIT ({analysis['dragon_head_count']})"
            if analysis["is_merged"]:
                merged_count += 1

            print(f"\n  Run {i+1}: {status} (total insights: {analysis['total']})")
            for di in analysis["dragon_insights"]:
                print(f"    → title: {di.get('title', '?')}")
                content = di.get('content', '?')
                print(f"      content: {content[:60]}")
                persons_in_content = []
                for name in ["周明", "强哥", "太太", "用户太太"]:
                    if name in content or name in di.get("title", ""):
                        persons_in_content.append(name)
                if persons_in_content:
                    print(f"      persons mentioned: {', '.join(persons_in_content)}")

        except Exception as e:
            print(f"\n  Run {i+1}: ERROR - {e}")

    pct = (merged_count / total_runs) * 100
    print(f"\n  Result: {merged_count}/{total_runs} merged ({pct:.0f}%)")
    print(f"  {'✅ PASS' if pct >= 80 else '❌ FAIL'} (target: >=80%)")

    # ── Test 2: WITHOUT holiday signals (current actual behavior) ──
    print("\n" + "─" * 70)
    print("Test 2: WITHOUT holiday signals (current prompt, 1 run)")
    print("  Shows: LLM has NO holiday context → cannot generate greetings at all")
    print("─" * 70)

    signal_payload_current = _build_actual_current_signals()
    user_prompt_current = f"今天是 2026-03-19。\n\n以下是收集到的信号：\n{signal_payload_current}"

    try:
        result_current = await call_llm(user_prompt_current)
        analysis_current = _count_dragon_head_insights(result_current)

        print(f"\n  Total insights: {analysis_current['total']}")
        print(f"  Dragon head insights: {analysis_current['dragon_head_count']}")
        if analysis_current["dragon_head_count"] == 0:
            print("  → LLM correctly has NO holiday context, so NO 龙抬头 insights")
            print("  → This is why rule_engine_insights exists: it fetches holidays separately")
        else:
            print("  → UNEXPECTED: LLM generated 龙抬头 insights without holiday signals!")

        print("\n  All insights generated:")
        for c in result_current:
            print(f"    → [{c.get('insight_type', '?')}] {c.get('title', '?')}")

    except Exception as e:
        print(f"  ERROR: {e}")

    # ── Summary ──
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print(f"  WITH holiday signals:    {merged_count}/{total_runs} merged ({pct:.0f}%)")
    print(f"  WITHOUT holiday signals: LLM cannot generate greetings (no data)")
    print()
    if pct >= 80:
        print("  → LLM CAN handle merged greetings if given holiday signals")
        print("  → Option A: Add holiday signal collector → let LLM handle it (99% LLM)")
        print("  → Option B: Keep rule engine but merge per-holiday (current fix)")
    else:
        print("  → LLM struggles with merging → rule engine is necessary")


if __name__ == "__main__":
    asyncio.run(main())
