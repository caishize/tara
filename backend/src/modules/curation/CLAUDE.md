# Curation

## Purpose
Event lifecycle pipeline — collects events from external sources, deduplicates, discovers associations (person/place/task/memory), resolves conflicts, and orchestrates the daily schedule via rule engine + LLM priority scoring.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, .schemas, ..member.interface, ..memory.interface, ..date_manager.interface
- **Forbidden imports**: ai_engine.*, api.*, ..insight.services (use bridge)

## Key Files
| File | Purpose |
|------|---------|
| services/orchestrator.py | Daily schedule orchestration, DayTheme generation |
| services/curation_service.py | Main pipeline: collect → dedup → associate → store |
| services/rule_engine.py | Rule-based event scoring and filtering |
| services/priority_engine.py | HybridPriorityEngine — skips LLM for intimate relations |
| services/association_service.py | Discovers event-entity associations via Haiku |
| services/conflict_detection.py | Time/resource conflict detection |
| services/trigger_dispatcher.py | Proactive trigger dispatch (trip completeness, reminders) |
| services/meal_window_service.py | Statistical meal window inference (no LLM) |
| services/reflection_service.py | Post-session reflection extraction |
| tasks.py | Celery tasks: `curation.*`, `secretary.*` |

## Module Conventions
- Celery tasks use `secretary.*` queue (not default)
- `OrchestratedDay` is the primary output, contains `day_theme` and prioritized events
- Temperature batch status via `asyncio.gather` (parallel, not sequential)
- Association → PendingAction pattern for suggest_meeting/greeting/gift
