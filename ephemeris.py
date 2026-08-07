"""Swiss Ephemeris calculations used by both REST and MCP interfaces."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import swisseph as swe
from dotenv import load_dotenv
from pydantic import ValidationError

from schemas import (
    ChartAngles,
    ChartMetadata,
    HoraryChartRequest,
    HoraryChartResponse,
    HouseCusp,
    PlanetPosition,
)

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_ephe_path() -> str:
    configured = os.getenv("SWEPH_PATH")
    if not configured or not configured.strip():
        return str(PROJECT_ROOT / "ephe")

    path = Path(configured.strip())
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path)


EPHE_PATH = _resolve_ephe_path()
swe.set_ephe_path(EPHE_PATH)

SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)

PLANETS: dict[str, int] = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "True Node": swe.TRUE_NODE,
    "Chiron": swe.CHIRON,
}

CALC_FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED
REQUIRED_EPHEMERIS_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")


def missing_ephemeris_files() -> list[str]:
    base = Path(EPHE_PATH)
    return [name for name in REQUIRED_EPHEMERIS_FILES if not (base / name).is_file()]


def _normalize(degrees: float) -> float:
    return degrees % 360.0


def _sign_details(longitude: float) -> tuple[str, float]:
    normalized = _normalize(longitude)
    sign_index = int(normalized // 30)
    return SIGNS[sign_index], normalized % 30


def _resolve_datetime(
    *,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    timezone_name: str | None,
    timezone_offset: float | None,
    fold: int,
) -> tuple[datetime, datetime, float]:
    try:
        naive = datetime(year, month, day, hour, minute, second)
    except ValueError as exc:
        raise ValueError(f"Invalid local date or time: {exc}") from exc

    if timezone_name:
        try:
            tz = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown IANA timezone: {timezone_name}") from exc

        local_dt = naive.replace(tzinfo=tz, fold=fold)

        # Reject spring-forward wall times that never occurred.
        utc_dt = local_dt.astimezone(timezone.utc)
        round_trip = utc_dt.astimezone(tz).replace(tzinfo=None)
        if round_trip != naive:
            raise ValueError(
                f"The local time {naive.isoformat()} does not exist in {timezone_name} "
                "because of a daylight-saving transition"
            )
    else:
        if timezone_offset is None:
            raise ValueError("Provide timezone_name or timezone_offset")
        tz = timezone(timedelta(hours=timezone_offset))
        local_dt = naive.replace(tzinfo=tz)
        utc_dt = local_dt.astimezone(timezone.utc)

    offset = local_dt.utcoffset()
    if offset is None:
        raise ValueError("Unable to resolve UTC offset for the supplied timezone")

    return local_dt, utc_dt, offset.total_seconds() / 3600.0


def _julian_day(utc_dt: datetime) -> float:
    decimal_hour = (
        utc_dt.hour
        + utc_dt.minute / 60.0
        + utc_dt.second / 3600.0
        + utc_dt.microsecond / 3_600_000_000.0
    )
    return swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        decimal_hour,
        swe.GREG_CAL,
    )


def _house_for_longitude(longitude: float, cusps: tuple[float, ...]) -> int:
    position = _normalize(longitude)
    for index in range(12):
        start = _normalize(cusps[index])
        end = _normalize(cusps[(index + 1) % 12])
        if start < end and start <= position < end:
            return index + 1
        if start > end and (position >= start or position < end):
            return index + 1
        if start == end:
            continue
    return 12


def calculate_chart(
    *,
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int = 0,
    timezone_name: str | None = None,
    timezone_offset: float | None = None,
    tz_offset: float | None = None,
    fold: int = 0,
    latitude: float | None = None,
    longitude: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    house_system: str = "R",
) -> dict[str, Any]:
    """Calculate a tropical Regiomontanus chart with Swiss Ephemeris.

    ``tz_offset``, ``lat``, and ``lon`` remain accepted as compatibility aliases.
    New integrations should use ``timezone_name``, ``latitude``, and ``longitude``.
    """
    if house_system != "R":
        raise ValueError("Only Regiomontanus houses are supported")

    # Swiss Ephemeris keeps state in thread-local storage. FastAPI runs sync
    # routes in worker threads, so set the path for every calculation.
    swe.set_ephe_path(EPHE_PATH)

    missing_files = missing_ephemeris_files()
    if os.getenv("REQUIRE_EPHE_FILES", "false").lower() in {"1", "true", "yes"} and missing_files:
        raise RuntimeError(
            "Required Swiss Ephemeris files are missing: " + ", ".join(missing_files)
        )

    resolved_offset = timezone_offset if timezone_offset is not None else tz_offset
    resolved_latitude = latitude if latitude is not None else lat
    resolved_longitude = longitude if longitude is not None else lon

    if resolved_latitude is None or resolved_longitude is None:
        raise ValueError("Both latitude and longitude are required")

    try:
        request = HoraryChartRequest(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            timezone_name=timezone_name,
            timezone_offset=resolved_offset,
            fold=fold,
            latitude=resolved_latitude,
            longitude=resolved_longitude,
            house_system="R",
        )
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    local_dt, utc_dt, utc_offset_hours = _resolve_datetime(
        year=request.year,
        month=request.month,
        day=request.day,
        hour=request.hour,
        minute=request.minute,
        second=request.second,
        timezone_name=request.timezone_name,
        timezone_offset=request.timezone_offset,
        fold=request.fold,
    )
    julian_day_ut = _julian_day(utc_dt)

    # pyswisseph returns exactly 12 cusps. Keep every cusp; do not use cusps[1:].
    cusps_raw, ascmc = swe.houses(
        julian_day_ut,
        request.latitude,
        request.longitude,
        b"R",
    )
    cusps = tuple(_normalize(float(value)) for value in cusps_raw)
    if len(cusps) != 12:
        raise RuntimeError(f"Swiss Ephemeris returned {len(cusps)} house cusps, expected 12")

    warnings: list[str] = []
    ephemeris_sources: set[str] = set()
    planets: dict[str, PlanetPosition] = {}

    for name, planet_id in PLANETS.items():
        try:
            values, return_flags = swe.calc_ut(julian_day_ut, planet_id, CALC_FLAGS)
        except swe.Error as exc:
            raise RuntimeError(f"Swiss Ephemeris failed while calculating {name}: {exc}") from exc

        planet_longitude = _normalize(float(values[0]))
        sign, degree_in_sign = _sign_details(planet_longitude)
        source = "Swiss Ephemeris" if return_flags & swe.FLG_SWIEPH else "Moshier fallback"
        ephemeris_sources.add(source)

        planets[name] = PlanetPosition(
            name=name,
            longitude=round(planet_longitude, 6),
            latitude=round(float(values[1]), 6),
            distance_au=round(float(values[2]), 9),
            speed_longitude=round(float(values[3]), 8),
            retrograde=float(values[3]) < 0,
            sign=sign,
            degree_in_sign=round(degree_in_sign, 6),
            house=_house_for_longitude(planet_longitude, cusps),
        )

    if missing_files:
        warnings.append("Missing ephemeris files: " + ", ".join(missing_files))
    if "Moshier fallback" in ephemeris_sources:
        warnings.append(
            "At least one body used the built-in Moshier fallback. Confirm the required .se1 files "
            "are present and SWEPH_PATH points to them."
        )

    house_cusps: list[HouseCusp] = []
    for index, cusp in enumerate(cusps, start=1):
        sign, degree_in_sign = _sign_details(cusp)
        house_cusps.append(
            HouseCusp(
                house=index,
                longitude=round(cusp, 4),
                sign=sign,
                degree_in_sign=round(degree_in_sign, 4),
            )
        )

    source_label = ", ".join(sorted(ephemeris_sources))
    response = HoraryChartResponse(
        metadata=ChartMetadata(
            local_datetime=local_dt.isoformat(),
            utc_datetime=utc_dt.isoformat(),
            timezone_name=request.timezone_name,
            utc_offset_hours=round(utc_offset_hours, 4),
            julian_day_ut=round(julian_day_ut, 8),
            latitude=request.latitude,
            longitude=request.longitude,
            house_system="R",
            ephemeris_path=str(Path(EPHE_PATH)),
            ephemeris_source=source_label,
        ),
        planets=planets,
        house_cusps=house_cusps,
        angles=ChartAngles(
            ascendant=round(_normalize(float(ascmc[0])), 6),
            midheaven=round(_normalize(float(ascmc[1])), 6),
            armc=round(_normalize(float(ascmc[2])), 6),
            vertex=round(_normalize(float(ascmc[3])), 6),
        ),
        warnings=warnings,
    )
    return response.model_dump(mode="json")
