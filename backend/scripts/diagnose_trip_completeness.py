"""Diagnostic script: check trip completeness logic against real data.

Usage:
    cd backend && python -m scripts.diagnose_trip_completeness
"""
import asyncio
import json
import sys
from pathlib import Path

# Ensure backend/src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from src.db.session import AsyncSessionLocal
from src.modules.curation.models import CuratedEvent, PreparationItem
from src.modules.trip.models.trip_plan import TripPlan
from src.modules.trip.models.trip_itinerary import TripItinerary
from src.modules.curation.services.trip_completeness_service import (
    TripCompletenessService,
    TripCompletenessCheck,
    _compute_input_hash,
    _serialize_trip,
    _serialize_event,
    _serialize_itinerary,
    _build_user_prompt,
)


SEPARATOR = "=" * 70


async def diagnose():
    async with AsyncSessionLocal() as db:
        # ── 1. Find trip(s) matching 东部华侨城 ──
        print(f"\n{SEPARATOR}")
        print("STEP 1: 查找行程 (trips)")
        print(SEPARATOR)

        trip_stmt = (
            select(TripPlan)
            .options(selectinload(TripPlan.itineraries))
            .where(TripPlan.is_active.is_(True))
            .order_by(TripPlan.created_at.desc())
            .limit(10)
        )
        trips = list((await db.execute(trip_stmt)).scalars().all())
        print(f"找到 {len(trips)} 个活跃行程:")
        target_trip = None
        for t in trips:
            marker = ""
            if "华侨城" in (t.trip_name or "") or "华侨城" in (t.destination or ""):
                marker = " ★ TARGET"
                target_trip = t
            print(
                f"  - {t.trip_name} | {t.destination} | "
                f"{t.start_date}~{t.end_date} | status={t.status} | "
                f"itineraries={len(t.itineraries)}{marker}"
            )

        if target_trip is None:
            print("\n未找到华侨城相关行程，使用第一个行程作为诊断目标")
            if not trips:
                print("ERROR: 数据库中没有任何活跃行程")
                return
            target_trip = trips[0]

        trip = target_trip
        trip_id = trip.trip_id
        family_id = trip.family_id
        print(f"\n诊断目标: {trip.trip_name} (trip_id={trip_id})")

        # ── 2. Show itinerary schedule data ──
        print(f"\n{SEPARATOR}")
        print("STEP 2: 行程日程 (trip_itineraries.schedule)")
        print(SEPARATOR)

        if trip.itineraries:
            for itin in sorted(trip.itineraries, key=lambda i: i.day_number):
                print(f"\n  Day {itin.day_number}:")
                schedule = itin.schedule or []
                for item in schedule:
                    title = item.get("title", "?")
                    atype = item.get("activity_type", "?")
                    time = item.get("time", "?")
                    print(f"    [{time}] {title} (type={atype})")
        else:
            print("  (无行程日程数据)")

        # ── 3. Show CuratedEvents linked to this trip ──
        print(f"\n{SEPARATOR}")
        print("STEP 3: 关联的策展事件 (curated_events where trip_id=...)")
        print(SEPARATOR)

        ev_stmt = (
            select(CuratedEvent)
            .where(
                CuratedEvent.trip_id == trip_id,
                CuratedEvent.family_id == family_id,
                CuratedEvent.is_active.is_(True),
                CuratedEvent.status != "cancelled",
            )
            .order_by(CuratedEvent.normalized_start)
        )
        events = list((await db.execute(ev_stmt)).scalars().all())
        print(f"找到 {len(events)} 个策展事件:")
        for ev in events:
            print(
                f"  - [{ev.event_type}] {ev.title} | "
                f"location={ev.location} | status={ev.status}"
            )
            if ev.notes:
                print(f"    notes: {ev.notes[:100]}")
            if ev.secretary_note:
                print(f"    secretary_note: {ev.secretary_note[:100]}")
            enrichments = ev.enrichments or {}
            transport = enrichments.get("transportation") or enrichments.get("transport_mode")
            if transport:
                print(f"    transportation: {transport}")

        # ── 4. Show existing PreparationItems ──
        print(f"\n{SEPARATOR}")
        print("STEP 4: 现有的准备清单条目 (preparation_items)")
        print(SEPARATOR)

        if events:
            event_ids = [ev.id for ev in events]
            prep_stmt = (
                select(PreparationItem)
                .where(PreparationItem.event_id.in_(event_ids))
                .order_by(PreparationItem.created_at)
            )
            preps = list((await db.execute(prep_stmt)).scalars().all())
            print(f"找到 {len(preps)} 个准备条目:")
            for p in preps:
                done_mark = "✓" if p.done else "○"
                print(f"  {done_mark} [{p.source}] {p.text}")
                print(f"    id={p.id}, event_id={p.event_id}")
        else:
            print("  (无关联事件，无法查询准备条目)")

        # ── 5. Show cached completeness check results ──
        print(f"\n{SEPARATOR}")
        print("STEP 5: 缓存的完整性检查结果 (trip_completeness_checks)")
        print(SEPARATOR)

        cache_stmt = (
            select(TripCompletenessCheck)
            .where(TripCompletenessCheck.trip_id == trip_id)
            .order_by(TripCompletenessCheck.checked_at.desc())
        )
        caches = list((await db.execute(cache_stmt)).scalars().all())
        print(f"找到 {len(caches)} 条缓存记录:")
        for c in caches:
            print(f"  - hash={c.input_hash} | checked_at={c.checked_at}")
            print(f"    result={json.dumps(c.result, ensure_ascii=False, indent=2)}")

        # ── 6. Compute new hash (with itinerary data) vs old hash ──
        print(f"\n{SEPARATOR}")
        print("STEP 6: Hash 对比 (旧 vs 新)")
        print(SEPARATOR)

        itin_stmt = (
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .order_by(TripItinerary.day_number)
        )
        itineraries = list((await db.execute(itin_stmt)).scalars().all())

        old_hash = _compute_input_hash(trip, events)
        new_hash = _compute_input_hash(trip, events, itineraries if itineraries else None)

        print(f"  旧 Hash (无 itinerary): {old_hash}")
        print(f"  新 Hash (含 itinerary): {new_hash}")
        print(f"  Hash 变化: {'是 ✓ (缓存将失效)' if old_hash != new_hash else '否 ✗ (缓存不失效！)'}")

        cache_match = any(c.input_hash == new_hash for c in caches)
        print(f"  新 Hash 是否命中缓存: {'是 (将返回缓存结果)' if cache_match else '否 (将触发新 LLM 调用)'}")

        # ── 7. Show what LLM would receive ──
        print(f"\n{SEPARATOR}")
        print("STEP 7: LLM 将收到的 Prompt (序列化数据)")
        print(SEPARATOR)

        trip_json = _serialize_trip(trip)
        events_json = [_serialize_event(e) for e in events]
        itineraries_json = [_serialize_itinerary(i) for i in itineraries] if itineraries else None

        print("\n行程信息:")
        print(json.dumps(trip_json, ensure_ascii=False, indent=2))

        print("\n策展事件:")
        print(json.dumps(events_json, ensure_ascii=False, indent=2))

        if itineraries_json:
            print("\n每日行程安排 (新增):")
            print(json.dumps(itineraries_json, ensure_ascii=False, indent=2))
        else:
            print("\n每日行程安排: (无数据)")

        # ── 8. Actually run the completeness check ──
        print(f"\n{SEPARATOR}")
        print("STEP 8: 执行完整性检查 (调用 LLM)")
        print(SEPARATOR)

        try:
            from anthropic import AsyncAnthropic
            from src.config.settings import settings

            client = AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url or None,
            )

            svc = TripCompletenessService(db, llm_provider=client)
            result = await svc.check_completeness(trip_id, family_id)

            if result is None:
                print("  结果: None (LLM 不可用或无事件)")
            else:
                print(f"  has_departure: {result.has_departure}")
                print(f"  has_return: {result.has_return}")
                print(f"  return_type: {result.return_type}")
                print(f"  has_accommodation: {result.has_accommodation}")
                print(f"  accommodation_type: {result.accommodation_type}")
                print(f"  gaps: {result.gaps}")
                print(f"  input_hash: {result.input_hash}")

            await db.commit()

        except Exception as exc:
            print(f"  LLM 调用失败: {exc}")
            import traceback
            traceback.print_exc()

        # ── 9. Check PreparationItems AFTER the check ──
        print(f"\n{SEPARATOR}")
        print("STEP 9: 检查后的准备清单条目")
        print(SEPARATOR)

        if events:
            event_ids = [ev.id for ev in events]
            prep_stmt2 = (
                select(PreparationItem)
                .where(PreparationItem.event_id.in_(event_ids))
                .order_by(PreparationItem.created_at)
            )
            preps_after = list((await db.execute(prep_stmt2)).scalars().all())
            print(f"找到 {len(preps_after)} 个准备条目:")
            for p in preps_after:
                done_mark = "✓" if p.done else "○"
                print(f"  {done_mark} [{p.source}] {p.text}")
        else:
            print("  (无关联事件)")

        print(f"\n{SEPARATOR}")
        print("诊断完成")
        print(SEPARATOR)


if __name__ == "__main__":
    asyncio.run(diagnose())
