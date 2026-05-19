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
) -> ValidationResult:
    path = Path(path)
    info = read_geoparquet_info(path)
    info.sample = sample
    all_checks: list[CheckResult] = []

    # GeoParquet metadata — always run for Parquet inputs
    from geoassert.checks.geoparquet import run_metadata_checks

    all_checks.extend(run_metadata_checks(info, contract))

    # CRS checks (metadata only, no extras needed)
    from geoassert.checks.crs import run_crs_checks

    all_checks.extend(run_crs_checks(info, contract))

    # Bounds checks (metadata only)
    from geoassert.checks.bounds import run_bounds_checks

    all_checks.extend(run_bounds_checks(info, contract))

    # Geometry checks — require shapely
    if contract.geometry is not None:
        all_checks.extend(_run_geometry_checks(info, contract))

    # Attribute checks — pure PyArrow
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
