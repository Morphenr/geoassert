"""Spatial bounds checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geoassert.checks.base import BaseCheck
from geoassert.result import CheckResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo


def _bbox_from_meta(info: DatasetInfo) -> list[float] | None:
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

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        bbox = _bbox_from_meta(info)
        if bbox is None:
            return CheckResult(
                check=self.name,
                status="warn",
                severity="warn",
                message="No bbox metadata found in GeoParquet column metadata.",
                suggestion="Include bbox in GeoParquet metadata for faster spatial filtering.",
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"Dataset bounds from metadata: {bbox}",
        )


class BoundsWithinCheck(BaseCheck):
    name = "bounds.within"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        if not (contract and contract.bounds and contract.bounds.within):
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no bounds.within constraint in contract.",
            )

        expected_bbox = contract.bounds.within.bbox
        if expected_bbox is None:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: bounds.within.bbox not set (country preset not yet supported).",
            )

        observed_bbox = _bbox_from_meta(info)
        if observed_bbox is None:
            return CheckResult(
                check=self.name,
                status="warn",
                severity="warn",
                message="Cannot verify bounds: no bbox metadata in dataset.",
                suggestion=(
                    "Include bbox in GeoParquet metadata, or use a full geometry scan"
                    " (not yet supported)."
                ),
            )

        e_minx, e_miny, e_maxx, e_maxy = expected_bbox
        o_minx, o_miny, o_maxx, o_maxy = observed_bbox

        if o_minx < e_minx or o_miny < e_miny or o_maxx > e_maxx or o_maxy > e_maxy:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message="Dataset bounds exceed the expected bbox.",
                expected=expected_bbox,
                observed=observed_bbox,
                why_it_matters=(
                    "Data outside expected bounds may indicate coordinate errors"
                    " or unexpected coverage."
                ),
                suggestion="Verify the data source or update the contract bounds.",
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"Dataset bounds {observed_bbox} are within expected bbox {expected_bbox}.",
        )


class BboxConsistencyCheck(BaseCheck):
    """Compare declared GeoParquet bbox metadata to the actual bbox computed from geometries."""

    name = "bounds.bbox_consistency"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        declared = _bbox_from_meta(info)
        if declared is None:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no declared bbox in GeoParquet metadata.",
            )

        # Determine geometry column
        primary = info.geo_metadata.get("primary_column") if info.geo_metadata else None  # type: ignore[union-attr]
        col = primary or "geometry"
        if col not in info.schema.names:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message=f"Skipped: geometry column {col!r} not in schema.",
            )

        try:
            from geoassert.engines.pyarrow import read_table_for_check
            from geoassert.engines.shapely import wkb_column_to_geometries
        except ImportError:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: install geoassert[shapely] to enable bbox consistency checks.",
            )

        import shapely

        table = read_table_for_check(info, columns=[col])
        geoms = wkb_column_to_geometries(table.column(col))
        valid_geoms = [g for g in geoms if g is not None and not g.is_empty]
        if not valid_geoms:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no valid geometries found to compute actual bbox.",
            )

        bounds = shapely.bounds(shapely.geometrycollections(valid_geoms))
        actual_minx, actual_miny, actual_maxx, actual_maxy = (
            float(bounds[0]),
            float(bounds[1]),
            float(bounds[2]),
            float(bounds[3]),
        )
        actual = [actual_minx, actual_miny, actual_maxx, actual_maxy]

        d_minx, d_miny, d_maxx, d_maxy = declared
        # Tolerance: allow 1e-6 degree (~0.1 m) of floating-point drift
        tol = 1e-6
        mismatch = (
            abs(actual_minx - d_minx) > tol
            or abs(actual_miny - d_miny) > tol
            or abs(actual_maxx - d_maxx) > tol
            or abs(actual_maxy - d_maxy) > tol
        )
        if mismatch:
            return CheckResult(
                check=self.name,
                status="warn",
                severity="warn",
                message="Declared bbox in metadata does not match the actual geometry bounds.",
                expected=declared,
                observed=actual,
                suggestion=(
                    "Re-export the file with accurate bbox metadata, "
                    "or update the GeoParquet metadata to reflect the actual bounds."
                ),
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"Declared bbox {declared} matches actual geometry bounds.",
        )


def run_bounds_checks(
    info: DatasetInfo,
    contract: Contract | None = None,
) -> list[CheckResult]:
    return [
        c.run(info, contract)
        for c in [BoundsAvailableCheck(), BoundsWithinCheck(), BboxConsistencyCheck()]
    ]
