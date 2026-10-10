# Observability

## Logging

- **Backend**: Python `logging` module with structured JSON output
- **Key loggers**: Per-module loggers (`logger = logging.getLogger(__name__)`)
- **Sensitive data**: Never log API keys, passwords, or user PII in plain text

## Audit Trail

- **Location**: `backend/src/core/audit/`
- **What's audited**: Tool executions via ToolGateway, PendingAction confirmations, sensitive operations
- **Storage**: Database audit table

## Monitoring

- **Location**: `backend/src/core/observability/`
- **Health check**: FastAPI `/health` endpoint
- **Service status**: `scripts/start.sh status` shows PostgreSQL, Redis, Backend, Celery Worker, Celery Beat status

## Key Metrics to Watch

| Metric | Source | Alert Threshold |
|--------|--------|----------------|
| Intent routing latency | IntentRouter | >500ms |
| Intervention classification | InterventionClassifier | >150ms |
| Cold start context rebuild | build_cold_start_conversation | >3s |
| Agent SDK client pool | ClaudeSDKClient pool | >80% utilization |
| Outbox relay lag | Celery outbox task | >30s behind |
| WebSocket connections | WebSocket manager | >1000 per instance |

## Debugging

```bash
# Check service status
./scripts/start.sh status

# Tail backend logs
cd backend && uvicorn src.main:app --reload --log-level debug

# Check Celery task status
cd backend && celery -A src.celery_app inspect active

# Redis session state
redis-cli GET "session:status:{session_id}"
redis-cli GET "user:active_session:{user_id}"
```
