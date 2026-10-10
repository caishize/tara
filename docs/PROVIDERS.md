# Cross-Cutting Providers

> Interfaces and implementations that cut across all modules.
> Located in `backend/src/core/interfaces/`.

## Provider Interfaces (ABCs)

| Interface | Purpose | Implementations |
|-----------|---------|----------------|
| `ILLMProvider` | LLM API abstraction | Anthropic (Haiku/Sonnet), OpenAI |
| `IMCPProvider` | MCP server protocol | In-process MCP server for Agent SDK |
| `IEventBus` | Domain event publishing | Redis-backed outbox pattern |
| `IScheduler` | Task scheduling | Redis sorted-set scheduler |

## Authentication & Authorization

- **JWT tokens**: `backend/src/core/auth/`
- **Guard**: `Depends(get_current_user)` on every API endpoint
- **Family isolation**: `verify_member_belongs_to_family()` ensures members can only access own family data

## Rate Limiting

- **Location**: `backend/src/core/rate_limit/`
- **Tiered**: unauth / free / basic / premium — different per-minute/hour/burst limits
- **Applied**: Via FastAPI dependency injection

## Event System

- **Pattern**: Transactional outbox (write events in same DB transaction)
- **Relay**: Celery task every 5 seconds picks up outbox entries
- **Handlers**: `backend/src/core/events/handlers/`

## Push Notifications

- **Provider**: Firebase Cloud Messaging (FCM)
- **Location**: `backend/src/core/push/`

## WebSocket

- **Multi-device**: Users can connect from multiple devices simultaneously
- **PubSub bridge**: Redis PubSub for cross-process WebSocket message distribution
- **Location**: `backend/src/core/websocket/`

## Observability

See [OBSERVABILITY.md](OBSERVABILITY.md) for details.
- **Logging**: Structured JSON logging
- **Audit**: `backend/src/core/audit/` — tracks sensitive operations
- **Metrics**: `backend/src/core/observability/`
