"""Tests for partition detection and schema consistency checks."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from geoassert.checks.partitions import PartitionDetectedCheck, PartitionSchemaConsistencyCheck
from geoassert.engines.pyarrow import DatasetInfo


def _dir_info(path: Path) -> DatasetInfo:
    return DatasetInfo(path=path, schema=pa.schema([]), num_rows=0)


def _write_parquet(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def _schema_a() -> pa.Table:
    return pa.table({"id": pa.array([1, 2]), "score": pa.array([1.0, 2.0])})


def _schema_b() -> pa.Table:
    return pa.table({"id": pa.array([3, 4]), "extra": pa.array(["a", "b"])})


# ── PartitionDetectedCheck ─────────────────────────────────────────────────────


def test_partition_detected_hive(tmp_path):
    _write_parquet(tmp_path / "year=2023" / "part.parquet", _schema_a())
    _write_parquet(tmp_path / "year=2024" / "part.parquet", _schema_a())
    result = PartitionDetectedCheck().run(_dir_info(tmp_path))
    assert result.status == "pass"
    assert "year" in str(result.observed)


def test_partition_detected_flat_dir(tmp_path):
    _write_parquet(tmp_path / "file1.parquet", _schema_a())
    _write_parquet(tmp_path / "file2.parquet", _schema_a())
    result = PartitionDetectedCheck().run(_dir_info(tmp_path))
    assert result.status == "warn"


def test_partition_detected_empty_dir(tmp_path):
    result = PartitionDetectedCheck().run(_dir_info(tmp_path))
    assert result.status == "fail"


def test_partition_detected_skip_for_file(tmp_path):
    p = tmp_path / "single.parquet"
    pq.write_table(_schema_a(), p)
    info = DatasetInfo(path=p, schema=pa.schema([]), num_rows=0)
    result = PartitionDetectedCheck().run(info)
    assert result.status == "skip"


# ── PartitionSchemaConsistencyCheck ───────────────────────────────────────────


def test_schema_consistency_pass(tmp_path):
    _write_parquet(tmp_path / "part=a" / "data.parquet", _schema_a())
    _write_parquet(tmp_path / "part=b" / "data.parquet", _schema_a())
    result = PartitionSchemaConsistencyCheck().run(_dir_info(tmp_path))
    assert result.status == "pass"


def test_schema_consistency_fail(tmp_path):
    _write_parquet(tmp_path / "part=a" / "data.parquet", _schema_a())
    _write_parquet(tmp_path / "part=b" / "data.parquet", _schema_b())
    result = PartitionSchemaConsistencyCheck().run(_dir_info(tmp_path))
    assert result.status == "fail"
    assert result.observed  # list of mismatched files


def test_schema_consistency_skip_single_file(tmp_path):
    _write_parquet(tmp_path / "only.parquet", _schema_a())
    result = PartitionSchemaConsistencyCheck().run(_dir_info(tmp_path))
    assert result.status == "skip"


def test_schema_consistency_skip_not_a_dir(tmp_path):
    p = tmp_path / "file.parquet"
    pq.write_table(_schema_a(), p)
    info = DatasetInfo(path=p, schema=pa.schema([]), num_rows=0)
    result = PartitionSchemaConsistencyCheck().run(info)
    assert result.status == "skip"
