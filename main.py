"""FastAPI application exposing REST, health, and MCP endpoints."""

from __future__ import annotations

import logging
import os
from secrets import compare_digest
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import Lock
from typing import Awaitable, Callable

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.ephemeris import calculate_chart, missing_ephemeris_files
from app.mcp_server import mcp
from app.schemas import HoraryChartRequest, HoraryChartResponse

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("orora.ephemeris")


def _truthy_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _valid_mcp_bearer_token(request: Request, configured_key: str) -> bool:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return scheme.lower() == "bearer" and compare_digest(token, configured_key)


mcp_http_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Orora Swiss Ephemeris Engine",
    version="2.0.0",
    lifespan=lifespan,
)

# Baseline per-process limiter. Use a gateway or shared Redis limiter for multi-worker production.
_rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
_rate_windows: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = Lock()


@app.middleware("http")
async def security_and_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started = time.perf_counter()
    path = request.url.path
    response: Response | None = None

    try:
        # Starlette Mount normally redirects /mcp to /mcp/. Rewrite internally so
        # MCP clients can use the exact public URL without a 307 redirect.
        if request.scope.get("path") == "/mcp":
            request.scope["path"] = "/mcp/"
            request.scope["raw_path"] = b"/mcp/"

        if path.startswith("/mcp"):
            configured_key = os.getenv("MCP_API_KEY")
            if configured_key:
                if not _valid_mcp_bearer_token(request, configured_key):
                    response = JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Missing or invalid bearer token"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                    return response
            elif _truthy_env("MCP_AUTH_REQUIRED", True):
                response = JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"detail": "MCP_API_KEY must be set before serving MCP requests"},
                )
                return response

            client_host = request.client.host if request.client else "unknown"
            now = time.monotonic()
            with _rate_lock:
                window = _rate_windows[client_host]
                while window and now - window[0] >= 60:
                    window.popleft()
                if len(window) >= _rate_limit:
                    response = JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Rate limit exceeded"},
                        headers={"Retry-After": "60"},
                    )
                    return response
                window.append(now)

        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "%s %s status=%s duration_ms=%.2f",
            request.method,
            path,
            response.status_code if response is not None else 500,
            duration_ms,
        )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", response_model=None)
def readiness_check():
    missing = missing_ephemeris_files()
    if missing:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "missing_ephemeris_files": missing},
        )
    return {"status": "ready", "missing_ephemeris_files": []}


@app.post("/chart", response_model=HoraryChartResponse)
def calculate_chart_route(payload: HoraryChartRequest) -> dict:
    """REST compatibility endpoint for direct chart calculations."""
    try:
        return calculate_chart(**payload.model_dump())
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


app.mount("/mcp", mcp_http_app)

calculate_chart, missing_ephemeris_files
mcp
HoraryChartRequest, HoraryChartResponse
