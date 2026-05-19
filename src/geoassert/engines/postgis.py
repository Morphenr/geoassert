"""PostGIS engine — read geometry tables from PostgreSQL/PostGIS.

Requires: pip install "geoassert[postgis]"
"""

from __future__ import annotations

import datetime
import decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from geoassert.engines.pyarrow import DatasetInfo

try:
    import psycopg2  # noqa: F401

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


def check_postgis() -> None:
    if not HAS_PSYCOPG2:
        raise ImportError(
            "psycopg2 is required for the PostGIS engine. "
            "Install it with: pip install 'geoassert[postgis]'"
        )


def read_postgis_info(
    dsn: str,
    table: str,
    *,
    geom_col: str = "geometry",
    schema: str = "public",
    where: str | None = None,
    sample: int | None = None,
) -> DatasetInfo:
    """Read a PostGIS table and return a DatasetInfo for validation.

    Args:
        dsn: PostgreSQL connection string (e.g. ``postgresql://user:pass@host/db``).
        table: Table name.
        geom_col: Name of the geometry column (default: ``"geometry"``).
        schema: Database schema (default: ``"public"``).
        where: Optional WHERE clause (without the ``WHERE`` keyword).
        sample: Row limit. When set, only this many rows are fetched.

    Returns:
        ``DatasetInfo`` with ``source_type="postgis"`` and an in-memory
        PyArrow table ready for validation checks.
    """
    check_postgis()
    import psycopg2

    from geoassert.engines.pyarrow import DatasetInfo
    from geoassert.exceptions import DataReadError

    where_clause = f"WHERE {where}" if where else ""
    limit_clause = f"LIMIT {sample}" if sample is not None else ""

    try:
        conn = psycopg2.connect(dsn)
    except Exception as exc:
        raise DataReadError(f"Cannot connect to PostGIS ({dsn}): {exc}") from exc

    try:
        with conn.cursor() as cur:
            # Total row count (without limit)
            cur.execute(
                f'SELECT COUNT(*) FROM "{schema}"."{table}" {where_clause}'  # noqa: S608
            )
            num_rows: int = cur.fetchone()[0]

            # CRS from geometry_columns metadata view
            cur.execute(
                "SELECT srid FROM geometry_columns "
                "WHERE f_table_schema = %s AND f_table_name = %s "
                "AND f_geometry_column = %s",
                (schema, table, geom_col),
            )
            row = cur.fetchone()
            srid: int | None = row[0] if row else None

            # Fetch data — geometry as WKB bytes, all other columns as-is
            cur.execute(
                f'SELECT *, ST_AsWKB("{geom_col}") AS __geom_wkb__ '  # noqa: S608
                f'FROM "{schema}"."{table}" {where_clause} {limit_clause}'
            )
            colnames = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
    except psycopg2.Error as exc:
        raise DataReadError(f"PostGIS query failed: {exc}") from exc
    finally:
        conn.close()

    # Replace geometry column with WKB bytes column
    wkb_idx = colnames.index("__geom_wkb__")
    geom_idx = colnames.index(geom_col)
    final_colnames = [
        "__geom_wkb__" if i == geom_idx else name for i, name in enumerate(colnames) if i != wkb_idx
    ]
    final_colnames[geom_idx] = geom_col
    processed_rows = [
        tuple(row[wkb_idx] if i == geom_idx else v for i, v in enumerate(row) if i != wkb_idx)
        for row in rows
    ]

    arrow_table = _rows_to_arrow(final_colnames, processed_rows)

    # Build minimal geo_metadata so CRS and bounds checks can run
    geo_metadata: dict[str, Any] = {
        "version": "1.1.0",
        "primary_column": geom_col,
        "columns": {
            geom_col: {
                "encoding": "WKB",
                "geometry_types": [],
                **(
                    {
                        "crs": {
                            "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
                            "type": "GeographicCRS",
                            "name": f"EPSG:{srid}",
                            "id": {"authority": "EPSG", "code": srid},
                        }
                    }
                    if srid
                    else {}
                ),
            }
        },
    }

    return DatasetInfo(
        path=f"postgis://{schema}.{table}",
        schema=arrow_table.schema,
        num_rows=num_rows,
        geo_metadata=geo_metadata,
        source_type="postgis",
        table=arrow_table,
    )


def _rows_to_arrow(colnames: list[str], rows: list[tuple]) -> Any:
    """Convert psycopg2 row results to a PyArrow Table."""
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
        if isinstance(sample, (bytes, memoryview)):
            byte_values = [bytes(v) if v is not None else None for v in values]
            arrays[name] = pa.array(byte_values, type=pa.binary())
        elif isinstance(sample, bool):
            arrays[name] = pa.array(values, type=pa.bool_())
        elif isinstance(sample, int):
            arrays[name] = pa.array(values, type=pa.int64())
        elif isinstance(sample, float):
            arrays[name] = pa.array(values, type=pa.float64())
        elif isinstance(sample, decimal.Decimal):
            float_vals = [float(v) if v is not None else None for v in values]
            arrays[name] = pa.array(float_vals, type=pa.float64())
        elif isinstance(sample, datetime.datetime):
            arrays[name] = pa.array(values, type=pa.timestamp("us"))
        elif isinstance(sample, datetime.date):
            arrays[name] = pa.array(values, type=pa.date32())
        else:
            str_vals = [str(v) if v is not None else None for v in values]
            arrays[name] = pa.array(str_vals, type=pa.string())

    return pa.table(arrays)
