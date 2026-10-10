"""Test with REAL database data and the ACTUAL code path.

Connects to the real DB, runs the actual signal collector, builds the
exact prompt that _generate_batch would send, and calls the LLM.

Run: cd backend && python -m tests.manual.test_llm_real_data
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


async def main():
    from datetime import date
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

    from src.config.settings import settings

    # Import all models to initialize mappers (required for standalone scripts)
    # The app's startup normally does this; standalone scripts need explicit imports
    import src.modules.curation.models  # noqa: F401
    import src.modules.trip.models  # noqa: F401
    import src.modules.trip.models.trip_plan  # noqa: F401
    import src.modules.conversation.models  # noqa: F401
    import src.modules.member.models  # noqa: F401
    import src.modules.insight.models  # noqa: F401
    import src.modules.memory.models  # noqa: F401
    import src.modules.relationship.models  # noqa: F401

    from src.modules.insight.insight_signal_collector import InsightSignalCollector
    from src.modules.insight.insight_pipeline import _BATCH_SYSTEM_PROMPT, InsightPipeline
    from src.modules.insight.insight_dedup_aware import (
        fetch_active_insights,
        build_dedup_aware_prompt_section,
    )
    from src.modules.insight.insight_llm_client import call_llm_and_parse
    from src.modules.insight.life_stage_detector import detect_life_stage, LifeStage
    from src.core.utils.timezone import local_today

    # ── Step 1: Connect to real DB ──
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args=settings.database_connect_args,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )

    async with session_factory() as db:
        # ── Step 2: Find a real user ──
        from src.modules.member.models.user import User

        # Pick the user that has person profiles (family with actual data)
        from sqlalchemy import func as sqla_func
        from src.modules.member.models.person_profile import PersonProfile
        rich_family = await db.execute(
            select(PersonProfile.family_id, sqla_func.count(PersonProfile.id))
            .group_by(PersonProfile.family_id)
            .order_by(sqla_func.count(PersonProfile.id).desc())
            .limit(1)
        )
        rich_row = rich_family.first()
        if rich_row:
            target_family_id = rich_row[0]
            result = await db.execute(
                select(User.id, User.family_id).where(User.family_id == target_family_id).limit(1)
            )
        else:
            result = await db.execute(
                select(User.id, User.family_id).limit(1)
            )
        row = result.first()
        if not row:
            print("ERROR: No users found in database")
            return

        user_id, family_id = row.id, row.family_id
        print("=" * 70)
        print(f"Real Data Test")
        print(f"  User ID:   {user_id}")
        print(f"  Family ID: {family_id}")
        print(f"  Model:     {os.environ.get('FAST_WORKER_MODEL', 'qwen-flash')}")
        print("=" * 70)

        # ── Step 3: Collect real signals (exactly as run_scheduled does) ──
        target_date = local_today()
        print(f"\n  Target date: {target_date}")

        collector = InsightSignalCollector(db)
        signals = await collector.collect_all(user_id, family_id, target_date)

        print(f"\n  Signals collected:")
        print(f"    protected:     {len(signals.protected)}")
        print(f"    events:        {len(signals.events)}")
        print(f"    holidays:      {len(signals.holidays)}")
        print(f"    relationships: {len(signals.relationships)}")
        print(f"    memories:      {len(signals.memories)}")
        print(f"    associations:  {len(signals.associations)}")
        print(f"    graph:         {len(signals.graph)}")
        print(f"    preferences:   {len(signals.preferences)}")
        print(f"    TOTAL:         {signals.total_count()}")

        if signals.total_count() == 0:
            print("\n  WARNING: No signals collected. Prompt will be empty.")

        # ── Step 4: Compress signals (exactly as pipeline does) ──
        pipeline = InsightPipeline(db)
        prefs = await pipeline._load_preferences(user_id, family_id)
        budget = pipeline._build_budget(prefs)
        compressed = pipeline._compress_signals(signals, budget)

        print(f"\n  Compressed signals:")
        print(f"    protected:     {len(compressed.protected)}")
        print(f"    events:        {len(compressed.events)}")
        print(f"    holidays:      {len(compressed.holidays)}")
        print(f"    relationships: {len(compressed.relationships)}")
        print(f"    memories:      {len(compressed.memories)}")
        print(f"    associations:  {len(compressed.associations)}")

        # ── Step 5: Build exact prompt (same as _generate_batch) ──
        signal_payload = json.dumps(
            {
                "protected": compressed.protected,
                "events": compressed.events,
                "holidays": compressed.holidays,
                "relationships": compressed.relationships,
                "memories": compressed.memories,
                "associations": compressed.associations,
            },
            ensure_ascii=False,
        )

        today_str = local_today().isoformat()

        # Life stage
        life_stage_hint = ""
        try:
            life_stage_ctx = await detect_life_stage(db, family_id)
            if life_stage_ctx.stage != LifeStage.UNKNOWN:
                adjustments = life_stage_ctx.strategy_adjustments
                description = adjustments.get("description", "")
                focus = ", ".join(adjustments.get("focus_areas", []))
                life_stage_hint = (
                    f"\n\n## 家庭阶段上下文\n"
                    f"当前阶段: {description}\n"
                    f"重点关注: {focus}\n"
                    f"子女数量: {life_stage_ctx.child_count}"
                )
                if life_stage_ctx.youngest_child_age is not None:
                    life_stage_hint += f", 最小孩子年龄: {life_stage_ctx.youngest_child_age}岁"
                life_stage_hint += "\n请根据家庭阶段调整洞察的侧重点和语气。"
        except Exception as e:
            print(f"  Life stage detection failed: {e}")

        # Dedup section
        dedup_section = ""
        try:
            active_rows = await fetch_active_insights(db, user_id)
            dedup_section = build_dedup_aware_prompt_section(active_rows)
            print(f"\n  Active insights for dedup: {len(active_rows)}")
        except Exception as e:
            print(f"  Dedup fetch failed: {e}")

        user_prompt = (
            f"今天是 {today_str}。{life_stage_hint}"
            f"\n\n以下是收集到的信号：\n{signal_payload}"
            f"{dedup_section}"
        )

        print(f"\n  Prompt sizes:")
        print(f"    System prompt: {len(_BATCH_SYSTEM_PROMPT)} chars")
        print(f"    User prompt:   {len(user_prompt)} chars")
        print(f"    Signal payload: {len(signal_payload)} chars")

        # ── Step 6: Print the actual prompts ──
        print(f"\n{'─' * 70}")
        print("SYSTEM PROMPT (first 500 chars):")
        print(f"{'─' * 70}")
        print(_BATCH_SYSTEM_PROMPT[:500])
        print("...")

        print(f"\n{'─' * 70}")
        print("USER PROMPT:")
        print(f"{'─' * 70}")
        print(user_prompt[:3000])
        if len(user_prompt) > 3000:
            print(f"... ({len(user_prompt) - 3000} more chars)")

        # ── Step 6.5: Dump full prompts to file ──
        dump_path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".gstack", "qa-reports",
        )
        os.makedirs(dump_path, exist_ok=True)
        prompt_dump = os.path.join(dump_path, "real-prompt-dump.txt")
        with open(prompt_dump, "w") as f:
            f.write("=" * 70 + "\n")
            f.write("SYSTEM PROMPT\n")
            f.write("=" * 70 + "\n")
            f.write(_BATCH_SYSTEM_PROMPT)
            f.write("\n\n")
            f.write("=" * 70 + "\n")
            f.write("USER PROMPT\n")
            f.write("=" * 70 + "\n")
            f.write(user_prompt)
        print(f"\n  Full prompts dumped to: {prompt_dump}")

        # ── Step 7: Call LLM ──
        print(f"\n{'─' * 70}")
        print("LLM RESPONSE:")
        print(f"{'─' * 70}")

        candidates = await call_llm_and_parse(
            system_prompt=_BATCH_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_attempts=2,
        )

        print(f"\n  Total candidates: {len(candidates)}")
        for i, c in enumerate(candidates):
            disp = c.disposition or "NEW"
            eid = c.existing_id or "-"
            print(f"\n  [{i+1}] ({c.insight_type}, imp={c.importance}, urg={c.urgency}) {disp}")
            print(f"      title:   {c.title}")
            print(f"      content: {c.content[:80]}")
            if c.suggested_action:
                print(f"      action:  {c.suggested_action[:60]}")
            if c.action_options:
                labels = [a.get("label", "?") if isinstance(a, dict) else "?" for a in c.action_options]
                print(f"      buttons: {labels}")
            if eid != "-":
                print(f"      existing_id: {eid}")

        # ── Quality summary ──
        print(f"\n{'─' * 70}")
        print("QUALITY SUMMARY:")
        print(f"{'─' * 70}")

        types = [c.insight_type for c in candidates]
        type_counts = {}
        for t in types:
            type_counts[t] = type_counts.get(t, 0) + 1
        print(f"  Type distribution: {type_counts}")

        # Check for duplicates
        titles = [c.title for c in candidates]
        dup_titles = [t for t in set(titles) if titles.count(t) > 1]
        if dup_titles:
            print(f"  ⚠ Duplicate titles: {dup_titles}")
        else:
            print(f"  ✅ No duplicate titles")

        # Check for positive affirmation
        has_positive = any(c.insight_type == "positive_affirmation" for c in candidates)
        print(f"  Positive affirmation: {'✅ yes' if has_positive else '⚠ missing'}")

        # Check count
        if 3 <= len(candidates) <= 10:
            print(f"  Count: ✅ {len(candidates)} (reasonable)")
        else:
            print(f"  Count: ⚠ {len(candidates)} (expected 3-10)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
