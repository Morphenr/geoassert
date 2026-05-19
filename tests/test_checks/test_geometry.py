"""Tests for geometry checks — pass, fail, warn, and skip paths.

All shapely-dependent tests are skipped when shapely is not installed.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from geoassert.checks.geometry import (
    GeometryColumnExistsCheck,
    GeometryEmptyCheck,
    GeometryTypeCheck,
    GeometryValidCheck,
    run_geometry_checks,
)
from geoassert.engines.pyarrow import read_geoparquet_info
from tests.conftest import make_contract, write_test_geoparquet

shapely = pytest.importorskip("shapely")


# ── WKB helpers ───────────────────────────────────────────────────────────────


def _wkb_invalid_polygon() -> bytes:
    """WKB for a self-intersecting (bowtie) polygon — invalid geometry."""
    ring = [(0.0, 0.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0), (0.0, 0.0)]
    header = struct.pack("<bII", 1, 3, 1)
    ring_header = struct.pack("<I", len(ring))
    coords = b"".join(struct.pack("<dd", x, y) for x, y in ring)
    return header + ring_header + coords


def _wkb_empty_point() -> bytes:
    """WKB for POINT EMPTY via shapely."""
    import shapely.wkt

    return shapely.wkt.loads("POINT EMPTY").wkb


def _write_custom_wkb_parquet(path: Path, wkb_rows: list[bytes]) -> Path:
    """Write a GeoParquet file with explicit WKB bytes per row."""
    import json

    table = pa.table({"geometry": pa.array(wkb_rows, type=pa.binary())})
    geo_meta = {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {
            "geometry": {
                "encoding": "WKB",
                "crs": {
                    "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
                    "type": "GeographicCRS",
                    "name": "EPSG:4326",
                    "id": {"authority": "EPSG", "code": 4326},
                },
                "geometry_types": ["Point"],
            }
        },
    }
    table = table.replace_schema_metadata({b"geo": json.dumps(geo_meta).encode()})
    pq.write_table(table, path)
    return path


# ── GeometryColumnExistsCheck ─────────────────────────────────────────────────


def test_geometry_column_exists_passes_for_default_column(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = GeometryColumnExistsCheck().run(info)
    assert result.status == "pass"


def test_geometry_column_exists_fails_for_wrong_column_name(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    contract = make_contract(geometry={"column": "geom"})
    result = GeometryColumnExistsCheck().run(info, contract)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.expected == "geom"
    assert result.suggestion is not None


def test_geometry_column_exists_passes_when_contract_column_present(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet", column="geom"))
    contract = make_contract(geometry={"column": "geom"})
    result = GeometryColumnExistsCheck().run(info, contract)
    assert result.status == "pass"


# ── GeometryValidCheck ────────────────────────────────────────────────────────


def test_geometry_valid_passes_for_valid_geometries(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = GeometryValidCheck().run(info)
    assert result.status == "pass"


def test_geometry_valid_fails_for_invalid_polygon(tmp_path: Path) -> None:
    path = _write_custom_wkb_parquet(
        tmp_path / "invalid.parquet",
        [_wkb_invalid_polygon(), _wkb_invalid_polygon()],
    )
    info = read_geoparquet_info(path)
    result = GeometryValidCheck().run(info)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.affected_rows == 2
    assert result.why_it_matters is not None
    assert result.suggestion is not None


def test_geometry_valid_skips_when_column_missing(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    contract = make_contract(geometry={"column": "no_such_col"})
    result = GeometryValidCheck().run(info, contract)
    assert result.status == "skip"


# ── GeometryEmptyCheck ────────────────────────────────────────────────────────


def test_geometry_empty_passes_when_no_empty_geometries(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = GeometryEmptyCheck().run(info)
    assert result.status == "pass"


def test_geometry_empty_fails_when_empty_not_allowed(tmp_path: Path) -> None:
    path = _write_custom_wkb_parquet(
        tmp_path / "empty_geom.parquet",
        [_wkb_empty_point(), _wkb_empty_point()],
    )
    info = read_geoparquet_info(path)
    contract = make_contract(geometry={"column": "geometry", "allow_empty": False})
    result = GeometryEmptyCheck().run(info, contract)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.affected_rows == 2
    assert result.suggestion is not None


def test_geometry_empty_warns_when_empty_allowed(tmp_path: Path) -> None:
    path = _write_custom_wkb_parquet(
        tmp_path / "empty_geom.parquet",
        [_wkb_empty_point()],
    )
    info = read_geoparquet_info(path)
    contract = make_contract(geometry={"column": "geometry", "allow_empty": True})
    result = GeometryEmptyCheck().run(info, contract)
    assert result.status == "warn"
    assert result.affected_rows == 1


def test_geometry_empty_skips_when_column_missing(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    contract = make_contract(geometry={"column": "no_such_col"})
    result = GeometryEmptyCheck().run(info, contract)
    assert result.status == "skip"


# ── GeometryTypeCheck ─────────────────────────────────────────────────────────


def test_geometry_type_skips_when_no_type_constraint(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    contract = make_contract(geometry={"column": "geometry"})
    result = GeometryTypeCheck().run(info, contract)
    assert result.status == "skip"


def test_geometry_type_passes_when_types_match(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    contract = make_contract(geometry={"column": "geometry", "type": ["Point"]})
    result = GeometryTypeCheck().run(info, contract)
    assert result.status == "pass"


def test_geometry_type_fails_when_unexpected_type_present(tmp_path: Path) -> None:
    import struct as _struct

    def _polygon_wkb(i: int) -> bytes:
        x0, y0, x1, y1 = float(i), float(i), float(i + 1), float(i + 1)
        ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
        header = _struct.pack("<bII", 1, 3, 1)
        ring_header = _struct.pack("<I", len(ring))
        coords = b"".join(_struct.pack("<dd", x, y) for x, y in ring)
        return header + ring_header + coords

    info = read_geoparquet_info(
        write_test_geoparquet(
            tmp_path / "poly.parquet",
            n_rows=2,
            wkb_factory=_polygon_wkb,
        )
    )
    contract = make_contract(geometry={"column": "geometry", "type": ["Point"]})
    result = GeometryTypeCheck().run(info, contract)
    assert result.status == "fail"
    assert result.severity == "error"
    assert "Polygon" in str(result.observed)
    assert result.suggestion is not None


def test_geometry_type_skips_when_no_contract(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = GeometryTypeCheck().run(info)
    assert result.status == "skip"


# ── run_geometry_checks (integration) ─────────────────────────────────────────


def test_run_geometry_checks_returns_four_results(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    results = run_geometry_checks(info)
    assert len(results) == 4


def test_run_geometry_checks_all_pass_for_valid_file(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    contract = make_contract(geometry={"column": "geometry", "type": ["Point"]})
    results = run_geometry_checks(info, contract)
    failed = [r for r in results if r.status == "fail"]
    assert failed == [], f"Unexpected failures: {[r.check for r in failed]}"
