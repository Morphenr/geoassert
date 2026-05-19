"""Tests for GeoParquet metadata checks."""

from __future__ import annotations

from pathlib import Path

from geoassert.checks.geoparquet import (
    ColumnInSchemaCheck,
    GeoMetadataCheck,
    run_metadata_checks,
)
from geoassert.engines.pyarrow import read_geoparquet_info
from tests.conftest import write_test_geoparquet


def test_valid_geoparquet_all_pass(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "ok.parquet")
    info = read_geoparquet_info(path)
    results = run_metadata_checks(info)
    statuses = {r.check: r.status for r in results}
    assert statuses["geoparquet.geo_metadata"] == "pass"
    assert statuses["geoparquet.primary_column"] == "pass"
    assert statuses["geoparquet.column_in_schema"] == "pass"
    assert statuses["geoparquet.encoding"] == "pass"
    assert statuses["geoparquet.crs_parseable"] == "pass"


def test_missing_geo_metadata_fails(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "no_meta.parquet", include_geo_meta=False)
    info = read_geoparquet_info(path)
    result = GeoMetadataCheck().run(info)
    assert result.status == "fail"
    assert result.severity == "error"


def test_column_not_in_schema_fails(tmp_path: Path) -> None:
    """Geo metadata declares a column that doesn't exist in the Parquet schema."""
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / "mismatch.parquet"
    table = pa.table({"geometry": pa.array([b"\x01\x01\x00\x00\x00" + b"\x00" * 16])})
    geo_meta = {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {
            "geometry": {"encoding": "WKB", "crs": {"id": {"authority": "EPSG", "code": 4326}}},
            "geom2": {"encoding": "WKB"},  # declared but missing from schema
        },
    }
    table = table.replace_schema_metadata({b"geo": json.dumps(geo_meta).encode()})
    pq.write_table(table, path)

    info = read_geoparquet_info(path)
    result = ColumnInSchemaCheck().run(info)
    assert result.status == "fail"
    assert "geom2" in str(result.observed)


def test_no_rows_file(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "empty.parquet", n_rows=0)
    info = read_geoparquet_info(path)
    assert info.num_rows == 0
    results = run_metadata_checks(info)
    assert all(r.status in ("pass", "warn", "skip") for r in results)
