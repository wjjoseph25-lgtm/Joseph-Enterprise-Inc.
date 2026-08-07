"""FastAPI application exposing REST, health, and MCP endpoints."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from secrets import compare_digest
from threading import Lock
from typing import Awaitable, Callable

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from ephemeris import calculate_chart, missing_ephemeris_files
from mcp_server import mcp
from schemas import HoraryChartRequest, HoraryChartResponse


# ---------------------------------------------------------------------------
# Configuration and logging
# ---------------------------------------------------------------------------

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


def _valid_mcp_bearer_token(
    request: Request,
    configured_key: str,
) -> bool:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")

    return (
        scheme.lower() == "bearer"
        and bool(token)
        and compare_digest(token, configured_key)
    )


# ---------------------------------------------------------------------------
# MCP application
# ---------------------------------------------------------------------------

# mcp is imported from mcp_server.py.
# The MCP application is mounted below at /mcp.
mcp_http_app = mcp.streamable_http_app()


# ---------------------------------------------------------------------------
# Main FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Orora Swiss Ephemeris Engine",
    version="2.0.0",
    lifespan=mcp_http_app.lifespan,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

_rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
_rate_windows: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = Lock()


@app.middleware("http")
async def security_and_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started = time.perf_counter()
    original_path = request.url.path
    response: Response | None = None

    try:
        # Avoid a redirect when clients request /mcp without a trailing slash.
        if request.scope.get("path") == "/mcp":
            request.scope["path"] = "/mcp/"
            request.scope["raw_path"] = b"/mcp/"

        if original_path.startswith("/mcp"):
            configured_key = os.getenv("MCP_API_KEY")

            # Require a bearer token only when MCP_API_KEY is configured.
            if configured_key:
                if not _valid_mcp_bearer_token(request, configured_key):
                    response = JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Missing or invalid bearer token"},
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                    return response

            # Optional strict mode. It is disabled by default.
            elif _truthy_env("MCP_AUTH_REQUIRED", False):
                response = JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "detail": (
                            "MCP_API_KEY must be set when "
                            "MCP_AUTH_REQUIRED is enabled"
                        )
                    },
                )
                return response

            client_host = (
                request.client.host
                if request.client is not None
                else "unknown"
            )

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
            original_path,
            response.status_code if response is not None else 500,
            duration_ms,
        )


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root_health() -> dict[str, str]:
    return {"status": "ok"}


@app.head("/")
async def root_health_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", response_model=None)
def readiness_check():
    missing = missing_ephemeris_files()

    if missing:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "missing_ephemeris_files": missing,
            },
        )

    return {
        "status": "ready",
        "missing_ephemeris_files": [],
    }


# ---------------------------------------------------------------------------
# REST compatibility endpoint
# ---------------------------------------------------------------------------

@app.post("/chart", response_model=HoraryChartResponse)
def calculate_chart_route(payload: HoraryChartRequest) -> dict:
    """Calculate a horary chart through the REST API."""

    try:
        return calculate_chart(**payload.model_dump())
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Mount MCP last
# ---------------------------------------------------------------------------

app.mount("/mcp", mcp_http_app)
