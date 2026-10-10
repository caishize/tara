# Trip

## Purpose
Travel planning module — manages trip plans, daily itineraries, expense tracking, budget suggestions, and packing lists. Integrates with curation for event linking.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, .schemas, ..member.interface, ..curation.interface
- **Forbidden imports**: ai_engine.*, api.*

## Key Files
| File | Purpose |
|------|---------|
| services/ | Trip CRUD, itinerary generation, budget tracking |
| models/ | SQLAlchemy models: TripPlan, ItineraryDay, Expense, PackingItem |
| schemas/ | Pydantic request/response schemas |
| parsers/ | LLM output parsers for itinerary suggestions |
| api/ | Module-internal API helpers (not route definitions) |
| interface.py | Public DTOs: TripPlanDTO, ItineraryDayDTO, ExpenseSummaryDTO |

## Module Conventions
- Trip status lifecycle: `planning → confirmed → in_progress → completed → cancelled`
- `create_trip` is a non-interruptible tool (intervention signals deferred)
- Budget tracking uses actual_expense vs budget comparison
- Trip completeness checked by curation's `trigger_dispatcher` (T1)
