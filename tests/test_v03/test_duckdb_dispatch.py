"""Attribute checks dispatching to DuckDB when engine='duckdb'."""

from __future__ import annotations

import pytest

duckdb = pytest.importorskip("duckdb")

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from geoassert.checks.attributes import (
    AttributeNullCheck,
    AttributeRangeCheck,
    AttributeUniqueCheck,
)
from geoassert.engines.pyarrow import DatasetInfo


def _make_info(path: Path, engine: str = "duckdb") -> DatasetInfo:
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(path)
    return DatasetInfo(
        path=path,
        schema=pf.schema_arrow,
        num_rows=pf.metadata.num_rows,
        engine=engine,
    )


def _write_table(tmp_path: Path, table: pa.Table) -> Path:
    p = tmp_path / "data.parquet"
    pq.write_table(table, p)
    return p


# ── AttributeNullCheck ─────────────────────────────────────────────────────────


def test_null_check_pass_duckdb(tmp_path):
    p = _write_table(tmp_path, pa.table({"score": pa.array([1.0, 2.0, 3.0])}))
    result = AttributeNullCheck("score", nullable=False).run(_make_info(p))
    assert result.status == "pass"


def test_null_check_fail_duckdb(tmp_path):
    p = _write_table(tmp_path, pa.table({"score": pa.array([1.0, None, 3.0])}))
    result = AttributeNullCheck("score", nullable=False).run(_make_info(p))
    assert result.status == "fail"
    assert "1" in result.message


# ── AttributeUniqueCheck ───────────────────────────────────────────────────────


def test_unique_check_pass_duckdb(tmp_path):
    p = _write_table(tmp_path, pa.table({"id": pa.array([1, 2, 3])}))
    result = AttributeUniqueCheck("id").run(_make_info(p))
    assert result.status == "pass"


def test_unique_check_fail_duckdb(tmp_path):
    p = _write_table(tmp_path, pa.table({"id": pa.array([1, 2, 2])}))
    result = AttributeUniqueCheck("id").run(_make_info(p))
    assert result.status == "fail"


# ── AttributeRangeCheck ────────────────────────────────────────────────────────


def test_range_check_pass_duckdb(tmp_path):
    p = _write_table(tmp_path, pa.table({"score": pa.array([1.0, 2.0, 3.0])}))
    result = AttributeRangeCheck("score", min_val=0.0, max_val=10.0).run(_make_info(p))
    assert result.status == "pass"


def test_range_check_fail_duckdb(tmp_path):
    p = _write_table(tmp_path, pa.table({"score": pa.array([1.0, 2.0, 99.0])}))
    result = AttributeRangeCheck("score", min_val=0.0, max_val=10.0).run(_make_info(p))
    assert result.status == "fail"
    assert "99" in result.message


def test_range_all_null_skip_duckdb(tmp_path):
    p = _write_table(tmp_path, pa.table({"score": pa.array([None, None], type=pa.float64())}))
    result = AttributeRangeCheck("score", min_val=0.0, max_val=10.0).run(_make_info(p))
    assert result.status == "skip"
