"""Spatial bounds checks."""
from __future__ import annotations

from typing import TYPE_CHECKING

from geoassert.checks.base import BaseCheck
from geoassert.result import CheckResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo


def _bbox_from_meta(info: "DatasetInfo") -> list[float] | None:
    """Return [minx, miny, maxx, maxy] from GeoParquet metadata, if present."""
    if not info.geo_metadata:
        return None
    primary = info.geo_metadata.get("primary_column")
    if not primary:
        return None
    col_meta = info.geo_metadata.get("columns", {}).get(primary, {})
    return col_meta.get("bbox")


class BoundsAvailableCheck(BaseCheck):
    name = "bounds.available"

    def run(self, info: "DatasetInfo", contract: "Contract | None" = None) -> CheckResult:
        bbox = _bbox_from_meta(info)
        if bbox is None:
            return CheckResult(
                check=self.name, status="warn", severity="warn",
                message="No bbox metadata found in GeoParquet column metadata.",
                suggestion="Include bbox in GeoParquet metadata for faster spatial filtering.",
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message=f"Dataset bounds from metadata: {bbox}",
        )


class BoundsWithinCheck(BaseCheck):
    name = "bounds.within"

    def run(self, info: "DatasetInfo", contract: "Contract | None" = None) -> CheckResult:
        if not (contract and contract.bounds and contract.bounds.within):
            return CheckResult(check=self.name, status="skip", severity="info",
                               message="Skipped: no bounds.within constraint in contract.")

        expected_bbox = contract.bounds.within.bbox
        if expected_bbox is None:
            return CheckResult(check=self.name, status="skip", severity="info",
                               message="Skipped: bounds.within.bbox not set (country preset not yet supported).")

        observed_bbox = _bbox_from_meta(info)
        if observed_bbox is None:
            return CheckResult(
                check=self.name, status="warn", severity="warn",
                message="Cannot verify bounds: no bbox metadata in dataset.",
                suggestion="Include bbox in GeoParquet metadata, or use a full geometry scan (not yet supported).",
            )

        e_minx, e_miny, e_maxx, e_maxy = expected_bbox
        o_minx, o_miny, o_maxx, o_maxy = observed_bbox

        if o_minx < e_minx or o_miny < e_miny or o_maxx > e_maxx or o_maxy > e_maxy:
            return CheckResult(
                check=self.name, status="fail", severity="error",
                message="Dataset bounds exceed the expected bbox.",
                expected=expected_bbox,
                observed=observed_bbox,
                why_it_matters="Data outside expected bounds may indicate coordinate errors or unexpected coverage.",
                suggestion="Verify the data source or update the contract bounds.",
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message=f"Dataset bounds {observed_bbox} are within expected bbox {expected_bbox}.",
        )


def run_bounds_checks(
    info: "DatasetInfo",
    contract: "Contract | None" = None,
) -> list[CheckResult]:
    return [c.run(info, contract) for c in [BoundsAvailableCheck(), BoundsWithinCheck()]]
