import logging
from time import perf_counter

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.admin import router as admin_router
from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.cases import router as cases_router
from app.api.dashboard import router as dashboard_router
from app.api.dataset import router as dataset_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.limiter import limiter
from app.core.deps import get_db
from app.database.session import init_db

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description=(
        "Research prototype for medical image preprocessing and model-based artery segmentation. "
        "Model outputs are not clinical diagnoses or validated stenosis measurements."
    ),
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: JSONResponse(status_code=429, content={"detail": "Too many requests. Please wait and try again."}),
)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Page-Limit", "X-Page-Offset"],
)


@app.on_event("startup")
def on_startup():
    log_path = configure_logging(settings)
    logger.info("Application file logging initialized at %s", log_path)
    init_db()
    logger.info("Database initialization completed")


@app.middleware("http")
async def log_request_telemetry(request, call_next):
    """Log request outcome and latency without recording request data or IDs."""
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        logger.exception("HTTP request failed method=%s route=%s", request.method, route)
        raise

    route = getattr(request.scope.get("route"), "path", "unmatched")
    logger.info(
        "HTTP request completed method=%s route=%s status=%s duration_ms=%.1f",
        request.method,
        route,
        response.status_code,
        (perf_counter() - started) * 1000,
    )
    return response


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    """Readiness probe for the API and its database dependency."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Health database probe failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "service": settings.app_name,
                "checks": {"database": "unavailable"},
            },
        )
    return {
        "status": "ok",
        "service": settings.app_name,
        "checks": {"database": "ok"},
    }


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(cases_router)
app.include_router(dashboard_router)
app.include_router(dataset_router)
app.include_router(analysis_router)
