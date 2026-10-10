"""API v1 route registration.

Provides ``register_v1_routes(app)`` which attaches all modular API routers
under ``/api/v1``.  Called from main.py at startup.

15 route groups per api-redesign.md:
  auth, chat, kanban, briefing, memory, graph, trips, gifts,
  members, dates, relationships, actions, websocket, curation, devices
"""
from fastapi import FastAPI

from .auth import router as auth_router
from .chat import router as chat_router
from .kanban import router as kanban_router
from .briefing import router as briefing_router
from .memory import router as memory_router
from .graph import router as graph_router
from .trips import router as trips_router
from .gifts import router as gifts_router
from .gift_memory import router as gift_memory_router
from .gift_browse import router as gift_browse_router
from .members import router as members_router
from .people import router as people_router
from .user_services import router as user_services_router
from .dates import router as dates_router
from .relationships import router as relationships_router
from .actions import router as actions_router
from .websocket import router as websocket_router
from .curation import router as curation_router
from .devices import router as devices_router
from .connections import router as connections_router
from .report import router as report_router
from .data import router as data_router
from .notes import router as notes_router
from .assistant import router as assistant_router
from .views import router as views_router
from .insights import router as insights_router


def register_v1_routes(app: FastAPI) -> None:
    """Register all v1 API routers on the given FastAPI application."""
    prefix = "/api/v1"

    # Auth
    app.include_router(auth_router, prefix=prefix)

    # Core: Chat (main entry point), Assistant (onboarding)
    app.include_router(chat_router, prefix=prefix)
    app.include_router(assistant_router, prefix=prefix)

    # Views: Kanban, Briefing, Graph, Views (compatibility)
    app.include_router(kanban_router, prefix=prefix)
    app.include_router(briefing_router, prefix=prefix)
    app.include_router(graph_router, prefix=prefix)
    app.include_router(views_router, prefix=prefix)

    # Domain: Memory, Notes, Trips, Gifts, Members, Dates, Relationships
    app.include_router(memory_router, prefix=prefix)
    app.include_router(notes_router, prefix=prefix)
    app.include_router(trips_router, prefix=prefix)
    app.include_router(gifts_router, prefix=prefix)
    app.include_router(gift_memory_router, prefix=prefix)
    app.include_router(gift_browse_router, prefix=prefix)
    # user_services_router MUST be registered before members_router because
    # members_router has a /{member_id} catch-all that would match /smart-services
    # and /stats paths, causing 422 when FastAPI tries to parse them as UUIDs.
    app.include_router(user_services_router, prefix=prefix)
    app.include_router(members_router, prefix=prefix)
    app.include_router(people_router, prefix=prefix)
    app.include_router(dates_router, prefix=prefix)
    app.include_router(relationships_router, prefix=prefix)

    # System: Actions, WebSocket, Curation, Devices
    app.include_router(actions_router, prefix=prefix)
    app.include_router(websocket_router, prefix=prefix)
    app.include_router(curation_router, prefix=prefix)
    app.include_router(devices_router, prefix=prefix)

    # Profile: Connections, Report, Data Management
    app.include_router(connections_router, prefix=prefix)
    app.include_router(report_router, prefix=prefix)
    app.include_router(data_router, prefix=prefix)

    # Unified Insights: cross-table feedback endpoint (PLAN-006)
    app.include_router(insights_router, prefix=prefix)
