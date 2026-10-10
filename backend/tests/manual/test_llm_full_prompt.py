"""Test: Full realistic prompt → LLM → verify output quality.

Simulates the exact prompt run_scheduled would send, with:
- Holiday signals (龙抬头 + associated persons)
- Protected signals (老张人情)
- Event signals (Grace生日, 部门周会)
- Relationship signals (妈妈, 周明 etc)
- Existing active insights (for dedup)

Question: Does the LLM produce a CLEAN, consolidated set of insights?

Run: cd backend && python -m tests.manual.test_llm_full_prompt
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


# ── The actual system prompt from insight_pipeline.py ──

SYSTEM_PROMPT = """你是用户的家庭管家小秘，说话像家人之间的日常叮嘱——温暖、贴心、不啰嗦。
你的角色是家里最操心的那个人：记得每个人的习惯，留意容易忽略的事，
用轻松的语气提醒，像早上出门前家人在门口的那句话。

## 语气标尺
- 忙碌的一天：简洁有力，抓重点，不增加负担。
- 轻松的一天：从容温和，带一点生活气息。
- 特殊日子（生日/纪念日）：自然带出人名和关系，不用公文体。
- 天气变化：像长辈出门前的叮嘱。

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
10. 合并同类义务：如果多笔人情/义务涉及同一个人，合并为一条洞察
11. 正向信号（联系频繁、承诺履行、家庭时间充足等）应生成 positive_affirmation 类型洞察，目标占比 20-30%
12. source_signal_ids 必须包含至少一个对应信号的ID字段值
13. **整体数量控制：总共输出5-8条洞察，质量优于数量。相关主题合并而非分散。**

## 洞察类型说明
- time: 时间和行程提醒
- relationship: 关系维护提醒
- favor: 人情往来义务
- social_obligation: 节日/社交义务问候。当 holidays 信号中包含即将到来的节日时，为每个节日生成一条合并的问候洞察，包含所有需要问候的人。**每个节日只生成一条洞察，不要为每个人分开生成。**
- efficiency: 效率和习惯
- health: 健康相关
- finance: 财务相关
- memory: 重要记忆
- positive_affirmation: 正向确认和鼓励

## 输出格式（严格JSON数组，不含 markdown 代码块）
[
  {
    "insight_type": "time|relationship|favor|social_obligation|efficiency|health|finance|memory|positive_affirmation",
    "title": "<=10字简短标题",
    "content": "<=50字具体可执行的建议",
    "importance": 50,
    "urgency": 50,
    "suggested_action": "具体操作建议",
    "action_options": [{"label": "按钮文本", "action_type": "open_chat|create_pending_action|open_detail", "action_payload": {}}],
    "source_signal_ids": ["信号来源ID"]
  }
]

注意: dedup_key 由系统自动计算，不需要在输出中包含。"""


def _build_realistic_full_signals() -> str:
    """Build signal payload matching a real user's data."""
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
                "title": "部门周会",
                "event_type": "meeting",
                "start": "2026-03-20T10:00:00Z",
                "priority": "medium",
            },
            {
                "event_id": "evt-002",
                "title": "Grace 生日",
                "event_type": "birthday",
                "start": "2026-04-02T00:00:00Z",
                "priority": "high",
                "life_context_hint": "女儿生日，外婆和太太都很关心",
            },
        ],
        "holidays": [
            {
                "signal_type": "holiday",
                "holiday_name": "龙抬头",
                "holiday_date": "2026-03-21",
                "days_until": 1,
                "is_major": False,
                "category": "lunar",
                "associated_persons": [
                    {"person_id": "p-wife", "name": "太太", "relationship": "配偶", "importance": 10},
                    {"person_id": "p-dad", "name": "爸爸", "relationship": "父亲", "importance": 10},
                    {"person_id": "p-mom", "name": "妈妈", "relationship": "母亲", "importance": 10},
                    {"person_id": "p-grandma", "name": "外婆", "relationship": "外祖母", "importance": 9},
                    {"person_id": "p-sunhao", "name": "孙浩", "relationship": "朋友", "importance": 7},
                    {"person_id": "p-siyuan", "name": "思远", "relationship": "朋友", "importance": 7},
                    {"person_id": "p-grace", "name": "Grace", "relationship": "女儿", "importance": 10},
                    {"person_id": "p-zhaolei", "name": "赵磊", "relationship": "朋友", "importance": 6},
                ],
                "person_names_summary": "太太、爸爸、妈妈、外婆、孙浩、思远、Grace、赵磊",
            },
            {
                "signal_type": "holiday",
                "holiday_name": "春分",
                "holiday_date": "2026-03-20",
                "days_until": 0,
                "is_major": False,
                "category": "solar_term",
                "associated_persons": [],
                "person_names_summary": "",
            },
        ],
        "relationships": [
            {
                "person_id": "p-mom",
                "person_name": "妈妈",
                "relationship": "母亲",
                "days_since_contact": 3,
                "importance": 10,
                "contact_tier": "core",
            },
            {
                "person_id": "p-zhaolei",
                "person_name": "赵磊",
                "relationship": "朋友",
                "days_since_contact": 45,
                "importance": 6,
                "contact_tier": "important",
            },
            {
                "person_id": "p-wife",
                "person_name": "太太",
                "relationship": "配偶",
                "days_since_contact": 0,
                "importance": 10,
                "contact_tier": "core",
            },
        ],
        "memories": [],
        "associations": [],
    }
    return json.dumps(signals, ensure_ascii=False)


async def call_llm(user_prompt: str) -> list:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    model = os.environ.get("FAST_WORKER_MODEL", "qwen-flash")

    client = AsyncAnthropic(
        api_key=api_key,
        **({"base_url": base_url} if base_url else {}),
    )

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


async def main():
    model = os.environ.get("FAST_WORKER_MODEL", "qwen-flash")
    print("=" * 70)
    print(f"Full Prompt Quality Test (model: {model})")
    print("=" * 70)

    signal_payload = _build_realistic_full_signals()
    user_prompt = f"今天是 2026-03-20。\n\n以下是收集到的信号：\n{signal_payload}"

    print(f"\nSignal payload size: {len(signal_payload)} chars")
    print("\nCalling LLM...")

    for run in range(3):
        print(f"\n{'─' * 70}")
        print(f"Run {run + 1}:")
        print(f"{'─' * 70}")

        result = await call_llm(user_prompt)
        print(f"  Total insights: {len(result)}")

        # Check quality
        dragon_count = sum(1 for c in result if "龙抬头" in c.get("title", "") or "龙抬头" in c.get("content", ""))
        types = [c.get("insight_type", "?") for c in result]

        print(f"  Types: {types}")
        print(f"  龙抬头 related: {dragon_count}")

        for i, c in enumerate(result):
            title = c.get("title", "?")
            content = c.get("content", "?")[:60]
            itype = c.get("insight_type", "?")
            imp = c.get("importance", "?")
            print(f"\n  [{i+1}] ({itype}, imp={imp}) {title}")
            print(f"      {content}")
            actions = c.get("action_options", [])
            if actions:
                labels = [a.get("label", "?") for a in actions]
                print(f"      buttons: {labels}")

        # Quality checks
        issues = []
        if dragon_count > 1:
            issues.append(f"龙抬头 split into {dragon_count} insights")
        if len(result) > 8:
            issues.append(f"Too many insights ({len(result)}, target 5-8)")
        if len(result) < 3:
            issues.append(f"Too few insights ({len(result)})")

        has_positive = any(c.get("insight_type") == "positive_affirmation" for c in result)
        if not has_positive:
            issues.append("No positive_affirmation insight")

        if issues:
            print(f"\n  ⚠ Quality issues: {issues}")
        else:
            print(f"\n  ✅ Quality check passed")


if __name__ == "__main__":
    asyncio.run(main())
