"""Tests for the DuckDB engine helper functions."""

from __future__ import annotations

import pytest

duckdb = pytest.importorskip("duckdb")

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def _write_scores(tmp_path: Path) -> Path:
    p = tmp_path / "scores.parquet"
    table = pa.table(
        {
            "id": pa.array([1, 2, 2, 3, None], type=pa.int64()),
            "score": pa.array([10.0, 20.0, 20.0, None, 5.0], type=pa.float64()),
        }
    )
    pq.write_table(table, p)
    return p


def test_count_nulls(tmp_path):
    from geoassert.engines.duckdb import count_nulls

    p = _write_scores(tmp_path)
    assert count_nulls(p, "id") == 1
    assert count_nulls(p, "score") == 1


def test_count_non_null(tmp_path):
    from geoassert.engines.duckdb import count_non_null

    p = _write_scores(tmp_path)
    assert count_non_null(p, "id") == 4


def test_count_distinct(tmp_path):
    from geoassert.engines.duckdb import count_distinct

    p = _write_scores(tmp_path)
    # ids: 1, 2, 3 (NULL excluded) → 3 distinct
    assert count_distinct(p, "id") == 3


def test_count_total(tmp_path):
    from geoassert.engines.duckdb import count_total

    p = _write_scores(tmp_path)
    assert count_total(p) == 5


def test_get_min_max(tmp_path):
    from geoassert.engines.duckdb import get_min_max

    p = _write_scores(tmp_path)
    mn, mx = get_min_max(p, "score")
    assert mn == pytest.approx(5.0)
    assert mx == pytest.approx(20.0)
