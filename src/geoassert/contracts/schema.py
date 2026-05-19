"""Pydantic models for the geoassert contract schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    path: str | None = None
    format: str = "geoparquet"


class SeverityConfig(BaseModel):
    enabled: bool = True
    severity: Literal["info", "warn", "error"] = "error"


class GeometryContract(BaseModel):
    column: str = "geometry"
    type: list[str] | None = None
    crs: str | None = None
    valid: bool | SeverityConfig = True
    allow_empty: bool = False
    allow_null: bool = False
    allow_equivalent_crs: bool = False


class BoundsWithinConfig(BaseModel):
    bbox: list[float] | None = None  # [minx, miny, maxx, maxy]
    country: str | None = None


class BoundsContract(BaseModel):
    within: BoundsWithinConfig | None = None


class AttributeContract(BaseModel):
    nullable: bool = True
    unique: bool = False
    min: float | None = None
    max: float | None = None
    allowed_values: list[Any] | None = None


class Contract(BaseModel):
    geoassert_version: str = "0.1"
    dataset: str = "unnamed"
    source: SourceConfig = Field(default_factory=SourceConfig)
    geometry: GeometryContract | None = None
    bounds: BoundsContract | None = None
    attributes: dict[str, AttributeContract] = Field(default_factory=dict)
