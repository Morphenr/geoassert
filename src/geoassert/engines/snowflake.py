"""Snowflake engine — read geometry tables from Snowflake.

Requires: pip install "geoassert[snowflake]"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from geoassert.engines.pyarrow import DatasetInfo

try:
    import snowflake.connector  # noqa: F401

    HAS_SNOWFLAKE = True
except ImportError:
    HAS_SNOWFLAKE = False


def check_snowflake() -> None:
    if not HAS_SNOWFLAKE:
        raise ImportError(
            "snowflake-connector-python is required for the Snowflake engine. "
            "Install it with: pip install 'geoassert[snowflake]'"
        )


def read_snowflake_info(
    account: str,
    user: str,
    password: str,
    database: str,
    schema: str,
    table: str,
    *,
    geom_col: str = "geometry",
    warehouse: str | None = None,
    where: str | None = None,
    sample: int | None = None,
) -> DatasetInfo:
    """Read a Snowflake geometry table and return a DatasetInfo for validation.

    Args:
        account: Snowflake account identifier (e.g. ``"xy12345.us-east-1"``).
        user: Snowflake username.
        password: Snowflake password.
        database: Snowflake database name.
        schema: Snowflake schema name.
        table: Table name.
        geom_col: Name of the GEOMETRY column (default: ``"geometry"``).
        warehouse: Snowflake virtual warehouse (optional).
        where: Optional WHERE clause (without the ``WHERE`` keyword).
        sample: Row limit.

    Returns:
        ``DatasetInfo`` with ``source_type="snowflake"`` and an in-memory
        PyArrow table ready for validation checks.
    """
    check_snowflake()
    import snowflake.connector

    from geoassert.engines.pyarrow import DatasetInfo
    from geoassert.exceptions import DataReadError

    connect_params: dict[str, Any] = {
        "account": account,
        "user": user,
        "password": password,
        "database": database,
        "schema": schema,
    }
    if warehouse:
        connect_params["warehouse"] = warehouse

    try:
        conn = snowflake.connector.connect(**connect_params)
    except Exception as exc:
        raise DataReadError(f"Cannot connect to Snowflake ({account}): {exc}") from exc

    fqt = f'"{database}"."{schema}"."{table}"'
    where_clause = f"WHERE {where}" if where else ""
    limit_clause = f"LIMIT {sample}" if sample is not None else ""

    try:
        cur = conn.cursor()

        # Row count
        cur.execute(f"SELECT COUNT(*) FROM {fqt} {where_clause}")  # noqa: S608
        num_rows: int = cur.fetchone()[0]

        # Fetch data — GEOMETRY as WKB bytes via ST_ASEWKB
        cur.execute(
            f"SELECT * EXCLUDE {geom_col}, ST_ASEWKB({geom_col}) AS {geom_col} "  # noqa: S608
            f"FROM {fqt} {where_clause} {limit_clause}"
        )
        colnames = [desc[0].lower() for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
    except Exception as exc:
        raise DataReadError(f"Snowflake query failed: {exc}") from exc
    finally:
        conn.close()

    arrow_table = _rows_to_arrow(colnames, rows, geom_col)

    # Snowflake GEOMETRY is stored with an SRID; we default to 4326 (WGS84) if unknown
    geo_metadata: dict[str, Any] = {
        "version": "1.1.0",
        "primary_column": geom_col,
        "columns": {
            geom_col: {
                "encoding": "WKB",
                "geometry_types": [],
                "crs": {
                    "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
                    "type": "GeographicCRS",
                    "name": "EPSG:4326",
                    "id": {"authority": "EPSG", "code": 4326},
                },
            }
        },
    }

    return DatasetInfo(
        path=f"snowflake://{account}/{database}/{schema}/{table}",
        schema=arrow_table.schema,
        num_rows=num_rows,
        geo_metadata=geo_metadata,
        source_type="snowflake",
        table=arrow_table,
    )


def _rows_to_arrow(colnames: list[str], rows: list[tuple], geom_col: str) -> Any:
    """Convert Snowflake cursor results to a PyArrow Table."""
    import pyarrow as pa

    if not rows:
        return pa.table({name: pa.array([], type=pa.null()) for name in colnames})

    columns: dict[str, list] = {name: [] for name in colnames}
    for row in rows:
        for name, value in zip(colnames, row, strict=False):
            columns[name].append(value)

    arrays: dict[str, Any] = {}
    for name, values in columns.items():
        non_null = [v for v in values if v is not None]
        if not non_null:
            arrays[name] = pa.array(values, type=pa.null())
            continue
        sample = non_null[0]
        if name == geom_col or isinstance(sample, (bytes, bytearray, memoryview)):
            byte_vals = [bytes(v) if v is not None else None for v in values]
            arrays[name] = pa.array(byte_vals, type=pa.binary())
        elif isinstance(sample, bool):
            arrays[name] = pa.array(values, type=pa.bool_())
        elif isinstance(sample, int):
            arrays[name] = pa.array(values, type=pa.int64())
        elif isinstance(sample, float):
            arrays[name] = pa.array(values, type=pa.float64())
        else:
            str_vals = [str(v) if v is not None else None for v in values]
            arrays[name] = pa.array(str_vals, type=pa.string())

    return pa.table(arrays)
