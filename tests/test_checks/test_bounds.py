"""Tests for bounds checks — pass, fail, warn, and skip paths."""

from __future__ import annotations

from pathlib import Path

from geoassert.checks.bounds import BoundsAvailableCheck, BoundsWithinCheck, run_bounds_checks
from geoassert.engines.pyarrow import read_geoparquet_info
from tests.conftest import make_contract, write_test_geoparquet

# ── BoundsAvailableCheck ──────────────────────────────────────────────────────


def test_bounds_available_passes_when_bbox_present(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", bbox=[-1.0, -1.0, 1.0, 1.0])
    )
    result = BoundsAvailableCheck().run(info)
    assert result.status == "pass"
    assert result.severity == "info"


def test_bounds_available_warns_when_no_bbox(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = BoundsAvailableCheck().run(info)
    assert result.status == "warn"
    assert result.suggestion is not None


def test_bounds_available_warns_when_no_geo_metadata(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "no_meta.parquet", include_geo_meta=False)
    )
    result = BoundsAvailableCheck().run(info)
    assert result.status == "warn"


# ── BoundsWithinCheck ─────────────────────────────────────────────────────────


def test_bounds_within_passes_when_data_inside_contract(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", bbox=[-1.0, -1.0, 1.0, 1.0])
    )
    contract = make_contract(bounds={"within": {"bbox": [-10.0, -10.0, 10.0, 10.0]}})
    result = BoundsWithinCheck().run(info, contract)
    assert result.status == "pass"


def test_bounds_within_fails_when_data_exceeds_contract(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "out.parquet", bbox=[-20.0, -20.0, 20.0, 20.0])
    )
    expected_bbox = [-10.0, -10.0, 10.0, 10.0]
    contract = make_contract(bounds={"within": {"bbox": expected_bbox}})
    result = BoundsWithinCheck().run(info, contract)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.expected == expected_bbox
    assert result.observed == [-20.0, -20.0, 20.0, 20.0]
    assert result.why_it_matters is not None
    assert result.suggestion is not None


def test_bounds_within_warns_when_no_dataset_bbox(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    contract = make_contract(bounds={"within": {"bbox": [-10.0, -10.0, 10.0, 10.0]}})
    result = BoundsWithinCheck().run(info, contract)
    assert result.status == "warn"
    assert result.suggestion is not None


def test_bounds_within_skips_when_no_contract(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = BoundsWithinCheck().run(info, make_contract())
    assert result.status == "skip"


def test_bounds_within_skips_when_no_bounds_section(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = BoundsWithinCheck().run(info)
    assert result.status == "skip"


# ── run_bounds_checks (integration) ───────────────────────────────────────────


def test_run_bounds_checks_returns_expected_results(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    results = run_bounds_checks(info)
    check_names = [r.check for r in results]
    assert "bounds.available" in check_names
    assert "bounds.within" in check_names
    assert "bounds.bbox_consistency" in check_names


def test_run_bounds_checks_all_pass_when_within_contract(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", bbox=[0.0, 0.0, 5.0, 5.0])
    )
    contract = make_contract(bounds={"within": {"bbox": [-10.0, -10.0, 10.0, 10.0]}})
    statuses = {r.check: r.status for r in run_bounds_checks(info, contract)}
    assert statuses["bounds.available"] == "pass"
    assert statuses["bounds.within"] == "pass"


def test_run_bounds_checks_fail_for_exceeding_bounds(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "out.parquet", bbox=[-50.0, -50.0, 50.0, 50.0])
    )
    contract = make_contract(bounds={"within": {"bbox": [-10.0, -10.0, 10.0, 10.0]}})
    statuses = {r.check: r.status for r in run_bounds_checks(info, contract)}
    assert statuses["bounds.available"] == "pass"
    assert statuses["bounds.within"] == "fail"
