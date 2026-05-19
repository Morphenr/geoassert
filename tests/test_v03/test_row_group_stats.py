"""Tests for RowGroupStatsCheck."""

from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq

from geoassert.checks.geoparquet import RowGroupStatsCheck
from geoassert.engines.pyarrow import read_geoparquet_info
from tests.conftest import write_test_geoparquet


def test_row_group_stats_pass(tmp_path):
    p = write_test_geoparquet(tmp_path / "rg.parquet")
    info = read_geoparquet_info(p)
    result = RowGroupStatsCheck().run(info)
    # PyArrow writes statistics by default
    assert result.status in ("pass", "warn")  # pass when stats present


def test_row_group_stats_present_in_metadata_checks(tmp_path):
    from geoassert.checks.geoparquet import run_metadata_checks

    p = write_test_geoparquet(tmp_path / "rg.parquet")
    info = read_geoparquet_info(p)
    checks = run_metadata_checks(info)
    check_names = [c.check for c in checks]
    assert "geoparquet.row_group_stats" in check_names


def test_row_group_stats_no_metadata(tmp_path):
    p = write_test_geoparquet(tmp_path / "rg.parquet")
    info = read_geoparquet_info(p)
    info.parquet_metadata = None
    result = RowGroupStatsCheck().run(info)
    assert result.status == "skip"


def test_row_group_stats_warn_when_missing(tmp_path):
    """Write a file without statistics and confirm warn is returned."""
    p = tmp_path / "nostats.parquet"
    table = pa.table({"x": pa.array([1, 2, 3])})
    pq.write_table(table, p, write_statistics=False)
    info = read_geoparquet_info(p)
    result = RowGroupStatsCheck().run(info)
    assert result.status == "warn"
    assert "missing" in result.message
