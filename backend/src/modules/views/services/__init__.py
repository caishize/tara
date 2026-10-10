"""Views services package.

Unified display layer services (merged from kanban + graph modules).

Kanban services:
    - KanbanService: Semantic grouping of future events
    - MemoryLaneService: Past events organized into story groups
    - EventDetailService: Enriched event context for detail views
    - PreparationService: Preparation checklist CRUD
    - SearchService: Full-text event search
    - TimelineService: Curated timeline with directional pagination
    - EventContextService: Facade over all kanban services

Graph services:
    - EventGraphService: Graph construction and visualization
    - KnowledgeGraphService: Relationship/entity graph management
    - AssociationManager: Association CRUD operations
"""
from .kanban_service import KanbanService
from .memory_lane_service import MemoryLaneService
from .event_detail_service import EventDetailService
from .preparation_service import PreparationService
from .search_service import SearchService
from .timeline_service import TimelineService
from .event_context_service import EventContextService
from .graph_service import EventGraphService
from .knowledge_graph_service import KnowledgeGraphService
from .association_manager import AssociationManager

__all__ = [
    "KanbanService",
    "MemoryLaneService",
    "EventDetailService",
    "PreparationService",
    "SearchService",
    "TimelineService",
    "EventContextService",
    "EventGraphService",
    "KnowledgeGraphService",
    "AssociationManager",
]
