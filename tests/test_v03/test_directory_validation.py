"""Tests for validate_directory()."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from geoassert.runner import validate_directory
from tests.conftest import make_contract, write_test_geoparquet


def _write_geoparquet(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_test_geoparquet(path)


def test_validate_directory_returns_results(tmp_path):
    _write_geoparquet(tmp_path / "a.parquet")
    _write_geoparquet(tmp_path / "b.parquet")
    contract = make_contract()
    results = validate_directory(tmp_path, contract)
    # First result is the directory/partition-level summary
    assert len(results) == 3
    assert results[0].stats.get("type") == "directory"


def test_validate_directory_empty_returns_empty(tmp_path):
    contract = make_contract()
    results = validate_directory(tmp_path, contract)
    assert results == []


def test_validate_directory_hive_partitions(tmp_path):
    _write_geoparquet(tmp_path / "year=2023" / "part.parquet")
    _write_geoparquet(tmp_path / "year=2024" / "part.parquet")
    contract = make_contract()
    results = validate_directory(tmp_path, contract)
    dir_result = results[0]
    # PartitionDetectedCheck should pass (Hive structure found)
    partition_checks = [c for c in dir_result.checks if c.check == "partitions.detected"]
    assert partition_checks[0].status == "pass"


def test_validate_directory_schema_mismatch_fails(tmp_path):
    _write_geoparquet(tmp_path / "part=a" / "data.parquet")
    # Write a file with a different schema (no geo metadata, different columns)
    bad = tmp_path / "part=b" / "data.parquet"
    bad.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({"x": pa.array([1, 2, 3])}), bad)
    contract = make_contract()
    results = validate_directory(tmp_path, contract)
    dir_result = results[0]
    consistency_checks = [
        c for c in dir_result.checks if c.check == "partitions.schema_consistency"
    ]
    assert consistency_checks[0].status == "fail"


def test_validate_directory_all_pass(tmp_path):
    _write_geoparquet(tmp_path / "f1.parquet")
    _write_geoparquet(tmp_path / "f2.parquet")
    contract = make_contract()
    results = validate_directory(tmp_path, contract)
    file_results = results[1:]
    assert all(r.passed for r in file_results)
