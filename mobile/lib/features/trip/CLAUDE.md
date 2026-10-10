# Trip Module

## Purpose
Travel planning UI: trip CRUD, AI-generated smart itineraries with style/preference config, day-by-day schedule editing, expense tracking, destination recommendations, trip memories/photos, itinerary versioning, and association summaries.

## Layer Rules
- **Layer**: feature (`features/trip/`)
- **Allowed imports**: `core/`, `shared/`, `domain/` and `data/` within this feature
- **Forbidden imports**: other `features/` modules

## Key Files
| File | Purpose |
|------|---------|
| `presentation/bloc/trip_bloc.dart` | Single BLoC for all trip operations (events/state in same file) |
| `presentation/pages/trip_page.dart` | Trip list with status/category filters |
| `presentation/pages/trip_detail_page.dart` | Trip detail with overview + schedule tabs |
| `presentation/pages/create_trip_page.dart` | Trip creation form |
| `domain/repositories/trip_repository.dart` | Abstract contract: trips, itinerary, expenses, memories, recommendations |
| `domain/entities/trip.dart` | Trip entity with TripStatus and TripCategory enums |
| `domain/entities/smart_itinerary.dart` | AI-generated itinerary with style metadata |
| `data/datasources/trip_remote_datasource.dart` | All trip API calls via Dio |
| `data/models/trip_context_model.dart` | Contextual data for smart generation |
| `data/models/association_summary_model.dart` | Curated association links |

## Module Conventions
- Single `TripBloc` handles all operations (unlike kanban's 9 BLoCs)
- `dartz` `Either<Failure, T>` for repository returns
- Smart itinerary generation: config sheet -> loading dialog -> result
- Itinerary editing: activity actions (swap days, fill gaps, add/remove activities)
- Trip associations link to kanban curated events (`trip_associations_section.dart`)
- Budget tracking via `budget_overview_card` and `enhanced_budget_card`
