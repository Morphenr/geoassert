"""Tests for attribute checks — pass, fail, and skip paths."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa

from geoassert.checks.attributes import (
    AttributeExistsCheck,
    AttributeNullCheck,
    AttributeRangeCheck,
    AttributeUniqueCheck,
    run_attribute_checks,
)
from geoassert.engines.pyarrow import read_geoparquet_info

from tests.conftest import make_contract, write_test_geoparquet


# ── AttributeExistsCheck ──────────────────────────────────────────────────────


def test_attribute_exists_passes_when_column_present(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", extra_columns={"name": ["a", "b", "c"]})
    )
    result = AttributeExistsCheck("name").run(info)
    assert result.status == "pass"


def test_attribute_exists_fails_when_column_missing(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = AttributeExistsCheck("missing_col").run(info)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.expected == "missing_col"
    assert isinstance(result.observed, list)


# ── AttributeNullCheck ────────────────────────────────────────────────────────


def test_attribute_null_check_passes_when_no_nulls(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", extra_columns={"score": [1, 2, 3]})
    )
    result = AttributeNullCheck("score", nullable=False).run(info)
    assert result.status == "pass"


def test_attribute_null_check_passes_when_nullable_true(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", extra_columns={"score": [1, None, 3]})
    )
    result = AttributeNullCheck("score", nullable=True).run(info)
    assert result.status == "pass"


def test_attribute_null_check_fails_when_nulls_present(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "nulls.parquet", extra_columns={"score": [1, None, 3]})
    )
    result = AttributeNullCheck("score", nullable=False).run(info)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.affected_rows == 1
    assert result.suggestion is not None


def test_attribute_null_check_skips_when_column_missing(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = AttributeNullCheck("no_such_col", nullable=False).run(info)
    assert result.status == "skip"


# ── AttributeUniqueCheck ──────────────────────────────────────────────────────


def test_attribute_unique_passes_when_all_unique(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", extra_columns={"id": [1, 2, 3]})
    )
    result = AttributeUniqueCheck("id").run(info)
    assert result.status == "pass"


def test_attribute_unique_fails_when_duplicates_present(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "dupes.parquet", extra_columns={"id": [1, 1, 2]})
    )
    result = AttributeUniqueCheck("id").run(info)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.affected_rows == 1
    assert result.suggestion is not None


def test_attribute_unique_skips_when_column_missing(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = AttributeUniqueCheck("no_such_col").run(info)
    assert result.status == "skip"


# ── AttributeRangeCheck ───────────────────────────────────────────────────────


def test_attribute_range_passes_when_values_in_range(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "ok.parquet", extra_columns={"value": [1.0, 5.0, 9.0]})
    )
    result = AttributeRangeCheck("value", min_val=0.0, max_val=10.0).run(info)
    assert result.status == "pass"


def test_attribute_range_fails_when_min_violated(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "low.parquet", extra_columns={"value": [-5.0, 5.0, 9.0]})
    )
    result = AttributeRangeCheck("value", min_val=0.0, max_val=10.0).run(info)
    assert result.status == "fail"
    assert result.severity == "error"
    assert result.observed is not None
    assert result.observed["min"] == -5.0
    assert "min" in result.message


def test_attribute_range_fails_when_max_violated(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(tmp_path / "high.parquet", extra_columns={"value": [1.0, 5.0, 20.0]})
    )
    result = AttributeRangeCheck("value", min_val=0.0, max_val=10.0).run(info)
    assert result.status == "fail"
    assert result.observed["max"] == 20.0


def test_attribute_range_skips_when_column_missing(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    result = AttributeRangeCheck("no_such_col", min_val=0.0, max_val=10.0).run(info)
    assert result.status == "skip"


def test_attribute_range_skips_when_all_null(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(
            tmp_path / "all_null.parquet",
            extra_columns={"value": pa.array([None, None, None], type=pa.float64())},
        )
    )
    result = AttributeRangeCheck("value", min_val=0.0, max_val=10.0).run(info)
    assert result.status == "skip"


# ── run_attribute_checks (integration) ────────────────────────────────────────


def test_run_attribute_checks_returns_empty_without_contract(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    assert run_attribute_checks(info) == []


def test_run_attribute_checks_all_pass_for_valid_data(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(
            tmp_path / "ok.parquet",
            extra_columns={"id": [1, 2, 3], "score": [0.5, 0.7, 0.9]},
        )
    )
    contract = make_contract(
        attributes={
            "id": {"nullable": False, "unique": True},
            "score": {"nullable": False, "min": 0.0, "max": 1.0},
        }
    )
    results = run_attribute_checks(info, contract)
    failed = [r for r in results if r.status == "fail"]
    assert failed == [], f"Unexpected failures: {[r.check for r in failed]}"


def test_run_attribute_checks_fail_for_missing_column(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    contract = make_contract(attributes={"required_col": {"nullable": False}})
    statuses = {r.check: r.status for r in run_attribute_checks(info, contract)}
    assert statuses["attributes.required_col.exists"] == "fail"
    assert statuses["attributes.required_col.nullable"] == "skip"


def test_run_attribute_checks_fail_for_null_violation(tmp_path: Path) -> None:
    info = read_geoparquet_info(
        write_test_geoparquet(
            tmp_path / "nulls.parquet", extra_columns={"name": ["a", None, "c"]}
        )
    )
    contract = make_contract(attributes={"name": {"nullable": False}})
    statuses = {r.check: r.status for r in run_attribute_checks(info, contract)}
    assert statuses["attributes.name.exists"] == "pass"
    assert statuses["attributes.name.nullable"] == "fail"
