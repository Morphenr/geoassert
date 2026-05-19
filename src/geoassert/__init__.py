"""geoassert — data contracts for geospatial pipelines."""
from __future__ import annotations

from pathlib import Path
from typing import Union

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

__version__ = "0.1.0"


def validate(
    path: Union[str, Path],
    contract: Union[str, Path, Contract],
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


def profile(path: Union[str, Path]) -> dict:
    """Profile a geospatial dataset and return key facts."""
    from geoassert.profiling.profiler import profile_dataset

    return profile_dataset(path)
