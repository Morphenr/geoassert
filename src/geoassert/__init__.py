"""geoassert — data contracts for geospatial pipelines."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geoassert.contracts.loader import load_contract
from geoassert.contracts.schema import Contract
from geoassert.result import CheckResult, ValidationResult

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "validate",
    "validate_source",
    "validate_directory",
    "profile",
    "load_contract",
    "Contract",
    "ValidationResult",
    "CheckResult",
]

__version__ = "0.4.0"


def validate(
    path: str | Path,
    contract: str | Path | Contract,
    *,
    sample: int | None = None,
    engine: str = "pyarrow",
) -> ValidationResult:
    """Validate a geospatial dataset against a contract.

    Args:
        path: Path to the GeoParquet file (local or cloud URI).
        contract: Path to a contract YAML, or a loaded `Contract` object.
        sample: Row limit for row-level checks. Metadata checks always run on the full file.
        engine: Compute engine for attribute checks — `"pyarrow"` (default) or `"duckdb"`.

    Returns:
        `ValidationResult` with `.passed`, `.failures`, `.warnings`, and `.checks`.

    Example:
        ```python
        import geoassert as ga

        result = ga.validate(
            "data/buildings.parquet",
            contract="contracts/buildings.yml",
        )
        if not result.passed:
            print(result.to_markdown())
        ```
    """
    from geoassert.runner import run_validation

    if not isinstance(contract, Contract):
        contract = load_contract(contract)
    return run_validation(path, contract, sample=sample, engine=engine)


def validate_source(
    source_info: object,
    contract: str | Path | Contract,
) -> ValidationResult:
    """Validate a pre-built DatasetInfo (warehouse source) against a contract.

    Use this with the warehouse engine functions to validate PostGIS, BigQuery,
    or Snowflake tables programmatically.

    Args:
        source_info: A `DatasetInfo` returned by `read_postgis_info()`,
            `read_bigquery_info()`, or `read_snowflake_info()`.
        contract: Path to a contract YAML, or a loaded `Contract` object.

    Returns:
        `ValidationResult` with `.passed`, `.failures`, `.warnings`, and `.checks`.

    Example:
        ```python
        import geoassert as ga
        from geoassert.engines.postgis import read_postgis_info

        info = read_postgis_info("postgresql://user:pass@host/db", "buildings")
        result = ga.validate_source(info, "contracts/buildings.yml")
        ```
    """
    from geoassert.runner import run_validation_from_info

    if not isinstance(contract, Contract):
        contract = load_contract(contract)
    return run_validation_from_info(source_info, contract)  # type: ignore[arg-type]


def validate_directory(
    path: str | Path,
    contract: str | Path | Contract,
    *,
    pattern: str = "**/*.parquet",
    sample: int | None = None,
    engine: str = "pyarrow",
) -> list[ValidationResult]:
    """Validate every Parquet file in a directory against a contract.

    Also runs partition-level checks (Hive structure detection and schema consistency).
    The first element of the returned list is always the directory-level summary.

    Args:
        path: Path to the directory containing Parquet files.
        contract: Path to a contract YAML, or a loaded `Contract` object.
        pattern: Glob pattern used to find files (default: `"**/*.parquet"`).
        sample: Row limit for row-level checks per file.
        engine: Compute engine — `"pyarrow"` or `"duckdb"`.

    Returns:
        List of `ValidationResult` — one directory summary followed by one per file.

    Example:
        ```python
        import geoassert as ga

        results = ga.validate_directory(
            "data/partitioned/",
            contract="contracts/buildings.yml",
        )
        all_passed = all(r.passed for r in results)
        ```
    """
    from pathlib import Path as _Path

    from geoassert.runner import validate_directory as _validate_directory

    if not isinstance(contract, Contract):
        contract = load_contract(contract)
    return _validate_directory(_Path(path), contract, pattern=pattern, sample=sample, engine=engine)


def profile(path: str | Path) -> dict:
    """Profile a geospatial dataset and return key facts as a dictionary.

    Args:
        path: Path to the dataset.

    Returns:
        Dictionary with keys such as `rows`, `column_count`, `geometry_column`,
        `geometry_types`, `crs`, and `bounds`.
    """
    from geoassert.profiling.profiler import profile_dataset

    return profile_dataset(path)
