"""Base class for domain tool executors."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger

from ..shared.progress import ProgressCallback

logger = get_logger(__name__)


class BaseToolExecutor:
    """Base class providing common utilities for domain executors."""

    def __init__(
        self,
        db: AsyncSession,
        session_id: Optional[UUID] = None,
    ) -> None:
        self.db = db
        self.session_id = session_id

    def _emit_progress(
        self,
        callback: Optional[ProgressCallback],
        stage: str,
        message: str,
    ) -> None:
        """Emit a progress update if a callback is available."""
        if callback:
            try:
                callback(stage, message)
            except Exception as exc:
                logger.warning(f"Progress callback error: {exc}")
