"""Tests for warehouse engines (PostGIS, BigQuery, Snowflake) — all mocked."""

from __future__ import annotations

import datetime
import decimal
import struct
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa
import pytest

# ── helpers ────────────────────────────────────────────────────────────────────


def _wkb_point(x: float, y: float) -> bytes:
    return struct.pack("<bIdd", 1, 1, x, y)


# ── PostGIS engine ─────────────────────────────────────────────────────────────


class TestPostgisEngine:
    @patch("geoassert.engines.postgis.HAS_PSYCOPG2", False)
    def test_check_postgis_raises_without_psycopg2(self) -> None:
        from geoassert.engines.postgis import check_postgis

        with pytest.raises(ImportError, match="psycopg2"):
            check_postgis()

    def test_rows_to_arrow_empty(self) -> None:
        from geoassert.engines.postgis import _rows_to_arrow

        table = _rows_to_arrow(["id", "geometry"], [])
        assert table.num_rows == 0
        assert table.num_columns == 2

    def test_rows_to_arrow_type_inference(self) -> None:
        from geoassert.engines.postgis import _rows_to_arrow

        rows = [
            (
                1,
                1.5,
                True,
                b"\x01\x02",
                "hello",
                decimal.Decimal("3.14"),
                datetime.datetime(2024, 1, 1),
                datetime.date(2024, 1, 1),
            ),
        ]
        colnames = [
            "int_col",
            "float_col",
            "bool_col",
            "bytes_col",
            "str_col",
            "decimal_col",
            "ts_col",
            "date_col",
        ]
        table = _rows_to_arrow(colnames, rows)
        assert table.schema.field("int_col").type == pa.int64()
        assert table.schema.field("float_col").type == pa.float64()
        assert table.schema.field("bool_col").type == pa.bool_()
        assert table.schema.field("bytes_col").type == pa.binary()
        assert table.schema.field("str_col").type == pa.string()
        assert table.schema.field("decimal_col").type == pa.float64()
        assert table.schema.field("ts_col").type == pa.timestamp("us")
        assert table.schema.field("date_col").type == pa.date32()

    def test_rows_to_arrow_null_column(self) -> None:
        from geoassert.engines.postgis import _rows_to_arrow

        rows = [(None,), (None,)]
        table = _rows_to_arrow(["col"], rows)
        assert table.schema.field("col").type == pa.null()


# ── BigQuery engine ────────────────────────────────────────────────────────────


class TestBigQueryEngine:
    @patch("geoassert.engines.bigquery.HAS_BIGQUERY", False)
    def test_check_bigquery_raises_without_package(self) -> None:
        from geoassert.engines.bigquery import check_bigquery

        with pytest.raises(ImportError, match="google-cloud-bigquery"):
            check_bigquery()


# ── Snowflake engine ───────────────────────────────────────────────────────────


class TestSnowflakeEngine:
    @patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", False)
    def test_check_snowflake_raises_without_package(self) -> None:
        from geoassert.engines.snowflake import check_snowflake

        with pytest.raises(ImportError, match="snowflake-connector-python"):
            check_snowflake()

    def test_rows_to_arrow_empty(self) -> None:
        from geoassert.engines.snowflake import _rows_to_arrow

        table = _rows_to_arrow(["id", "geometry"], [], "geometry")
        assert table.num_rows == 0

    def test_rows_to_arrow_geometry_bytes(self) -> None:
        from geoassert.engines.snowflake import _rows_to_arrow

        wkb = _wkb_point(1.0, 2.0)
        rows = [(1, wkb), (2, wkb)]
        table = _rows_to_arrow(["id", "geometry"], rows, "geometry")
        assert table.schema.field("geometry").type == pa.binary()
        assert table.schema.field("id").type == pa.int64()

    def test_rows_to_arrow_null_values(self) -> None:
        from geoassert.engines.snowflake import _rows_to_arrow

        rows = [(None,)]
        table = _rows_to_arrow(["val"], rows, "geometry")
        assert table.schema.field("val").type == pa.null()

    def test_rows_to_arrow_string_fallback(self) -> None:
        from geoassert.engines.snowflake import _rows_to_arrow

        rows = [(object(),), (object(),)]
        table = _rows_to_arrow(["col"], rows, "geometry")
        assert table.schema.field("col").type == pa.string()


# ── DatasetInfo source_type field ──────────────────────────────────────────────


class TestDatasetInfoSourceType:
    def test_default_source_type_is_file(self) -> None:
        from geoassert.engines.pyarrow import DatasetInfo

        info = DatasetInfo(path=Path("/tmp/x.parquet"), schema=pa.schema([]), num_rows=0)
        assert info.source_type == "file"

    def test_custom_source_type(self) -> None:
        from geoassert.engines.pyarrow import DatasetInfo

        info = DatasetInfo(
            path="postgis://public.buildings",
            schema=pa.schema([]),
            num_rows=5,
            source_type="postgis",
        )
        assert info.source_type == "postgis"

    def test_in_memory_table_field(self) -> None:
        from geoassert.engines.pyarrow import DatasetInfo

        tbl = pa.table({"x": [1, 2, 3]})
        info = DatasetInfo(
            path="snowflake://acct/db/s/t",
            schema=tbl.schema,
            num_rows=3,
            source_type="snowflake",
            table=tbl,
        )
        assert info.table is tbl
        assert info.num_rows == 3
