"""Tests for warehouse engines (PostGIS, BigQuery, Snowflake).

Unit tests exercise _rows_to_arrow() directly.
Integration tests mock the full database connection so that
read_postgis_info(), read_bigquery_info(), and read_snowflake_info()
are exercised end-to-end without a real database.
"""

from __future__ import annotations

import datetime
import decimal
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

# ── WKB helpers ────────────────────────────────────────────────────────────────


def _wkb_point(x: float, y: float) -> bytes:
    return struct.pack("<bIdd", 1, 1, x, y)


def _make_description(*names: str) -> list:
    """Cursor description rows — only [0] (column name) is used by engines."""
    return [(name,) for name in names]


# ── PostGIS engine ─────────────────────────────────────────────────────────────


def _make_postgis_mock(
    num_rows: int = 3,
    srid: int = 4326,
    data_rows: list | None = None,
    col_names: list[str] | None = None,
) -> tuple[MagicMock, MagicMock]:
    """Return (mock_psycopg2, mock_conn) wired up for read_postgis_info()."""
    col_names = col_names or ["name", "geometry", "__geom_wkb__"]
    wkb = _wkb_point(1.0, 2.0)
    data_rows = data_rows or [("Building 1", wkb, wkb), ("Building 2", wkb, wkb)][:num_rows]

    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    # fetchone() is called twice: COUNT(*) then SRID lookup
    mock_cur.fetchone.side_effect = [(num_rows,), (srid,)]
    mock_cur.fetchall.return_value = data_rows
    mock_cur.description = _make_description(*col_names)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    mock_psycopg2 = MagicMock()
    mock_psycopg2.connect.return_value = mock_conn
    mock_psycopg2.Error = Exception

    return mock_psycopg2, mock_conn


class TestPostgisEngine:
    # ── guard ──────────────────────────────────────────────────────────────────

    @patch("geoassert.engines.postgis.HAS_PSYCOPG2", False)
    def test_check_postgis_raises_without_psycopg2(self) -> None:
        from geoassert.engines.postgis import check_postgis

        with pytest.raises(ImportError, match="psycopg2"):
            check_postgis()

    # ── read_postgis_info — happy path ─────────────────────────────────────────

    def test_returns_dataset_info_with_correct_metadata(self) -> None:
        mock_psycopg2, _ = _make_postgis_mock(num_rows=2, srid=4326)

        with (
            patch.dict(sys.modules, {"psycopg2": mock_psycopg2}),
            patch("geoassert.engines.postgis.HAS_PSYCOPG2", True),
        ):
            from geoassert.engines.postgis import read_postgis_info

            info = read_postgis_info("postgresql://host/db", "buildings")

        assert info.source_type == "postgis"
        assert info.num_rows == 2
        assert info.path == "postgis://public.buildings"
        assert info.geo_metadata["primary_column"] == "geometry"
        assert info.geo_metadata["columns"]["geometry"]["crs"]["id"]["code"] == 4326

    def test_arrow_table_has_correct_columns(self) -> None:
        mock_psycopg2, _ = _make_postgis_mock(num_rows=2)

        with (
            patch.dict(sys.modules, {"psycopg2": mock_psycopg2}),
            patch("geoassert.engines.postgis.HAS_PSYCOPG2", True),
        ):
            from geoassert.engines.postgis import read_postgis_info

            info = read_postgis_info("postgresql://host/db", "buildings")

        assert "geometry" in info.table.column_names
        assert "name" in info.table.column_names
        assert "__geom_wkb__" not in info.table.column_names

    def test_geometry_column_is_binary(self) -> None:
        mock_psycopg2, _ = _make_postgis_mock(num_rows=2)

        with (
            patch.dict(sys.modules, {"psycopg2": mock_psycopg2}),
            patch("geoassert.engines.postgis.HAS_PSYCOPG2", True),
        ):
            from geoassert.engines.postgis import read_postgis_info

            info = read_postgis_info("postgresql://host/db", "buildings")

        assert info.table.schema.field("geometry").type == pa.binary()

    def test_srid_none_when_not_in_geometry_columns(self) -> None:
        mock_psycopg2, mock_conn = _make_postgis_mock(num_rows=1, srid=4326)
        # Override the SRID fetchone to return None (table not in geometry_columns)
        mock_cur = mock_conn.cursor.return_value
        mock_cur.fetchone.side_effect = [(1,), None]

        with (
            patch.dict(sys.modules, {"psycopg2": mock_psycopg2}),
            patch("geoassert.engines.postgis.HAS_PSYCOPG2", True),
        ):
            from geoassert.engines.postgis import read_postgis_info

            info = read_postgis_info("postgresql://host/db", "buildings")

        # No CRS key when SRID is unknown
        assert "crs" not in info.geo_metadata["columns"]["geometry"]

    def test_custom_schema_used_in_path(self) -> None:
        mock_psycopg2, _ = _make_postgis_mock(num_rows=1)

        with (
            patch.dict(sys.modules, {"psycopg2": mock_psycopg2}),
            patch("geoassert.engines.postgis.HAS_PSYCOPG2", True),
        ):
            from geoassert.engines.postgis import read_postgis_info

            info = read_postgis_info("postgresql://host/db", "buildings", schema="analytics")

        assert info.path == "postgis://analytics.buildings"

    def test_connection_failure_raises_data_read_error(self) -> None:
        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.side_effect = Exception("connection refused")
        mock_psycopg2.Error = Exception

        with (
            patch.dict(sys.modules, {"psycopg2": mock_psycopg2}),
            patch("geoassert.engines.postgis.HAS_PSYCOPG2", True),
        ):
            from geoassert.engines.postgis import read_postgis_info
            from geoassert.exceptions import DataReadError

            with pytest.raises(DataReadError, match="Cannot connect to PostGIS"):
                read_postgis_info("postgresql://host/db", "buildings")

    def test_query_failure_raises_data_read_error(self) -> None:
        mock_psycopg2 = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = Exception("relation does not exist")
        mock_psycopg2.connect.return_value = mock_conn
        mock_psycopg2.Error = Exception
        mock_conn.cursor.return_value = mock_cur

        with (
            patch.dict(sys.modules, {"psycopg2": mock_psycopg2}),
            patch("geoassert.engines.postgis.HAS_PSYCOPG2", True),
        ):
            from geoassert.engines.postgis import read_postgis_info
            from geoassert.exceptions import DataReadError

            with pytest.raises(DataReadError, match="PostGIS query failed"):
                read_postgis_info("postgresql://host/db", "missing_table")

    def test_connection_closed_after_query(self) -> None:
        mock_psycopg2, mock_conn = _make_postgis_mock(num_rows=1)

        with (
            patch.dict(sys.modules, {"psycopg2": mock_psycopg2}),
            patch("geoassert.engines.postgis.HAS_PSYCOPG2", True),
        ):
            from geoassert.engines.postgis import read_postgis_info

            read_postgis_info("postgresql://host/db", "buildings")

        mock_conn.close.assert_called_once()

    def test_connection_closed_even_on_query_error(self) -> None:
        mock_psycopg2 = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = Exception("boom")
        mock_psycopg2.connect.return_value = mock_conn
        mock_psycopg2.Error = Exception
        mock_conn.cursor.return_value = mock_cur

        with (
            patch.dict(sys.modules, {"psycopg2": mock_psycopg2}),
            patch("geoassert.engines.postgis.HAS_PSYCOPG2", True),
        ):
            from geoassert.engines.postgis import read_postgis_info
            from geoassert.exceptions import DataReadError

            with pytest.raises(DataReadError):
                read_postgis_info("postgresql://host/db", "buildings")

        mock_conn.close.assert_called_once()

    # ── _rows_to_arrow ─────────────────────────────────────────────────────────

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


def _make_bigquery_mock(num_rows: int = 3) -> MagicMock:
    """Return a mock google.cloud.bigquery module."""
    wkb = _wkb_point(1.0, 2.0)
    arrow_table = pa.table(
        {
            "name": pa.array(["Building 1"] * num_rows),
            "geometry": pa.array([wkb] * num_rows, type=pa.binary()),
        }
    )

    # list(count_job.result())[0]["n"] — result() must return a plain list
    count_job = MagicMock()
    count_job.result.return_value = [{"n": num_rows}]

    data_job = MagicMock()
    data_job.to_arrow.return_value = arrow_table

    mock_client = MagicMock()
    mock_client.query.side_effect = [count_job, data_job]

    mock_bq = MagicMock()
    mock_bq.Client.return_value = mock_client
    mock_bq.QueryJobConfig.return_value = MagicMock()

    return mock_bq


def _bigquery_sys_modules(mock_bq: MagicMock) -> dict:
    """Build the sys.modules patch dict for BigQuery.

    'from google.cloud import bigquery as bq' resolves via the google.cloud
    module attribute, not sys.modules["google.cloud.bigquery"] directly.
    Both must point at mock_bq, otherwise later tests get a stale auto-attr.
    """
    mock_google = MagicMock()
    mock_google.cloud.bigquery = mock_bq
    return {
        "google": mock_google,
        "google.cloud": mock_google.cloud,
        "google.cloud.bigquery": mock_bq,
    }


def _snowflake_sys_modules(mock_sf: MagicMock) -> dict:
    """Build the sys.modules patch dict for Snowflake."""
    return {"snowflake": mock_sf, "snowflake.connector": mock_sf.connector}


class TestBigQueryEngine:
    # ── guard ──────────────────────────────────────────────────────────────────

    @patch("geoassert.engines.bigquery.HAS_BIGQUERY", False)
    def test_check_bigquery_raises_without_package(self) -> None:
        from geoassert.engines.bigquery import check_bigquery

        with pytest.raises(ImportError, match="google-cloud-bigquery"):
            check_bigquery()

    # ── read_bigquery_info — happy path ────────────────────────────────────────

    def test_returns_dataset_info_with_correct_metadata(self) -> None:
        mock_bq = _make_bigquery_mock(num_rows=3)

        with (
            patch.dict(sys.modules, _bigquery_sys_modules(mock_bq)),
            patch("geoassert.engines.bigquery.HAS_BIGQUERY", True),
        ):
            from geoassert.engines.bigquery import read_bigquery_info

            info = read_bigquery_info("my-project", "my_dataset", "buildings")

        assert info.source_type == "bigquery"
        assert info.num_rows == 3
        assert info.path == "bigquery://my-project/my_dataset/buildings"
        assert info.geo_metadata["primary_column"] == "geometry"
        assert info.geo_metadata["columns"]["geometry"]["crs"]["id"]["code"] == 4326

    def test_arrow_table_columns_preserved(self) -> None:
        mock_bq = _make_bigquery_mock(num_rows=2)

        with (
            patch.dict(sys.modules, _bigquery_sys_modules(mock_bq)),
            patch("geoassert.engines.bigquery.HAS_BIGQUERY", True),
        ):
            from geoassert.engines.bigquery import read_bigquery_info

            info = read_bigquery_info("proj", "ds", "tbl")

        assert "geometry" in info.table.column_names
        assert "name" in info.table.column_names

    def test_query_failure_raises_data_read_error(self) -> None:
        mock_bq = MagicMock()
        mock_client = MagicMock()
        mock_client.query.side_effect = Exception("quota exceeded")
        mock_bq.Client.return_value = mock_client
        mock_bq.QueryJobConfig.return_value = MagicMock()

        with (
            patch.dict(sys.modules, _bigquery_sys_modules(mock_bq)),
            patch("geoassert.engines.bigquery.HAS_BIGQUERY", True),
        ):
            from geoassert.engines.bigquery import read_bigquery_info
            from geoassert.exceptions import DataReadError

            with pytest.raises(DataReadError, match="BigQuery query failed"):
                read_bigquery_info("proj", "ds", "tbl")

    def test_sample_passed_as_limit(self) -> None:
        mock_bq = _make_bigquery_mock(num_rows=2)

        with (
            patch.dict(sys.modules, _bigquery_sys_modules(mock_bq)),
            patch("geoassert.engines.bigquery.HAS_BIGQUERY", True),
        ):
            from geoassert.engines.bigquery import read_bigquery_info

            read_bigquery_info("proj", "ds", "tbl", sample=10)

        data_query_call = mock_bq.Client.return_value.query.call_args_list[1]
        assert "LIMIT 10" in data_query_call.args[0]


# ── Snowflake engine ───────────────────────────────────────────────────────────


def _make_snowflake_mock(num_rows: int = 3, warehouse: str | None = None) -> MagicMock:
    """Return a mock snowflake.connector module."""
    wkb = _wkb_point(1.0, 2.0)
    data_rows = [("Building 1", wkb)] * num_rows

    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = (num_rows,)
    mock_cur.fetchall.return_value = data_rows
    mock_cur.description = [("NAME",), ("GEOMETRY",)]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    mock_sf = MagicMock()
    mock_sf.connector.connect.return_value = mock_conn

    return mock_sf


class TestSnowflakeEngine:
    # ── guard ──────────────────────────────────────────────────────────────────

    @patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", False)
    def test_check_snowflake_raises_without_package(self) -> None:
        from geoassert.engines.snowflake import check_snowflake

        with pytest.raises(ImportError, match="snowflake-connector-python"):
            check_snowflake()

    # ── read_snowflake_info — happy path ───────────────────────────────────────

    def test_returns_dataset_info_with_correct_metadata(self) -> None:
        mock_sf = _make_snowflake_mock(num_rows=3)

        with (
            patch.dict(sys.modules, _snowflake_sys_modules(mock_sf)),
            patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", True),
        ):
            from geoassert.engines.snowflake import read_snowflake_info

            info = read_snowflake_info("myaccount", "user", "pass", "MY_DB", "PUBLIC", "BUILDINGS")

        assert info.source_type == "snowflake"
        assert info.num_rows == 3
        assert info.path == "snowflake://myaccount/MY_DB/PUBLIC/BUILDINGS"
        assert info.geo_metadata["primary_column"] == "geometry"
        assert info.geo_metadata["columns"]["geometry"]["crs"]["id"]["code"] == 4326

    def test_column_names_lowercased(self) -> None:
        """Snowflake returns uppercase names — engine must lowercase them."""
        mock_sf = _make_snowflake_mock(num_rows=2)

        with (
            patch.dict(sys.modules, _snowflake_sys_modules(mock_sf)),
            patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", True),
        ):
            from geoassert.engines.snowflake import read_snowflake_info

            info = read_snowflake_info("acct", "u", "p", "DB", "S", "T")

        assert "name" in info.table.column_names
        assert "geometry" in info.table.column_names
        assert "NAME" not in info.table.column_names

    def test_warehouse_included_in_connect_params(self) -> None:
        mock_sf = _make_snowflake_mock(num_rows=1)

        with (
            patch.dict(sys.modules, _snowflake_sys_modules(mock_sf)),
            patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", True),
        ):
            from geoassert.engines.snowflake import read_snowflake_info

            read_snowflake_info("acct", "u", "p", "DB", "S", "T", warehouse="COMPUTE_WH")

        connect_kwargs = mock_sf.connector.connect.call_args.kwargs
        assert connect_kwargs.get("warehouse") == "COMPUTE_WH"

    def test_no_warehouse_omitted_from_connect_params(self) -> None:
        mock_sf = _make_snowflake_mock(num_rows=1)

        with (
            patch.dict(sys.modules, _snowflake_sys_modules(mock_sf)),
            patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", True),
        ):
            from geoassert.engines.snowflake import read_snowflake_info

            read_snowflake_info("acct", "u", "p", "DB", "S", "T")

        connect_kwargs = mock_sf.connector.connect.call_args.kwargs
        assert "warehouse" not in connect_kwargs

    def test_connection_failure_raises_data_read_error(self) -> None:
        mock_sf = MagicMock()
        mock_sf.connector.connect.side_effect = Exception("auth failed")

        with (
            patch.dict(sys.modules, _snowflake_sys_modules(mock_sf)),
            patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", True),
        ):
            from geoassert.engines.snowflake import read_snowflake_info
            from geoassert.exceptions import DataReadError

            with pytest.raises(DataReadError, match="Cannot connect to Snowflake"):
                read_snowflake_info("acct", "u", "p", "DB", "S", "T")

    def test_query_failure_raises_data_read_error(self) -> None:
        mock_sf = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = Exception("object does not exist")
        mock_conn.cursor.return_value = mock_cur
        mock_sf.connector.connect.return_value = mock_conn

        with (
            patch.dict(sys.modules, _snowflake_sys_modules(mock_sf)),
            patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", True),
        ):
            from geoassert.engines.snowflake import read_snowflake_info
            from geoassert.exceptions import DataReadError

            with pytest.raises(DataReadError, match="Snowflake query failed"):
                read_snowflake_info("acct", "u", "p", "DB", "S", "T")

    def test_connection_closed_after_query(self) -> None:
        mock_sf = _make_snowflake_mock(num_rows=1)

        with (
            patch.dict(sys.modules, _snowflake_sys_modules(mock_sf)),
            patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", True),
        ):
            from geoassert.engines.snowflake import read_snowflake_info

            read_snowflake_info("acct", "u", "p", "DB", "S", "T")

        mock_sf.connector.connect.return_value.close.assert_called_once()

    def test_connection_closed_even_on_error(self) -> None:
        mock_sf = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = Exception("boom")
        mock_conn.cursor.return_value = mock_cur
        mock_sf.connector.connect.return_value = mock_conn

        with (
            patch.dict(sys.modules, _snowflake_sys_modules(mock_sf)),
            patch("geoassert.engines.snowflake.HAS_SNOWFLAKE", True),
        ):
            from geoassert.engines.snowflake import read_snowflake_info
            from geoassert.exceptions import DataReadError

            with pytest.raises(DataReadError):
                read_snowflake_info("acct", "u", "p", "DB", "S", "T")

        mock_conn.close.assert_called_once()

    # ── _rows_to_arrow ─────────────────────────────────────────────────────────

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


# ── DatasetInfo source_type / table fields ────────────────────────────────────


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
