"""MCP tool surface for the Orora Swiss Ephemeris engine."""

from __future__ import annotations

import inspect
import os
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from ephemeris import calculate_chart as calculate_chart_impl


load_dotenv()


def _csv_env(name: str) -> list[str]:
    """Read a comma-separated environment variable."""

    value = os.getenv(name, "")

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def _transport_security_settings():
    """Build optional MCP transport-security settings."""

    allowed_hosts = _csv_env("MCP_ALLOWED_HOSTS")
    allowed_origins = _csv_env("MCP_ALLOWED_ORIGINS")
    default_allowed_hosts = [
        "localhost:*",
        "127.0.0.1:*",
        "joseph-enterprise-inc.onrender.com",
        "*.onrender.com",
    ]

    if not allowed_hosts and not allowed_origins:
        return None

    try:
        from mcp.server.transport_security import (
            TransportSecuritySettings,
        )
    except ImportError as exc:
        raise RuntimeError(
            "The installed MCP SDK does not support transport-security "
            "settings. Upgrade the mcp package."
        ) from exc

    return TransportSecuritySettings(
        allowed_hosts=list(dict.fromkeys([*allowed_hosts, *default_allowed_hosts])),
        allowed_origins=allowed_origins,
    )


def _fast_mcp_kwargs() -> dict[str, Any]:
    """Create settings supported by the installed MCP SDK."""

    kwargs: dict[str, Any] = {
        "name": "Orora Swiss Ephemeris",
        "instructions": (
            "Use calculate_chart to calculate a tropical Regiomontanus "
            "horary chart. Prefer an IANA timezone name so daylight-saving "
            "time is resolved correctly."
        ),
        "stateless_http": True,
        "json_response": True,

        # main.py mounts the MCP ASGI application at /mcp.
        # Using / here avoids producing /mcp/mcp.
        "streamable_http_path": "/",
    }

    transport_security = _transport_security_settings()

    if transport_security is not None:
        constructor_parameters = inspect.signature(
            FastMCP
        ).parameters

        if "transport_security" not in constructor_parameters:
            raise RuntimeError(
                "The installed MCP SDK does not accept transport-security "
                "settings. Upgrade the mcp package."
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
) -> dict[str, Any]:
    """Calculate a tropical Regiomontanus horary chart.

    Prefer timezone_name, such as America/New_York, because it handles
    daylight-saving transitions correctly.

    timezone_offset is available as a fixed-offset fallback. When a local
    time occurs twice during a daylight-saving fall-back transition, use
    fold=1 to select the second occurrence.
    """

    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")

    if not 1 <= day <= 31:
        raise ValueError("day must be between 1 and 31")

    if not 0 <= hour <= 23:
        raise ValueError("hour must be between 0 and 23")

    if not 0 <= minute <= 59:
        raise ValueError("minute must be between 0 and 59")

    if not 0 <= second <= 59:
        raise ValueError("second must be between 0 and 59")

    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")

    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")

    if fold not in {0, 1}:
        raise ValueError("fold must be either 0 or 1")

    if timezone_name is None and timezone_offset is None:
        raise ValueError(
            "Provide either timezone_name or timezone_offset"
        )

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
