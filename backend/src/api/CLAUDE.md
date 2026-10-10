# API Routes

## Purpose
FastAPI v1 REST endpoints — thin routing layer that validates requests, calls services, and returns responses. No business logic lives here.

## Layer Rules
- **Layer**: API (topmost layer)
- **Allowed imports**: core.auth, core.rate_limit, modules.*.interface, modules.*.schemas, ai_engine.interface
- **Forbidden imports**: modules.*.services, modules.*.models (use schemas/interfaces only)

## Key Files
| File | Purpose |
|------|---------|
| v1/chat.py | Chat endpoint — session status check, intent routing, WebSocket streaming |
| v1/auth.py | Login, register, token refresh |
| v1/members.py | Family member CRUD |
| v1/trips.py | Trip planning endpoints |
| v1/gifts.py | Gift recommendations and task management |
| v1/dates.py | Important dates and reminders |
| v1/insights.py | Insight feed, feedback, adoption |
| v1/briefing.py | Briefing generation and delivery |
| v1/kanban.py | Kanban board operations |
| v1/views.py | Timeline, graph, search endpoints |
| v1/memory.py | Memory recall and management |
| v1/websocket.py | WebSocket connection handler |
| v1/actions.py | PendingAction confirmation/rejection |

## Module Conventions
- All routes require `Depends(get_current_user)` for JWT auth
- Use Pydantic schemas for request/response validation (never raw dicts)
- Route handlers should be thin: validate → delegate to service → return
- Family isolation: verify member belongs to family before any data access
- Error responses follow `ApiResponse` pattern with `success`, `data`, `error` fields
