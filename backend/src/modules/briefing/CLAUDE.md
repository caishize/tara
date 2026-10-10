# Briefing

## Purpose
Three-period daily briefings (morning/afternoon/evening) — aggregates events, weather, insights, suggestions, and recommendations into personalized push-delivered summaries.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, .schemas, ..curation.interface, ..insight.interface, ..member.interface
- **Forbidden imports**: ai_engine.*, api.*

## Key Files
| File | Purpose |
|------|---------|
| services/briefing_service.py | Main briefing generation orchestration |
| services/briefing_generator.py | Content assembly for each briefing section |
| services/insight_orchestrator.py | Selects and formats insights for briefing delivery |
| services/suggestion_service.py | Contextual suggestion generation |
| services/density_controller.py | Controls information density per user preference |
| services/push_service.py | Push notification delivery |
| services/event_aggregator.py | Aggregates events for briefing time window |
| weather_service.py | Weather data fetching and formatting |
| services/today_service.py | "Today" summary card generation |
| preparation_repository.py | Stores holiday preparation state |
| tasks.py | Celery tasks: holiday prep (daily 06:00), `events.*` queue |

## Module Conventions
- Three briefing periods: morning, afternoon, evening
- Density controller adapts content volume to user engagement patterns
- Insight delivery tracked via `services/insight_delivery_ledger.py` (prevents re-delivery)
- Weather data failures must surface as explicit errors, never mock data
