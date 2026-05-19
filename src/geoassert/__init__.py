"""geoassert — data contracts for geospatial pipelines."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geoassert.contracts.loader import load_contract
from geoassert.contracts.schema import Contract
from geoassert.result import CheckResult, ValidationResult

__all__ = [
    "validate",
    "profile",
    "load_contract",
    "Contract",
    "ValidationResult",
    "CheckResult",
]

if TYPE_CHECKING:
    from pathlib import Path

__version__ = "0.1.0"


def validate(
    path: str | Path,
    contract: str | Path | Contract,
) -> ValidationResult:
    """Validate a geospatial dataset against a contract.

    Args:
        path:     Path to the dataset (GeoParquet).
        contract: Path to a contract YAML, or a loaded Contract object.

    Returns:
        ValidationResult with .passed, .failures, .warnings, and .checks.
    """
    from geoassert.runner import run_validation

    if not isinstance(contract, Contract):
        contract = load_contract(contract)
    return run_validation(path, contract)


def profile(path: str | Path) -> dict:
    """Profile a geospatial dataset and return key facts."""
    from geoassert.profiling.profiler import profile_dataset

    return profile_dataset(path)
