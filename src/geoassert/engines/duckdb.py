"""DuckDB engine for attribute checks (requires geoassert[duckdb])."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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


def _conn(path: Path | str) -> tuple[duckdb.DuckDBPyConnection, str]:
    """Return (connection, normalised path string)."""
    check_duckdb()
    path_str = str(path)
    conn = duckdb.connect()
    return conn, path_str


def count_nulls(path: Path | str, column: str) -> int:
    """Return number of NULL values in *column*."""
    conn, p = _conn(path)
    result = conn.execute(
        f"SELECT COUNT(*) FROM read_parquet(?) WHERE \"{column}\" IS NULL", [p]
    ).fetchone()
    return int(result[0]) if result else 0


def count_non_null(path: Path | str, column: str) -> int:
    """Return number of non-NULL values in *column*."""
    conn, p = _conn(path)
    result = conn.execute(
        f"SELECT COUNT(\"{column}\") FROM read_parquet(?)", [p]
    ).fetchone()
    return int(result[0]) if result else 0


def count_distinct(path: Path | str, column: str) -> int:
    """Return number of distinct (non-NULL) values in *column*."""
    conn, p = _conn(path)
    result = conn.execute(
        f"SELECT COUNT(DISTINCT \"{column}\") FROM read_parquet(?)", [p]
    ).fetchone()
    return int(result[0]) if result else 0


def count_total(path: Path | str) -> int:
    """Return total row count."""
    conn, p = _conn(path)
    result = conn.execute("SELECT COUNT(*) FROM read_parquet(?)", [p]).fetchone()
    return int(result[0]) if result else 0


def get_min_max(path: Path | str, column: str) -> tuple[Any, Any]:
    """Return (min, max) for *column* ignoring NULLs."""
    conn, p = _conn(path)
    result = conn.execute(
        f"SELECT MIN(\"{column}\"), MAX(\"{column}\") FROM read_parquet(?)", [p]
    ).fetchone()
    if result is None:
        return (None, None)
    return (result[0], result[1])


def query_parquet(path: Path | str, sql: str) -> duckdb.DuckDBPyRelation:
    """Run arbitrary SQL against a Parquet file (table alias: *dataset*)."""
    conn, p = _conn(path)
    conn.execute(f"CREATE VIEW dataset AS SELECT * FROM read_parquet('{p}')")
    return conn.execute(sql)
