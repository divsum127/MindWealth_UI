"""MindWealth FastAPI application."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import optional_api_key
from api.jobs.runner import shutdown_executor
from api.routers import analytics, chatbot, conviction, macro, monitored_trades, portfolio, signals, virtual_trading
from api.schemas.conviction import HealthResponse
from api.services import conviction_service as svc
from src.config_paths import CONVICTION_STORE_DIR

API_VERSION = "1.7.3"
API_PREFIX = "/api/v1"

_default_origins = "http://localhost:8504,http://localhost:8509,http://127.0.0.1:8504,http://127.0.0.1:8509"
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    CONVICTION_STORE_DIR.mkdir(parents=True, exist_ok=True)
    yield
    shutdown_executor()


app = FastAPI(
    title="MindWealth API",
    description="REST API for MindWealth trading analysis services.",
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conviction.router, prefix=API_PREFIX)
app.include_router(chatbot.router, prefix=API_PREFIX)
app.include_router(signals.router, prefix=API_PREFIX)
app.include_router(monitored_trades.router, prefix=API_PREFIX)
app.include_router(virtual_trading.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(macro.router, prefix=API_PREFIX)
app.include_router(portfolio.router, prefix=API_PREFIX)


@app.get(
    f"{API_PREFIX}/health",
    tags=["health"],
    operation_id="get_health",
    response_model=HealthResponse,
    dependencies=[Depends(optional_api_key)],
)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=API_VERSION,
        conviction_store=str(CONVICTION_STORE_DIR),
        conviction_store_writable=svc.conviction_store_writable(),
    )
