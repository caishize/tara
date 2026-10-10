"""
Scheduler test conftest — override the root conftest to avoid
importing src.main (which triggers the playwright issue).
"""
import pytest


@pytest.fixture
def test_family_id() -> str:
    return "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def test_user_id() -> str:
    return "123e4567-e89b-12d3-a456-426614174001"
