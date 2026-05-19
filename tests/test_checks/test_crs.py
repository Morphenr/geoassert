"""Tests for CRS checks — pass, fail, and skip paths."""

from __future__ import annotations

from pathlib import Path

from geoassert.checks.crs import CRSExistsCheck, CRSMatchCheck, run_crs_checks
from geoassert.engines.pyarrow import read_geoparquet_info
from tests.conftest import make_contract, write_test_geoparquet

# ── CRSExistsCheck ────────────────────────────────────────────────────────────


def test_crs_exists_passes_when_crs_present(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", crs_authority="EPSG", crs_code=4326)
    )
    assert CRSExistsCheck().run(info).status == "pass"


def test_crs_exists_warns_when_no_geo_metadata(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "no_meta.parquet", include_geo_meta=False)
    )
    result = CRSExistsCheck().run(info)
    assert result.status == "warn"
    assert result.suggestion is not None


def test_crs_exists_observed_value_in_message(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", crs_authority="EPSG", crs_code=27700)
    )
    result = CRSExistsCheck().run(info)
    assert result.status == "pass"
    assert "EPSG:27700" in result.message


# ── CRSMatchCheck ─────────────────────────────────────────────────────────────


def test_crs_match_passes_when_crs_matches(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", crs_authority="EPSG", crs_code=4326)
    )
    contract = make_contract(geometry={"crs": "EPSG:4326"})
    result = CRSMatchCheck().run(info, contract)
    assert result.status == "pass"


def test_crs_match_fails_when_crs_mismatches(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "wrong_crs.parquet", crs_authority="EPSG", crs_code=32630)
    )
    contract = make_contract(geometry={"crs": "EPSG:4326"})
    result = CRSMatchCheck().run(info, contract)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.expected == "EPSG:4326"
    assert result.observed == "EPSG:32630"
    assert result.why_it_matters is not None
    assert result.suggestion is not None


def test_crs_match_fails_when_data_has_no_crs(tmp_path: Path) -> None:
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / "no_crs.parquet"
    table = pa.table({"geometry": pa.array([b"\x00"])})
    geo_meta = {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {"geometry": {"encoding": "WKB"}},
    }
    table = table.replace_schema_metadata({b"geo": json.dumps(geo_meta).encode()})
    pq.write_table(table, path)

    contract = make_contract(geometry={"crs": "EPSG:4326"})
    result = CRSMatchCheck().run(read_geoparquet_info(path), contract)
    assert result.status == "fail"
    assert result.observed is None


def test_crs_match_skips_when_no_contract_crs(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    contract = make_contract(geometry={"column": "geometry"})  # no crs constraint
    result = CRSMatchCheck().run(info, contract)
    assert result.status == "skip"


def test_crs_match_skips_when_no_geometry_contract(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = CRSMatchCheck().run(info, make_contract())
    assert result.status == "skip"


# ── run_crs_checks (integration) ──────────────────────────────────────────────


def test_run_crs_checks_returns_three_results(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    results = run_crs_checks(info)
    assert len(results) == 3


def test_run_crs_checks_all_pass_or_warn_for_matching_contract(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", crs_authority="EPSG", crs_code=4326)
    )
    contract = make_contract(geometry={"crs": "EPSG:4326"})
    results = run_crs_checks(info, contract)
    # CRSAxisOrderCheck warns for EPSG:4326 (lat-first), so expect pass or warn only
    assert all(r.status in ("pass", "warn") for r in results)


def test_run_crs_checks_fail_for_wrong_crs(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", crs_authority="EPSG", crs_code=27700)
    )
    contract = make_contract(geometry={"crs": "EPSG:4326"})
    statuses = {r.check: r.status for r in run_crs_checks(info, contract)}
    assert statuses["crs.exists"] == "pass"
    assert statuses["crs.match"] == "fail"
