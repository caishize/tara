# Core

## Purpose
Cross-cutting infrastructure — authentication, domain event bus, job scheduler, WebSocket management, rate limiting, push notifications, LLM client abstractions, caching, and shared utilities.

## Layer Rules
- **Layer**: Core (peer to Service, below AI Engine)
- **Allowed imports**: standard library, third-party packages, .utils
- **Forbidden imports**: modules.* (core must not depend on any module), ai_engine.*

## Key Files
| File | Purpose |
|------|---------|
| auth/auth_service.py | JWT authentication and token management |
| auth/permission_service.py | Role-based access control |
| events/event_bus.py | Domain event publish/subscribe |
| events/outbox.py | Transactional outbox pattern for reliable events |
| events/outbox_relay.py | Outbox relay (Celery: every 5s) |
| scheduler/manager.py | Job scheduler lifecycle management |
| scheduler/dispatcher.py | Schedule dispatch (Celery: every 30s) |
| websocket/ | WebSocket connection management and message push |
| rate_limit/ | Tiered rate limiting (unauth/free/basic/premium) |
| llm/ | LLM client abstractions (Haiku, Sonnet, Opus) |
| push/ | Push notification delivery |
| pubsub/ | Redis pub/sub wrappers |
| cache.py | Redis cache helpers |
| utils/ | Timezone (`utc_now()`), pagination, validators |

## Module Conventions
- `utc_now()` from `core.utils.timezone` is the **only** time source
- All API endpoints require JWT via `Depends(get_current_user)`
- Rate limits configured per tier in `rate_limit/` module
- Domain events flow: Service → outbox → relay (5s) → event_bus → handlers
