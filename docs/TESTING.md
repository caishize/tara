# Secretary Testing Strategy

## Test Structure

```
backend/tests/
├── unit/           # Unit tests (isolated, no external deps)
├── integration/    # Integration tests (requires DB, Redis)
├── manual/         # Manual/exploratory tests
├── contract/       # Contract tests (API contracts)
└── conftest.py     # Shared fixtures

mobile/test/
├── features/       # Feature-specific tests
└── widget_test.dart
```

## Commands

```bash
# Backend
cd backend && pytest                               # All tests
cd backend && pytest tests/unit/                    # Unit only
cd backend && pytest tests/integration/             # Integration only
cd backend && pytest --cov=src --cov-report=html   # With coverage report
cd backend && pytest -x -q                         # Fast fail, quiet
cd backend && pytest -k "test_name"                # Run specific test

# Mobile
cd mobile && flutter test                          # All tests
cd mobile && flutter test test/features/chat/      # Feature-specific
```

## Configuration

See `backend/pytest.ini`:
- `asyncio_mode = auto` — async tests run automatically
- `--cov=src --cov-report=term-missing` — coverage enabled by default
- Markers: `unit`, `integration`, `contract`, `asyncio`

## Test-Driven Development (TDD)

Mandatory workflow for new features and bug fixes:
1. **RED**: Write test first — it should FAIL
2. **GREEN**: Write minimal implementation to PASS
3. **IMPROVE**: Refactor while keeping tests green
4. Target: **80%+ coverage**

## Testing Rules

- **Mock data only in `tests/`** — production code must never return mock data
- **Use absolute imports** in tests: `from src.modules.xxx import ...`
- **Async tests**: Use `pytest.mark.asyncio` (auto mode handles most cases)
- **Fixtures**: Shared fixtures in `conftest.py`, module-specific fixtures co-located

## CI/CD

GitHub Actions (`.github/workflows/test.yml`):
- Triggers: push/PR to main/develop
- Services: PostgreSQL 15, Redis 7
- Steps: install deps → migrations → tests with coverage → lint (black, flake8, mypy)
