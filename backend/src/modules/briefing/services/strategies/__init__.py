"""Briefing suggestion strategy pattern."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .....config.logging import get_logger

logger = get_logger(__name__)


class SuggestionStrategy(ABC):
    """Base class for suggestion generation strategies."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @abstractmethod
    async def generate(
        self,
        user_id: UUID,
        family_id: Optional[UUID] = None,
    ) -> List[Any]:
        """Generate suggestions from the given context.

        Returns a list of Suggestion pydantic model instances.
        """
        ...
