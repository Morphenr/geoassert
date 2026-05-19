"""DuckDB spatial engine (requires geoassert[duckdb])."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

try:
    import duckdb

    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


def check_duckdb() -> None:
    if not HAS_DUCKDB:
        raise ImportError(
            "duckdb is required for this engine. Install it with: pip install 'geoassert[duckdb]'"
        )


def get_connection() -> duckdb.DuckDBPyConnection:
    check_duckdb()
    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial;")
    return conn


def query_parquet(path: Path | str, sql: str) -> duckdb.DuckDBPyRelation:
    """Run a SQL query against a Parquet file using DuckDB."""
    conn = get_connection()
    conn.execute(f"CREATE VIEW dataset AS SELECT * FROM read_parquet('{path}')")
    return conn.execute(sql)
