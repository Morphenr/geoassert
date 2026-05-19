"""BigQuery GIS engine — read geometry tables from Google BigQuery.

Requires: pip install "geoassert[bigquery]"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from geoassert.engines.pyarrow import DatasetInfo

try:
    from google.cloud import bigquery  # noqa: F401

    HAS_BIGQUERY = True
except ImportError:
    HAS_BIGQUERY = False


def check_bigquery() -> None:
    if not HAS_BIGQUERY:
        raise ImportError(
            "google-cloud-bigquery is required for the BigQuery engine. "
            "Install it with: pip install 'geoassert[bigquery]'"
        )


def read_bigquery_info(
    project: str,
    dataset: str,
    table: str,
    *,
    geom_col: str = "geometry",
    where: str | None = None,
    sample: int | None = None,
    credentials: Any | None = None,
) -> DatasetInfo:
    """Read a BigQuery GIS table and return a DatasetInfo for validation.

    Args:
        project: GCP project ID.
        dataset: BigQuery dataset name.
        table: BigQuery table name.
        geom_col: Name of the GEOGRAPHY or GEOMETRY column (default: ``"geometry"``).
        where: Optional WHERE clause (without the ``WHERE`` keyword).
        sample: Row limit.
        credentials: Optional ``google.oauth2.credentials.Credentials``.
            When omitted, uses Application Default Credentials.

    Returns:
        ``DatasetInfo`` with ``source_type="bigquery"`` and an in-memory
        PyArrow table ready for validation checks.
    """
    check_bigquery()
    from google.cloud import bigquery as bq

    from geoassert.engines.pyarrow import DatasetInfo
    from geoassert.exceptions import DataReadError

    client = bq.Client(project=project, credentials=credentials)
    table_ref = f"`{project}`.`{dataset}`.`{table}`"

    where_clause = f"WHERE {where}" if where else ""
    limit_clause = f"LIMIT {sample}" if sample is not None else ""

    try:
        # Row count
        count_job = client.query(
            f"SELECT COUNT(*) AS n FROM {table_ref} {where_clause}"  # noqa: S608
        )
        num_rows: int = list(count_job.result())[0]["n"]

        # Fetch data — GEOGRAPHY as WKB bytes via ST_AsWKB
        query = (
            f"SELECT * EXCEPT(`{geom_col}`), "  # noqa: S608
            f"ST_AsWKB(`{geom_col}`) AS `{geom_col}` "
            f"FROM {table_ref} {where_clause} {limit_clause}"
        )
        job_config = bq.QueryJobConfig()
        arrow_table = client.query(query, job_config=job_config).to_arrow()
    except Exception as exc:
        raise DataReadError(f"BigQuery query failed ({project}.{dataset}.{table}): {exc}") from exc

    geo_metadata: dict[str, Any] = {
        "version": "1.1.0",
        "primary_column": geom_col,
        "columns": {
            geom_col: {
                "encoding": "WKB",
                "geometry_types": [],
                # BigQuery GEOGRAPHY is always WGS84
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
        path=f"bigquery://{project}/{dataset}/{table}",
        schema=arrow_table.schema,
        num_rows=num_rows,
        geo_metadata=geo_metadata,
        source_type="bigquery",
        table=arrow_table,
    )
