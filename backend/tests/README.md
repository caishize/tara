# Secretary Backend Tests

Complete test suite for the Secretary (家庭秘书) backend application.

## Test Structure

```
tests/
├── conftest.py              # Shared pytest fixtures
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_member_service.py
│   ├── test_date_service.py
│   ├── test_gift_service.py
│   └── test_encryption_service.py
├── integration/             # Integration tests (database required)
│   └── test_member_api.py
└── contract/                # Contract tests (external APIs)
```

## Test Coverage

### Unit Tests (36 tests)
- **Module 001 - Member Management** (11 tests)
  - CRUD operations
  - Phone/email encryption
  - Profile completion calculation
  - Soft deletion

- **Module 002 - Date/Time Management** (12 tests)
  - Solar/lunar calendar support
  - Recurring dates
  - Reminder creation
  - Health data encryption

- **Module 003 - Gift Recommendation** (13 tests)
  - LLM-based recommendations
  - Budget filtering
  - 3-year deduplication
  - Feedback learning
  - Price encryption

### Integration Tests (8 tests)
- **Member Management API**
  - All CRUD endpoints
  - Validation handling
  - Health checks

## Running Tests

### Prerequisites

1. **Database Setup**: Create a test database
   ```bash
   # PostgreSQL
   createdb secretary_test
   ```

2. **Environment Variables**: Ensure `.env` is configured
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost/secretary_test
   ENCRYPTION_KEY=<32-byte-hex-key>
   ```

### Run All Tests

```bash
cd backend
pytest
```

### Run Specific Test Types

```bash
# Unit tests only (fast)
pytest -m unit

# Integration tests only
pytest -m integration

# Specific module
pytest tests/unit/test_member_service.py

# Specific test
pytest tests/unit/test_member_service.py::TestMemberService::test_create_member_success
```

### With Coverage Report

```bash
# Terminal report
pytest --cov=src --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Verbose Output

```bash
# Show all test names and details
pytest -vv

# Show print statements
pytest -s
```

## Test Markers

Tests are marked with the following markers:

- `@pytest.mark.unit`: Fast, isolated unit tests
- `@pytest.mark.integration`: Integration tests requiring database
- `@pytest.mark.contract`: Contract tests with external services
- `@pytest.mark.asyncio`: Async tests (handled automatically)

## Writing New Tests

### Unit Test Example

```python
import pytest
from uuid import UUID

@pytest.mark.unit
@pytest.mark.asyncio
class TestMyService:
    @pytest.fixture
    async def my_service(self, db_session):
        return MyService(db_session)

    async def test_something(self, my_service):
        result = await my_service.do_something()
        assert result is not None
```

### Integration Test Example

```python
import pytest
from httpx import AsyncClient

@pytest.mark.integration
@pytest.mark.asyncio
class TestMyAPI:
    async def test_endpoint(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/resource")
        assert response.status_code == 200
```

## Available Fixtures

### From `conftest.py`

- `db_session`: Async database session with rollback
- `async_client`: HTTP client for API testing
- `test_family_id`: Sample family UUID
- `test_user_id`: Sample user UUID
- `auth_token`: Mock JWT token (TODO: real auth)

### Custom Fixtures

Define module-specific fixtures in your test files:

```python
@pytest.fixture
async def sample_data(self):
    return {"key": "value"}
```

## Continuous Integration

Tests are designed to run in CI environments:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    cd backend
    pytest -m "unit or integration" --cov=src
```

## Troubleshooting

### Database Connection Errors

Ensure test database exists and is accessible:
```bash
psql -c "SELECT 1" postgresql://localhost/secretary_test
```

### Async Test Warnings

If you see event loop warnings, ensure:
- Test functions are marked with `@pytest.mark.asyncio`
- `asyncio_mode = auto` is set in `pytest.ini`

### Fixture Scope Issues

Fixtures use `function` scope by default for test isolation.
Only change scope if you understand the implications.

## Next Steps

- [ ] Add integration tests for modules 002-006
- [ ] Add contract tests for LLM provider
- [ ] Add performance/load tests
- [ ] Achieve >80% code coverage
- [ ] Set up CI/CD test pipeline

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [HTTPX AsyncClient](https://www.python-httpx.org/async/)
