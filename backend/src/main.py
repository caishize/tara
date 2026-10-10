"""
FastAPI application entry point.
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import uuid
import asyncio

from .config.settings import settings
from .config.logging import setup_logging, get_logger
from .db.session import init_db, close_db
from .core.cache import redis_client
from .celery_app import celery_app as _celery_app  # noqa: F401 — ensure Celery app is loaded for @shared_task


# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting application...")

    # Safety check: non-development environments must have strict auth enabled.
    # Prevents configuration drift from silently disabling auth in production.
    if settings.environment != "development" and not settings.strict_auth_enabled:
        raise RuntimeError(
            f"STRICT_AUTH_ENABLED must be True in non-development environments "
            f"(current: environment={settings.environment!r}, "
            f"strict_auth_enabled={settings.strict_auth_enabled!r}). "
            f"Set STRICT_AUTH_ENABLED=true or switch to environment=development."
        )

    await redis_client.connect()

    # Initialize event bus and handlers
    from .core.events import get_event_bus, register_all_handlers
    event_bus = get_event_bus()
    register_all_handlers(event_bus)
    logger.info("Event bus initialized")

    # Initialize FeedbackBus consumers (preference learning loop)
    from .core.feedback import setup_feedback_consumers
    from .db.session import async_session_maker
    setup_feedback_consumers(async_session_maker)
    logger.info("FeedbackBus consumers registered")

    # Scheduler framework: in-process schedulers have been migrated to
    # Redis Sorted Sets + Celery Beat. The scheduler_manager is kept
    # for its monitoring API but no schedulers are registered.
    from .core.scheduler import scheduler_manager
    logger.info("Scheduler framework initialized (tasks dispatched via Redis Sorted Sets + Celery Beat)")

    # Start Agent Worker if enabled or in debug mode (for dev convenience)
    worker_task = None
    if settings.run_agent_worker_in_process or settings.debug:
        from .ai_engine.worker_runner import run_agent_worker_loop

        async def _worker_with_error_logging():
            """Wrapper to surface exceptions from the worker background task."""
            try:
                logger.info(
                    "Agent Worker loop starting (pid=%d, debug=%s, "
                    "run_in_process=%s)",
                    os.getpid(),
                    settings.debug,
                    settings.run_agent_worker_in_process,
                )
                await run_agent_worker_loop()
            except asyncio.CancelledError:
                raise  # let cancellation propagate normally
            except Exception:
                logger.exception(
                    "Agent Worker background task crashed (pid=%d)",
                    os.getpid(),
                )

        worker_task = asyncio.create_task(_worker_with_error_logging())
        logger.info("Agent Worker background task started (in-process, pid=%d)", os.getpid())
    else:
        logger.info(
            "Agent Worker NOT started in-process "
            "(run_agent_worker_in_process=False, debug=False). "
            "Start a standalone worker via: ./scripts/start-agent-worker.sh"
        )

    logger.info("Application started successfully")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Gracefully close WebSocket connections (before Redis disconnect)
    try:
        from .core.websocket.manager import get_websocket_manager
        ws_manager = get_websocket_manager()
        await ws_manager.graceful_shutdown()
        logger.info("WebSocket graceful shutdown complete")
    except Exception as e:
        logger.warning("WebSocket graceful shutdown error: %s", e)

    # Stop worker task
    if worker_task:
        from .ai_engine.worker_runner import request_worker_shutdown
        request_worker_shutdown()       # Signal intentional shutdown first
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Agent Worker background task stopped")

    # Stop any remaining schedulers (none registered after migration)
    await scheduler_manager.stop_all(timeout=5.0)
    logger.info("Scheduler manager stopped")

    # Clean up web search service HTTP client (if available)
    try:
        from .ai_engine.tools.web_search import cleanup_web_search_service
        await cleanup_web_search_service()
    except (ImportError, AttributeError):
        pass  # web search cleanup not available

    await redis_client.disconnect()
    await close_db()
    logger.info("Application shut down successfully")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Secretary - AI-Powered Family Assistant API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


# Rate limiting middleware (added before CORS so that CORS headers are
# present on 429 responses — Starlette middleware wraps in reverse order,
# so the last add_middleware call runs outermost / first).
from .core.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "path": request.url.path,
            "method": request.method
        }
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", None)
            }
        }
    )


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Overall health check."""
    return {
        "status": "healthy",
        "service": "Secretary",
        "environment": settings.environment
    }


@app.get("/health/db", tags=["Health"])
async def health_check_db():
    """Database health check."""
    try:
        from sqlalchemy import text
        from .db.session import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy", "service": "database"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "service": "database"}
        )


@app.get("/health/redis", tags=["Health"])
async def health_check_redis():
    """Redis health check."""
    try:
        if await redis_client.ping():
            return {"status": "healthy", "service": "redis"}
        else:
            raise Exception("Redis ping failed")
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "service": "redis"}
        )


# K8s health probes (/healthz, /readyz, /startupz)
from .core.observability import health_check_router
app.include_router(health_check_router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "service": "Secretary - Member Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


# ── Route Registration (New Architecture: 16 route groups) ──────────────────
# All routes are registered via the unified register_v1_routes() function.
# This replaces the old per-module router includes.
from .api.v1 import register_v1_routes
register_v1_routes(app)
