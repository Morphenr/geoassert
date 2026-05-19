"""CRS validation checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geoassert.checks.base import BaseCheck
from geoassert.result import CheckResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo


def _observed_crs(info: DatasetInfo) -> str | None:
    """Extract CRS string from geo metadata for the primary column."""
    if not info.geo_metadata:
        return None
    primary = info.geo_metadata.get("primary_column")
    if not primary:
        return None
    col_meta = info.geo_metadata.get("columns", {}).get(primary, {})
    crs = col_meta.get("crs")
    if isinstance(crs, dict):
        try:
            crs_id = crs.get("id", {})
            return f"{crs_id['authority']}:{crs_id['code']}"
        except (KeyError, TypeError):
            return None
    return str(crs) if crs else None


class CRSExistsCheck(BaseCheck):
    name = "crs.exists"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        crs = _observed_crs(info)
        if not crs:
            return CheckResult(
                check=self.name,
                status="warn",
                severity="warn",
                message="CRS could not be determined from dataset metadata.",
                suggestion="Include CRS metadata when writing GeoParquet.",
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"CRS detected: {crs}",
        )


class CRSMatchCheck(BaseCheck):
    name = "crs.match"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        if not (contract and contract.geometry and contract.geometry.crs):
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no geometry.crs constraint in contract.",
            )
        expected = contract.geometry.crs
        observed = _observed_crs(info)
        if not observed:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message="Cannot verify CRS: no CRS detected in dataset.",
                expected=expected,
                observed=None,
            )
        if observed != expected:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message="CRS metadata differs from contract.",
                expected=expected,
                observed=observed,
                why_it_matters=(
                    "Coordinate axis order and downstream spatial operations"
                    " may behave differently."
                ),
                suggestion=(
                    f"Normalise CRS metadata before export or set allow_equivalent_crs: true "
                    f"in the contract if {observed!r} and {expected!r} are equivalent."
                ),
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"CRS matches contract: {observed}",
        )


def run_crs_checks(
    info: DatasetInfo,
    contract: Contract | None = None,
) -> list[CheckResult]:
    return [c.run(info, contract) for c in [CRSExistsCheck(), CRSMatchCheck()]]
