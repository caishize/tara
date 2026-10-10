# Gift

## Purpose
Gift recommendation engine — profile-based smart suggestions, price tracking, trending discovery, occasion matching, budget guidance, and gift task lifecycle management.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models*, .schemas, ..member.interface, ..memory.interface
- **Forbidden imports**: ai_engine.*, api.*

## Key Files
| File | Purpose |
|------|---------|
| recommendation_service.py | Profile-based smart gift recommendations |
| smart_recommendation.py | LLM-enhanced recommendation refinement |
| budget_suggestion_service.py | Budget range suggestions per occasion/relationship |
| occasion_service.py | Maps dates/events to gift occasions |
| trending_service.py | Discovers trending gift ideas |
| price_tracker.py | Tracks price history for saved gifts |
| task_service.py | Gift task state machine (discovered→purchased→completed) |
| preference_learning.py | Learns recipient preferences from feedback |
| scrapers/ | External product data scrapers |
| providers/ | Gift data provider integrations |
| tasks.py | Celery tasks: `gift.*` on default queue |

## Module Conventions
- Gift task lifecycle: `discovered → recommended → purchased → shipped → completed`
- Scrapers must handle failures gracefully (no mock data in production)
- Dedup via `dedup_analyzer.py` before presenting recommendations
- Memory integration for recipient preference recall
