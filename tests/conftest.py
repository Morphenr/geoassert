"""Shared test fixtures and parquet-building helpers."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from geoassert.contracts.schema import (
    Contract,
)

# ── WKB helpers ───────────────────────────────────────────────────────────────


def _wkb_point(x: float, y: float) -> bytes:
    """Minimal WKB for a 2D point (little-endian)."""
    return struct.pack("<bIdd", 1, 1, x, y)


def _wkb_polygon_box(x0: float, y0: float, x1: float, y1: float) -> bytes:
    """WKB for a simple axis-aligned Polygon."""
    ring = [
        (x0, y0),
        (x1, y0),
        (x1, y1),
        (x0, y1),
        (x0, y0),
    ]
    n_points = len(ring)
    header = struct.pack("<bII", 1, 3, 1)  # little-endian, WKBPolygon, 1 ring
    ring_header = struct.pack("<I", n_points)
    coords = b"".join(struct.pack("<dd", x, y) for x, y in ring)
    return header + ring_header + coords


# ── geo metadata builder ───────────────────────────────────────────────────────


def _make_geo_metadata(
    column: str = "geometry",
    crs_authority: str = "EPSG",
    crs_code: int = 4326,
    geometry_types: list[str] | None = None,
    bbox: list[float] | None = None,
    encoding: str = "WKB",
) -> dict[str, Any]:
    crs_json: dict[str, Any] = {
        "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
        "type": "GeographicCRS",
        "name": f"{crs_authority}:{crs_code}",
        "id": {"authority": crs_authority, "code": crs_code},
    }
    col_meta: dict[str, Any] = {
        "encoding": encoding,
        "crs": crs_json,
        "geometry_types": geometry_types if geometry_types is not None else ["Point"],
    }
    if bbox is not None:
        col_meta["bbox"] = bbox
    return {
        "version": "1.1.0",
        "primary_column": column,
        "columns": {column: col_meta},
    }


# ── main parquet writer ────────────────────────────────────────────────────────


def write_test_geoparquet(
    path: Path,
    *,
    n_rows: int = 3,
    include_geo_meta: bool = True,
    column: str = "geometry",
    extra_columns: dict[str, Any] | None = None,
    bbox: list[float] | None = None,
    crs_authority: str = "EPSG",
    crs_code: int = 4326,
    geometry_types: list[str] | None = None,
    encoding: str = "WKB",
    wkb_factory: Any = None,
) -> Path:
    """Write a minimal GeoParquet file for testing.

    Parameters
    ----------
    wkb_factory:
        Optional callable(index) -> bytes to produce custom WKB per row.
        Defaults to simple WKB points.
    """
    factory = wkb_factory or (lambda i: _wkb_point(float(i), float(i)))
    wkb_data = [factory(i) for i in range(n_rows)]
    arrays: dict[str, pa.Array] = {column: pa.array(wkb_data, type=pa.binary())}
    if extra_columns:
        for col_name, values in extra_columns.items():
            arrays[col_name] = pa.array(values)

    table = pa.table(arrays)

    if include_geo_meta:
        geo_meta = _make_geo_metadata(
            column=column,
            crs_authority=crs_authority,
            crs_code=crs_code,
            geometry_types=geometry_types,
            bbox=bbox,
            encoding=encoding,
        )
        existing_meta = table.schema.metadata or {}
        table = table.replace_schema_metadata(
            {**existing_meta, b"geo": json.dumps(geo_meta).encode()}
        )

    pq.write_table(table, path)
    return path


# ── contract builder ───────────────────────────────────────────────────────────


def make_contract(
    dataset: str = "test",
    geometry: dict[str, Any] | None = None,
    bounds: dict[str, Any] | None = None,
    attributes: dict[str, Any] | None = None,
) -> Contract:
    """Build a Contract object without going through YAML."""
    return Contract.model_validate(
        {
            "dataset": dataset,
            "geometry": geometry,
            "bounds": bounds,
            "attributes": attributes or {},
        }
    )


# ── pytest fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_geoparquet(tmp_path: Path) -> Path:
    return write_test_geoparquet(tmp_path / "test.parquet")


@pytest.fixture()
def tmp_geoparquet_no_meta(tmp_path: Path) -> Path:
    return write_test_geoparquet(tmp_path / "no_meta.parquet", include_geo_meta=False)
