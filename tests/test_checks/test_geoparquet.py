"""Tests for GeoParquet metadata checks — pass and fail paths."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from geoassert.checks.geoparquet import (
    ColumnInSchemaCheck,
    CRSParseableCheck,
    EncodingCheck,
    GeoMetadataCheck,
    GeometryTypeMetaCheck,
    PrimaryColumnCheck,
    run_metadata_checks,
)
from geoassert.engines.pyarrow import read_geoparquet_info
from tests.conftest import write_test_geoparquet

# ── GeoMetadataCheck ──────────────────────────────────────────────────────────


def test_geo_metadata_present_passes(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    assert GeoMetadataCheck().run(info).status == "pass"


def test_geo_metadata_absent_fails(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "no_meta.parquet", include_geo_meta=False)
    )
    result = GeoMetadataCheck().run(info)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.suggestion is not None


# ── PrimaryColumnCheck ────────────────────────────────────────────────────────


def test_primary_column_present_passes(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    assert PrimaryColumnCheck().run(info).status == "pass"


def test_primary_column_missing_fails(tmp_path: Path) -> None:
    path = tmp_path / "no_primary.parquet"
    table = pa.table({"geometry": pa.array([b"\x00"])})
    geo_meta = {"version": "1.1.0", "columns": {"geometry": {"encoding": "WKB"}}}
    table = table.replace_schema_metadata({b"geo": json.dumps(geo_meta).encode()})
    pq.write_table(table, path)

    result = PrimaryColumnCheck().run(read_geoparquet_info(path))
    assert result.status == "fail"


def test_primary_column_skipped_without_geo_meta(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "no_meta.parquet", include_geo_meta=False)
    )
    assert PrimaryColumnCheck().run(info).status == "skip"


# ── ColumnInSchemaCheck ───────────────────────────────────────────────────────


def test_column_in_schema_passes(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    assert ColumnInSchemaCheck().run(info).status == "pass"


def test_column_not_in_schema_fails(tmp_path: Path) -> None:
    path = tmp_path / "mismatch.parquet"
    table = pa.table({"geometry": pa.array([b"\x01\x01\x00\x00\x00" + b"\x00" * 16])})
    geo_meta = {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {
            "geometry": {"encoding": "WKB"},
            "geom2": {"encoding": "WKB"},  # declared but absent from schema
        },
    }
    table = table.replace_schema_metadata({b"geo": json.dumps(geo_meta).encode()})
    pq.write_table(table, path)

    result = ColumnInSchemaCheck().run(read_geoparquet_info(path))
    assert result.status == "fail"
    assert "geom2" in str(result.observed)


# ── EncodingCheck ─────────────────────────────────────────────────────────────


def test_encoding_wkb_passes(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    assert EncodingCheck().run(info).status == "pass"


def test_encoding_unknown_warns(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "enc.parquet", encoding="FLATBUF_FUTURE")
    )
    result = EncodingCheck().run(info)
    assert result.status == "warn"
    assert "FLATBUF_FUTURE" in str(result.message)


# ── CRSParseableCheck ─────────────────────────────────────────────────────────


def test_crs_parseable_passes(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    assert CRSParseableCheck().run(info).status == "pass"


def test_crs_missing_warns(tmp_path: Path) -> None:
    path = tmp_path / "no_crs.parquet"
    table = pa.table({"geometry": pa.array([b"\x00"])})
    geo_meta = {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {"geometry": {"encoding": "WKB"}},  # no CRS key
    }
    table = table.replace_schema_metadata({b"geo": json.dumps(geo_meta).encode()})
    pq.write_table(table, path)

    result = CRSParseableCheck().run(read_geoparquet_info(path))
    assert result.status == "warn"


# ── GeometryTypeMetaCheck ─────────────────────────────────────────────────────


def test_geometry_types_present_passes(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", geometry_types=["Point"])
    )
    assert GeometryTypeMetaCheck().run(info).status == "pass"


def test_geometry_types_empty_warns(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "empty_types.parquet", geometry_types=[])
    )
    result = GeometryTypeMetaCheck().run(info)
    assert result.status == "warn"


# ── run_metadata_checks (integration) ────────────────────────────────────────


def test_all_pass_for_valid_file(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    results = run_metadata_checks(info)
    failed = [r for r in results if r.status == "fail"]
    assert failed == [], f"Unexpected failures: {[r.check for r in failed]}"


def test_all_fail_or_skip_for_plain_parquet(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "plain.parquet", include_geo_meta=False)
    )
    statuses = {r.check: r.status for r in run_metadata_checks(info)}
    assert statuses["geoparquet.geo_metadata"] == "fail"
    assert all(
        s in ("skip", "fail") for check, s in statuses.items() if check != "geoparquet.geo_metadata"
    )


def test_empty_file_does_not_raise(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "empty.parquet", n_rows=0))
    results = run_metadata_checks(info)
    assert all(r.status in ("pass", "warn", "skip") for r in results)
