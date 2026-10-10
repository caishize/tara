"""Health check endpoints for K8s probes.

Implements the three-probe model:
- ``/healthz``  -- liveness (process alive)
- ``/readyz``   -- readiness (DB + Redis reachable)
- ``/startupz`` -- startup (initial setup complete)
"""

from typing import Dict, Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from ...config.logging import get_logger


logger = get_logger(__name__)

health_check_router = APIRouter(tags=["health"])


@health_check_router.get("/healthz")
async def liveness() -> Dict[str, str]:
    """Liveness probe -- process is alive."""
    return {"status": "ok"}


@health_check_router.get("/readyz")
async def readiness() -> JSONResponse:
    """Readiness probe -- DB + Redis reachable."""
    checks: Dict[str, str] = {}

    # Database check
    try:
        from ...db.session import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.error("Readiness: database check failed: %s", exc)
        checks["database"] = "fail"

    # Redis check
    try:
        from ..cache import redis_client
        if await redis_client.ping():
            checks["redis"] = "ok"
        else:
            checks["redis"] = "fail"
    except Exception as exc:
        logger.error("Readiness: redis check failed: %s", exc)
        checks["redis"] = "fail"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )


@health_check_router.get("/startupz")
async def startup() -> Dict[str, str]:
    """Startup probe -- initial setup complete."""
    return {"status": "ok"}
