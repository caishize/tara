# Kanban Module

## Purpose
Curation timeline hub: curated event timeline, insight feed with feedback, relationship graph visualization, future view with suggestions, memory lane, schedule aggregation, and event search. Largest feature module (~113 files).

## Layer Rules
- **Layer**: feature (`features/kanban/`)
- **Allowed imports**: `core/`, `shared/`, `domain/` and `data/` within this feature
- **Forbidden imports**: other `features/` modules

## Key Files
| File | Purpose |
|------|---------|
| `presentation/bloc/curated_timeline_bloc.dart` | Timeline load, pagination, curation requests, event CRUD |
| `presentation/bloc/insight_feed_bloc.dart` | Insight cards with feedback (useful/not-useful/dismiss) |
| `presentation/bloc/insight_graph_bloc.dart` | Relationship graph data (3D force-directed) |
| `presentation/bloc/kanban_bloc.dart` | Legacy semantic kanban buckets + search |
| `presentation/bloc/schedule_bloc.dart` | Daily schedule aggregation |
| `presentation/bloc/future_view_bloc.dart` | Forward-looking suggestions and upcoming events |
| `presentation/bloc/memory_lane_bloc.dart` | Historical memory highlights |
| `presentation/pages/curated_timeline_page.dart` | Main curated timeline view |
| `presentation/pages/insight_feed_page.dart` | Swipeable insight card feed |
| `domain/entities/curated_event.dart` | Core entity: curated events with associations |
| `insight_graph.dart` | Top-level barrel for graph feature |

## Module Conventions
- 9 BLoCs (kanban, curated_timeline, insight_feed, insight_dismiss, insight_graph, schedule, future_view, memory_lane, action) -- each with separate event/state files
- `dartz` `Either<Failure, T>` for all repository returns (fold pattern in BLoCs)
- Optimistic UI updates (e.g., `TogglePreparationItem` updates state before API)
- Insight styling via `presentation/utils/insight_style.dart` and `insight_title_enricher.dart`
- Skeleton widgets for loading states (`*_skeleton.dart`)
