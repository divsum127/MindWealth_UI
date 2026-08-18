"""MindWealth FastAPI application."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from api.dependencies import optional_api_key, require_api_key
from api.rate_limit import RateLimitMiddleware, limiter, rate_limit_exceeded_handler
from api.jobs.runner import shutdown_executor
from api.routers import analytics, activity, auth, chatbot, conviction, macro, meta, monitored_trades, overwatch, portfolio, signals, system, virtual_trading
from api.schemas.conviction import HealthResponse
from api.services import conviction_service as svc
from src.config_paths import CONVICTION_STORE_DIR

API_VERSION = "1.12.0"
API_PREFIX = "/api/v1"

_default_origins = "http://localhost:8504,http://localhost:8509,http://127.0.0.1:8504,http://127.0.0.1:8509,http://localhost:8512,http://127.0.0.1:8512"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

_docs_enabled = os.getenv("DOCS_ENABLED", "true").strip().lower() not in {"0", "false", "no"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    CONVICTION_STORE_DIR.mkdir(parents=True, exist_ok=True)
    # Chat jobs run in worker threads in this process, so anything still marked
    # running belongs to a process that no longer exists. Left alone, a client
    # polls that job forever and eventually reports the analyst as unreachable.
    try:
        from api.jobs.store import get_job_store  # noqa: PLC0415

        orphaned = get_job_store().fail_orphaned()
        if orphaned:
            logging.getLogger(__name__).warning(
                f"Marked {orphaned} chat job(s) as failed — interrupted by a previous restart"
            )
    except Exception as exc:  # never block startup over housekeeping
        logging.getLogger(__name__).warning(f"Could not reconcile orphaned chat jobs: {exc}")

    # Overwatch scans run here rather than in cron: the SSE event bus is
    # per-process, so a cron process publishes to nobody. See overwatch_runner.
    overwatch_tasks = []
    try:
        from api.services import overwatch_runner  # noqa: PLC0415

        overwatch_tasks = overwatch_runner.start()
    except Exception as exc:
        logging.getLogger(__name__).warning(f"Overwatch scheduler did not start: {exc}")

    yield

    for task in overwatch_tasks:
        task.cancel()
    shutdown_executor()


app = FastAPI(
    title="MindWealth API",
    description="REST API for MindWealth trading analysis services.",
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(activity.router, prefix=API_PREFIX)
app.include_router(conviction.router, prefix=API_PREFIX)
app.include_router(chatbot.router, prefix=API_PREFIX)
app.include_router(signals.router, prefix=API_PREFIX)
app.include_router(monitored_trades.router, prefix=API_PREFIX)
app.include_router(virtual_trading.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(macro.router, prefix=API_PREFIX)
app.include_router(portfolio.router, prefix=API_PREFIX)
app.include_router(overwatch.router, prefix=API_PREFIX)
app.include_router(system.router, prefix=API_PREFIX)
app.include_router(meta.router, prefix=API_PREFIX)


@app.get(
    f"{API_PREFIX}/health",
    tags=["health"],
    operation_id="get_health",
    response_model=HealthResponse,
    dependencies=[Depends(require_api_key)],
)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=API_VERSION,
        conviction_store=str(CONVICTION_STORE_DIR),
        conviction_store_writable=svc.conviction_store_writable(),
    )
