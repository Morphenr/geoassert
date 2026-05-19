"""Tests for 0.2 sampling support."""

from __future__ import annotations

from pathlib import Path

from geoassert.engines.pyarrow import read_geoparquet_info, read_table_for_check
from tests.conftest import write_test_geoparquet


def test_read_table_for_check_returns_full_table_without_sample(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "ok.parquet", n_rows=10)
    info = read_geoparquet_info(path)
    assert info.sample is None
    table = read_table_for_check(info, columns=["geometry"])
    assert len(table) == 10


def test_read_table_for_check_samples_when_sample_set(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "ok.parquet", n_rows=100)
    info = read_geoparquet_info(path)
    info.sample = 10
    table = read_table_for_check(info, columns=["geometry"])
    assert len(table) == 10


def test_read_table_for_check_returns_full_table_when_sample_ge_nrows(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "ok.parquet", n_rows=5)
    info = read_geoparquet_info(path)
    info.sample = 1000
    table = read_table_for_check(info, columns=["geometry"])
    assert len(table) == 5


def test_datasetinfo_sample_defaults_to_none(tmp_path: Path) -> None:
    info = read_geoparquet_info(write_test_geoparquet(tmp_path / "ok.parquet"))
    assert info.sample is None


def test_attribute_check_respects_sample(tmp_path: Path) -> None:
    from geoassert.checks.attributes import AttributeNullCheck

    path = write_test_geoparquet(
        tmp_path / "ok.parquet",
        n_rows=50,
        extra_columns={"score": list(range(50))},
    )
    info = read_geoparquet_info(path)
    info.sample = 5
    result = AttributeNullCheck("score", nullable=False).run(info)
    assert result.status == "pass"
