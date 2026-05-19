"""Pydantic models for the geoassert contract schema."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_CRS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*:\S+$")

_KNOWN_GEOMETRY_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
}


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
    # Dimension constraint: "2D" (no Z/M), "3D" (Z required), "any" (no check)
    dimensions: Literal["2D", "3D", "any"] = "any"

    @field_validator("crs")
    @classmethod
    def _validate_crs(cls, v: str | None) -> str | None:
        if v is not None and not _CRS_RE.match(v):
            raise ValueError(f"crs must be in AUTHORITY:CODE format (e.g. EPSG:4326), got {v!r}")
        return v

    @field_validator("type")
    @classmethod
    def _validate_geometry_types(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            unknown = sorted(set(v) - _KNOWN_GEOMETRY_TYPES)
            if unknown:
                raise ValueError(
                    f"Unknown geometry type(s): {unknown}. Allowed: {sorted(_KNOWN_GEOMETRY_TYPES)}"
                )
        return v


class BoundsWithinConfig(BaseModel):
    bbox: list[float] | None = None  # [minx, miny, maxx, maxy]
    country: str | None = None

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return v
        if len(v) != 4:
            raise ValueError(
                f"bbox must have exactly 4 values [minx, miny, maxx, maxy], got {len(v)}"
            )
        minx, miny, maxx, maxy = v
        if minx >= maxx:
            raise ValueError(f"bbox minx ({minx}) must be less than maxx ({maxx})")
        if miny >= maxy:
            raise ValueError(f"bbox miny ({miny}) must be less than maxy ({maxy})")
        return v


class BoundsContract(BaseModel):
    within: BoundsWithinConfig | None = None


class AttributeContract(BaseModel):
    nullable: bool = True
    unique: bool = False
    min: float | None = None
    max: float | None = None
    allowed_values: list[Any] | None = None

    @model_validator(mode="after")
    def _validate_min_max(self) -> AttributeContract:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"min ({self.min}) must be ≤ max ({self.max})")
        return self


class Contract(BaseModel):
    geoassert_version: str = "0.1"
    dataset: str = "unnamed"
    source: SourceConfig = Field(default_factory=SourceConfig)
    geometry: GeometryContract | None = None
    bounds: BoundsContract | None = None
    attributes: dict[str, AttributeContract] = Field(default_factory=dict)
    # Per-check severity overrides: {"crs.match": "warn", "geometry.valid": "error"}
    severity: dict[str, Literal["info", "warn", "error"]] = Field(default_factory=dict)
