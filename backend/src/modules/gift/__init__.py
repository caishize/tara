"""Gift module - unified gift management.

Merges gift_recommendation + gift_orchestration + trending_gifts
into a single cohesive module for recommendations, tracking,
trending discovery, and price monitoring.
"""
from .api import router
from .api_tasks import router as tasks_router
from .api_trending import router as trending_router

__all__ = ["router", "tasks_router", "trending_router"]
