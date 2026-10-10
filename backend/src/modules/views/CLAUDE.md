# Views

## Purpose
Read-optimized presentation layer — kanban board, timeline, knowledge graph, relationship graph, memory lane, and full-text search across family data.

## Layer Rules
- **Layer**: Service
- **Allowed imports**: core.*, .models, ..curation.interface, ..member.interface, ..memory.interface
- **Forbidden imports**: ai_engine.*, api.*

## Key Files
| File | Purpose |
|------|---------|
| services/kanban_service.py | Kanban board task aggregation and state management |
| services/timeline_service.py | Chronological event timeline with filtering |
| services/graph_service.py | Event relationship graph visualization |
| services/knowledge_graph_service.py | Entity knowledge graph (people, places, topics) |
| services/search_service.py | Full-text + semantic hybrid search |
| services/memory_lane_service.py | Nostalgic memory browsing by date/theme |
| services/event_detail_service.py | Rich event detail assembly |
| services/preparation_service.py | Holiday/event preparation status views |
| task_service.py | Task CRUD for kanban board |
| repositories.py | Shared query layer for view aggregation |

## Module Conventions
- Views are read-only aggregations; mutations go through source modules
- Graph services must handle `Matrix4` carefully (avoid crash on malformed data)
- Search combines FTS (PostgreSQL) + semantic (embeddings) results
- `services/_event_converter.py` and `services/_graph_helpers.py` are internal utilities (prefixed `_`)
