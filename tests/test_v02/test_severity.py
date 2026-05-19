"""Tests for 0.2 configurable severity overrides."""

from __future__ import annotations

from pathlib import Path

from geoassert.runner import run_validation
from tests.conftest import make_contract, write_test_geoparquet


def test_severity_override_downgrades_failing_check(tmp_path: Path) -> None:
    path = write_test_geoparquet(
        tmp_path / "wrong_crs.parquet", crs_authority="EPSG", crs_code=32630
    )
    contract_with_override = make_contract(geometry={"crs": "EPSG:4326"})
    # Manually inject severity override (as would come from YAML)
    contract_with_override.severity["crs.match"] = "warn"

    result = run_validation(path, contract_with_override)
    crs_match = next(r for r in result.checks if r.check == "crs.match")
    assert crs_match.status == "fail"  # status is still fail — severity is separate
    assert crs_match.severity == "warn"  # but severity was overridden


def test_severity_override_does_not_change_status(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "ok.parquet", crs_authority="EPSG", crs_code=4326)
    contract = make_contract(geometry={"crs": "EPSG:4326"})
    contract.severity["crs.match"] = "warn"

    result = run_validation(path, contract)
    crs_match = next(r for r in result.checks if r.check == "crs.match")
    assert crs_match.status == "pass"
    assert crs_match.severity == "warn"


def test_severity_override_applied_only_to_named_check(tmp_path: Path) -> None:
    path = write_test_geoparquet(
        tmp_path / "wrong_crs.parquet", crs_authority="EPSG", crs_code=32630
    )
    contract = make_contract(geometry={"crs": "EPSG:4326"})
    contract.severity["crs.match"] = "warn"

    result = run_validation(path, contract)
    crs_exists = next(r for r in result.checks if r.check == "crs.exists")
    assert crs_exists.severity == "info"  # unchanged — only crs.match was overridden
