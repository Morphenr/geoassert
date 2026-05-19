"""Shared test fixtures."""
from __future__ import annotations

import json
import struct
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def _wkb_point(x: float, y: float) -> bytes:
    """Minimal WKB for a 2D point (little-endian)."""
    return struct.pack("<bIdd", 1, 1, x, y)


def _make_geo_metadata(
    column: str = "geometry",
    crs_authority: str = "EPSG",
    crs_code: int = 4326,
    geometry_types: list[str] | None = None,
    bbox: list[float] | None = None,
) -> dict:
    crs_json: dict = {
        "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
        "type": "GeographicCRS",
        "name": f"{crs_authority}:{crs_code}",
        "id": {"authority": crs_authority, "code": crs_code},
    }
    col_meta: dict = {
        "encoding": "WKB",
        "crs": crs_json,
        "geometry_types": geometry_types or ["Point"],
    }
    if bbox:
        col_meta["bbox"] = bbox
    return {
        "version": "1.1.0",
        "primary_column": column,
        "columns": {column: col_meta},
    }


def write_test_geoparquet(
    path: Path,
    *,
    n_rows: int = 3,
    include_geo_meta: bool = True,
    column: str = "geometry",
    extra_columns: dict | None = None,
    bbox: list[float] | None = None,
) -> Path:
    """Write a minimal valid GeoParquet file for testing."""
    wkb_data = [_wkb_point(float(i), float(i)) for i in range(n_rows)]
    arrays: dict[str, pa.Array] = {column: pa.array(wkb_data, type=pa.binary())}
    if extra_columns:
        for col_name, values in extra_columns.items():
            arrays[col_name] = pa.array(values)

    table = pa.table(arrays)

    if include_geo_meta:
        geo_meta = _make_geo_metadata(column=column, bbox=bbox)
        existing_meta = table.schema.metadata or {}
        table = table.replace_schema_metadata(
            {**existing_meta, b"geo": json.dumps(geo_meta).encode()}
        )

    pq.write_table(table, path)
    return path


@pytest.fixture()
def tmp_geoparquet(tmp_path: Path) -> Path:
    return write_test_geoparquet(tmp_path / "test.parquet")


@pytest.fixture()
def tmp_geoparquet_no_meta(tmp_path: Path) -> Path:
    return write_test_geoparquet(tmp_path / "no_meta.parquet", include_geo_meta=False)
