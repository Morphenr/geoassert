"""PyArrow-based dataset reader — no extras required."""

from __future__ import annotations

import contextlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from geoassert.exceptions import DataReadError


@dataclass
class DatasetInfo:
    path: Path
    schema: pa.Schema
    num_rows: int
    metadata: dict[bytes, bytes] = field(default_factory=dict)
    geo_metadata: dict[str, Any] | None = None
    parquet_metadata: Any | None = None  # pq.FileMetaData
    sample: int | None = None  # row limit for row-level checks


def read_geoparquet_info(path: Path | str) -> DatasetInfo:
    """Read Parquet file metadata without loading all row data."""
    path = Path(path)
    try:
        parquet_file = pq.ParquetFile(path)
    except Exception as exc:
        raise DataReadError(f"Cannot open {path}: {exc}") from exc

    parquet_meta = parquet_file.metadata
    schema = parquet_file.schema_arrow
    raw_meta: dict[bytes, bytes] = schema.metadata or {}

    geo_metadata: dict[str, Any] | None = None
    if b"geo" in raw_meta:
        with contextlib.suppress(json.JSONDecodeError):
            geo_metadata = json.loads(raw_meta[b"geo"])

    return DatasetInfo(
        path=path,
        schema=schema,
        num_rows=parquet_meta.num_rows,
        metadata=raw_meta,
        geo_metadata=geo_metadata,
        parquet_metadata=parquet_meta,
    )


def read_table(path: Path | str, columns: list[str] | None = None) -> pa.Table:
    """Read the full table (or a column subset) into memory."""
    path = Path(path)
    try:
        return pq.read_table(path, columns=columns)
    except Exception as exc:
        raise DataReadError(f"Cannot read {path}: {exc}") from exc


def read_table_for_check(info: DatasetInfo, columns: list[str] | None = None) -> pa.Table:
    """Read a table for a check, honouring the sample size set on DatasetInfo."""
    table = read_table(info.path, columns=columns)
    if info.sample is not None and len(table) > info.sample:
        indices = sorted(random.sample(range(len(table)), info.sample))
        return table.take(indices)
    return table
