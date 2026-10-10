# Secretary Conventions

> The "Taste" — mechanical rules that enforce project quality. Every rule here should be
> testable by a structural test or lint rule.

## Code Organization

| Rule | Details |
|------|---------|
| **File size limit** | 500 lines max (Python), 400 lines max (Dart) |
| **Module structure** | Feature-based: each module in `backend/src/modules/<name>/` |
| **Mobile features** | `mobile/lib/features/<name>/` with BLoC pattern |

## Import Rules

### Backend (Python)
- **Within `backend/src/`**: Use **relative imports** (`from .service import ...`)
- **In `tests/`**: Use **absolute imports** (`from src.modules.xxx import ...`)
- **Circular imports**: Resolve with `__getattr__` lazy import (e.g., memory↔insight)
- **Layer direction**: Lower layers must NOT import from higher layers (see [ARCHITECTURE.md](ARCHITECTURE.md))

### Mobile (Dart)
- Feature modules import from `core/` and `shared/` only
- No cross-feature imports (features communicate via BLoC events)

## Naming Conventions

### Backend
- **Files**: `snake_case.py` — `user_service.py`, `trip_repository.py`
- **Classes**: `PascalCase` — `TripService`, `InsightOrchestrator`
- **Functions**: `snake_case` — `get_active_trips()`, `build_cold_start_conversation()`
- **Celery task names**: String identifiers with domain prefix (`assistant.*`, `secretary.*`, `events.*`, `gift.*`, `trending_gifts.*`, `reminder.*`, `scheduler.*`), NOT Python import paths
- **API routes**: kebab-case URLs `/api/v1/family-members/{id}`

### Mobile
- **Files**: `snake_case.dart` — `chat_bloc.dart`, `trip_screen.dart`
- **Classes**: `PascalCase` — `ChatBloc`, `TripScreen`
- **BLoC pattern**: `<Feature>Bloc`, `<Feature>Event`, `<Feature>State`

## DateTime Rules

| Layer | Rule |
|-------|------|
| **Database** | UTC, `TIMESTAMP WITH TIME ZONE` (NEVER bare `TIMESTAMP`) |
| **API transport** | ISO 8601 UTC: `2026-01-28T00:00:00Z` |
| **Application** | Convert to user timezone before display |
| **SQLAlchemy columns** | Must use `DateTime(timezone=True)` |
| **Time source** | `core.utils.timezone.utc_now()` is the ONLY time source |

```python
# Backend
from src.core.utils.timezone import to_utc, to_local, utc_now, DEFAULT_TIMEZONE_NAME

# Mobile
DateTime.parse(iso).toLocal()    # API → display
local.toUtc().toIso8601String()  # display → API
```

## Security Rules

| Rule | Details |
|------|---------|
| **API keys** | `.env` + `.gitignore`, NEVER commit |
| **SQL injection** | ORM parameterized queries only (SQLAlchemy) |
| **Authentication** | ALL API endpoints require JWT: `Depends(get_current_user)` |
| **No hardcoding** | ZERO hardcoded values — use env vars or `config/settings.py` |
| **Family isolation** | `verify_member_belongs_to_family()` on every member operation |
| **Rate limiting** | Tiered by user tier: unauth/free/basic/premium |
| **Spending limits** | `SPENDING_LIMIT_*`, `CONFIRMATION_AMOUNT_THRESHOLD` for over-limit confirmation |

## Data Integrity

- **No mock data in production**: Production must NEVER return mock/fake data. On failure, report error clearly. Mock data ONLY in `tests/` directory.
- **Multi-source fallback**: Try data sources sequentially → all fail → raise explicit error (no silent degradation to fake data).

## Python Compatibility

| Avoid | Use Instead |
|-------|-------------|
| `X \| Y` type union | `Optional[X]` or `Union[X, Y]` |
| `asyncio.timeout()` | `asyncio.wait_for()` |
| `str(Enum)` | `enum_value.value` |

## Logging

Use the project's `get_logger` wrapper, NOT `logging.getLogger`:

```python
from ...config.logging import get_logger

logger = get_logger(__name__)
```

## LLM Client Access

Use the shared client factory from `core/llm/`, NOT direct `AsyncAnthropic()`:

```python
from ...core.llm.haiku_client import get_haiku_client

client = get_haiku_client()
```

## Error Handling

```python
# Always handle errors with context
try:
    result = await risky_operation()
    return result
except SpecificError as e:
    logger.error("Operation failed: %s", e, extra={"context": relevant_data})
    raise
```

## Immutability

Prefer creating new objects over mutating existing ones:
```python
# Correct: new dict
updated = {**original, "key": new_value}

# Wrong: mutation
original["key"] = new_value
```

## Environment Variables

All configuration via `backend/src/config/settings.py` (Pydantic BaseSettings). See `backend/.env.example` for the full list. Core variables:

```
DATABASE_HOST, DATABASE_PASSWORD, REDIS_HOST, JWT_SECRET,
ANTHROPIC_API_KEY, OPENAI_API_KEY, NEO4J_URI, NEO4J_PASSWORD
```
