"""Validation orchestrator — runs all applicable checks for a dataset + contract."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from geoassert.engines.pyarrow import DatasetInfo, read_geoparquet_info
from geoassert.result import CheckResult, ValidationResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract


def run_validation(
    path: Path | str,
    contract: Contract,
    sample: int | None = None,
    engine: str = "pyarrow",
) -> ValidationResult:
    path = Path(path)
    info = read_geoparquet_info(path)
    info.sample = sample
    info.engine = engine
    all_checks: list[CheckResult] = []

    # GeoParquet metadata — always run for Parquet inputs
    from geoassert.checks.geoparquet import run_metadata_checks

    all_checks.extend(run_metadata_checks(info, contract))

    # CRS checks (metadata only, no extras needed)
    from geoassert.checks.crs import run_crs_checks

    all_checks.extend(run_crs_checks(info, contract))

    # Bounds checks (metadata only + optional shapely consistency check)
    from geoassert.checks.bounds import run_bounds_checks

    all_checks.extend(run_bounds_checks(info, contract))

    # Geometry checks — require shapely
    if contract.geometry is not None:
        all_checks.extend(_run_geometry_checks(info, contract))

    # Attribute checks — pyarrow or duckdb
    if contract.attributes:
        from geoassert.checks.attributes import run_attribute_checks

        all_checks.extend(run_attribute_checks(info, contract))

    # Apply per-check severity overrides from contract
    if contract.severity:
        for check in all_checks:
            if check.check in contract.severity:
                check.severity = contract.severity[check.check]

    failures = [c for c in all_checks if c.status == "fail"]
    warnings = [c for c in all_checks if c.status == "warn"]

    stats: dict = {
        "path": str(path),
        "rows": info.num_rows,
        "columns": len(info.schema.names),
        "engine": engine,
    }
    if sample is not None:
        stats["sample"] = sample

    return ValidationResult(
        passed=len(failures) == 0,
        failures=failures,
        warnings=warnings,
        checks=all_checks,
        stats=stats,
    )


def validate_directory(
    path: Path | str,
    contract: Contract,
    pattern: str = "**/*.parquet",
    sample: int | None = None,
    engine: str = "pyarrow",
) -> list[ValidationResult]:
    """Validate all Parquet files in a directory against a contract.

    Also runs partition-level checks (schema consistency, Hive structure).
    Returns one ValidationResult per file, preceded by a partition-level summary.
    """
    root = Path(path)
    files = sorted(root.glob(pattern))
    if not files:
        return []

    # Partition-level checks — use a synthetic DatasetInfo pointing at the directory
    results: list[ValidationResult] = []
    _partition_result = _run_directory_checks(root, contract)
    results.append(_partition_result)

    # Per-file validation
    for f in files:
        results.append(run_validation(f, contract, sample=sample, engine=engine))

    return results


def _run_directory_checks(root: Path, contract: Contract) -> ValidationResult:
    """Run partition-aware checks on the directory as a whole."""
    import pyarrow as pa

    from geoassert.checks.partitions import run_partition_checks

    # Minimal DatasetInfo pointing at the directory
    dir_info = DatasetInfo(
        path=root,
        schema=pa.schema([]),
        num_rows=0,
    )
    checks = run_partition_checks(dir_info, contract)
    failures = [c for c in checks if c.status == "fail"]
    warnings = [c for c in checks if c.status == "warn"]
    return ValidationResult(
        passed=len(failures) == 0,
        failures=failures,
        warnings=warnings,
        checks=checks,
        stats={"path": str(root), "type": "directory"},
    )


def _run_geometry_checks(info: DatasetInfo, contract: Contract) -> list[CheckResult]:
    try:
        from geoassert.checks.geometry import run_geometry_checks

        return run_geometry_checks(info, contract)
    except ImportError:
        return [
            CheckResult(
                check="geometry",
                status="skip",
                severity="info",
                message="Geometry checks skipped: install geoassert[shapely] to enable.",
            )
        ]
