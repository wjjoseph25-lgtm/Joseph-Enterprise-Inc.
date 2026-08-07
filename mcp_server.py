"""MCP tool surface for the Orora Swiss Ephemeris engine."""

from __future__ import annotations

import inspect
import os
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from app.ephemeris import calculate_chart as calculate_chart_impl

load_dotenv()


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def _transport_security_settings():
    allowed_hosts = _csv_env("MCP_ALLOWED_HOSTS")
    allowed_origins = _csv_env("MCP_ALLOWED_ORIGINS")
    if not allowed_hosts and not allowed_origins:
        return None

    try:
        from mcp.server.transport_security import TransportSecuritySettings
    except ImportError as exc:  # pragma: no cover - depends on installed MCP release
        raise RuntimeError(
            "This MCP SDK release does not support transport security settings. "
            "Upgrade mcp before deploying publicly."
        ) from exc

    return TransportSecuritySettings(
        allowed_hosts=allowed_hosts or ["localhost:*", "127.0.0.1:*"],
        allowed_origins=allowed_origins,
    )


def _fast_mcp_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "name": "Orora Swiss Ephemeris",
        "instructions": (
            "Use calculate_chart to calculate a tropical Regiomontanus horary chart. "
            "Prefer an IANA timezone name so daylight-saving time is resolved correctly."
        ),
        "stateless_http": True,
        "json_response": True,
        # The FastAPI app mounts this ASGI app at /mcp. Using / here prevents /mcp/mcp.
        "streamable_http_path": "/",
    }
    transport_security = _transport_security_settings()
    if transport_security is not None:
        if "transport_security" not in inspect.signature(FastMCP).parameters:
            raise RuntimeError(
                "This MCP SDK release does not accept transport security settings. "
                "Upgrade mcp before deploying publicly."
            )
        kwargs["transport_security"] = transport_security
    return kwargs


mcp = FastMCP(**_fast_mcp_kwargs())


@mcp.tool(
    name="calculate_chart",
    title="Calculate horary chart",
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def calculate_chart(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    latitude: float,
    longitude: float,
    timezone_name: str | None = None,
    timezone_offset: float | None = None,
    second: int = 0,
    fold: int = 0,
) -> dict:
    """Calculate a Regiomontanus horary chart using Swiss Ephemeris.

    Use ``timezone_name`` such as ``America/New_York`` for DST-safe production
    calculations. ``timezone_offset`` is supported only as a fixed-offset fallback.
    Use ``fold=1`` for the second occurrence of an ambiguous fall-back local time.
    """
    return calculate_chart_impl(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        timezone_name=timezone_name,
        timezone_offset=timezone_offset,
        fold=fold,
        latitude=latitude,
        longitude=longitude,
        house_system="R",
    )

calculate_chart
