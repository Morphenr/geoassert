"""Spatial bounds checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geoassert.checks.base import BaseCheck
from geoassert.result import CheckResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo

# Float arithmetic can introduce trailing noise (e.g. 83.2332400000001 instead of 83.23324).
# _WITHIN_TOL guards BoundsWithinCheck against false positives from such noise.
# _CONSISTENCY_TOL is the same guard for BboxConsistencyCheck's float-to-float comparison.
_WITHIN_TOL = 1e-9
_CONSISTENCY_TOL = 1e-6


def _fmt(v: float) -> str:
    """Format a coordinate, stripping float arithmetic noise beyond 6 decimal places."""
    return f"{v:.6f}".rstrip("0").rstrip(".")


def _fmt_bbox(bbox: list[float]) -> str:
    return f"[{', '.join(_fmt(v) for v in bbox)}]"


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

        # _WITHIN_TOL absorbs floating-point arithmetic noise (e.g. 83.2332400000001
        # vs 83.23324 from coordinate reprojection) so near-exact values don't false-positive.
        exceeds = (
            o_minx < e_minx - _WITHIN_TOL
            or o_miny < e_miny - _WITHIN_TOL
            or o_maxx > e_maxx + _WITHIN_TOL
            or o_maxy > e_maxy + _WITHIN_TOL
        )
        if exceeds:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message=(
                    f"Dataset bounds {_fmt_bbox(observed_bbox)} exceed"
                    f" expected bbox {_fmt_bbox(expected_bbox)}."
                ),
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
            message=(
                f"Dataset bounds {_fmt_bbox(observed_bbox)} are within"
                f" expected bbox {_fmt_bbox(expected_bbox)}."
            ),
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
        tol = _CONSISTENCY_TOL

        # "Tight" = declared bbox is smaller than actual extent — data leaks outside the
        # declared bounds. This is the more dangerous case: consumers using the declared
        # bbox for spatial filtering will silently miss features.
        declared_too_tight = (
            actual_minx < d_minx - tol
            or actual_miny < d_miny - tol
            or actual_maxx > d_maxx + tol
            or actual_maxy > d_maxy + tol
        )

        # "Loose" = declared bbox is larger than actual extent — the metadata overstates
        # coverage (e.g. declared maxy=90 but data only reaches 83.64). Not a data error,
        # but stale or over-conservative metadata that may mislead spatial index lookups.
        declared_too_loose = (
            actual_minx > d_minx + tol
            or actual_miny > d_miny + tol
            or actual_maxx < d_maxx - tol
            or actual_maxy < d_maxy - tol
        )

        fmt_declared = _fmt_bbox(declared)
        fmt_actual = _fmt_bbox(actual)

        if declared_too_tight:
            return CheckResult(
                check=self.name,
                status="warn",
                severity="warn",
                message=(
                    f"Declared bbox {fmt_declared} is smaller than the actual geometry"
                    f" extent {fmt_actual} — features fall outside the declared bounds."
                ),
                expected=declared,
                observed=actual,
                why_it_matters=(
                    "Spatial index consumers use the declared bbox to skip files."
                    " An underestimated bbox causes silent data loss in range queries."
                ),
                suggestion=(
                    "Re-export the file so the bbox metadata fully encloses all geometries."
                ),
            )
        if declared_too_loose:
            return CheckResult(
                check=self.name,
                status="warn",
                severity="warn",
                message=(
                    f"Declared bbox {fmt_declared} is larger than the actual geometry"
                    f" extent {fmt_actual} — metadata overstates coverage."
                ),
                expected=declared,
                observed=actual,
                why_it_matters=(
                    "An overstated bbox means files will be opened unnecessarily during"
                    " spatial filtering, reducing query performance."
                ),
                suggestion=(
                    "Update the GeoParquet bbox metadata to match the actual geometry extent."
                ),
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"Declared bbox {fmt_declared} matches actual geometry bounds.",
        )


def run_bounds_checks(
    info: DatasetInfo,
    contract: Contract | None = None,
) -> list[CheckResult]:
    return [
        c.run(info, contract)
        for c in [BoundsAvailableCheck(), BoundsWithinCheck(), BboxConsistencyCheck()]
    ]
