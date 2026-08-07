"""Pydantic request and response models for the Orora ephemeris engine."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HoraryChartRequest(BaseModel):
    """Input for a Regiomontanus horary chart calculation."""

    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=1800, le=2399)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    second: int = Field(default=0, ge=0, le=59)
    timezone_name: str | None = Field(
        default=None,
        description="IANA timezone name, for example America/New_York.",
    )
    timezone_offset: float | None = Field(
        default=None,
        ge=-14,
        le=14,
        description="Fixed UTC offset fallback. Prefer timezone_name for DST accuracy.",
    )
    fold: Literal[0, 1] = Field(
        default=0,
        description="Selects the first or second occurrence of an ambiguous DST time.",
    )
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    house_system: Literal["R"] = "R"

    @model_validator(mode="after")
    def validate_timezone(self) -> "HoraryChartRequest":
        if self.timezone_name is None and self.timezone_offset is None:
            raise ValueError("Provide timezone_name or timezone_offset")
        if self.timezone_name is not None and self.timezone_offset is not None:
            raise ValueError("Provide only one of timezone_name or timezone_offset")
        return self


class PlanetPosition(BaseModel):
    name: str
    longitude: float
    latitude: float
    distance_au: float
    speed_longitude: float
    retrograde: bool
    sign: str
    degree_in_sign: float
    house: int


class HouseCusp(BaseModel):
    house: int = Field(ge=1, le=12)
    longitude: float
    sign: str
    degree_in_sign: float


class ChartAngles(BaseModel):
    ascendant: float
    midheaven: float
    armc: float
    vertex: float


class ChartMetadata(BaseModel):
    local_datetime: str
    utc_datetime: str
    timezone_name: str | None
    utc_offset_hours: float
    julian_day_ut: float
    latitude: float
    longitude: float
    house_system: Literal["R"]
    ephemeris_path: str
    ephemeris_source: str


class HoraryChartResponse(BaseModel):
    metadata: ChartMetadata
    planets: dict[str, PlanetPosition]
    house_cusps: list[HouseCusp] = Field(min_length=12, max_length=12)
    angles: ChartAngles
    warnings: list[str] = Field(default_factory=list)
