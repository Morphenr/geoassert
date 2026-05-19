"""CRS validation checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geoassert.checks.base import BaseCheck
from geoassert.result import CheckResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo

# Known CRS equivalence groups — each set contains mutually equivalent identifiers.
# "Equivalent" here means same datum and same coordinate space, possibly differing
# only in authority, version, or axis-order convention that tools handle consistently.
_CRS_EQUIVALENCE_GROUPS: list[frozenset[str]] = [
    # WGS 84 geographic — EPSG:4326 (lat/lon) and OGC:CRS84 (lon/lat) share the
    # same datum; GeoParquet mandates lon/lat storage regardless of the CRS label,
    # so treat them as equivalent when allow_equivalent_crs is set.
    frozenset({"EPSG:4326", "OGC:CRS84", "CRS84"}),
    # ETRS89 geographic
    frozenset({"EPSG:4258", "urn:ogc:def:crs:EPSG::4258"}),
    # Web Mercator
    frozenset({"EPSG:3857", "EPSG:900913", "EPSG:3785"}),
]

# Geographic CRS codes whose official axis order is lat-first (y,x).
# Many tools write lon/lat data under these codes anyway, but the mismatch
# creates ambiguity. We warn so users can make the intent explicit.
_LAT_FIRST_CRS: frozenset[str] = frozenset(
    {
        "EPSG:4326",
        "EPSG:4258",  # ETRS89
        "EPSG:4269",  # NAD83
        "EPSG:4167",  # NZGD2000
        "EPSG:4283",  # GDA94
        "EPSG:7844",  # GDA2020
    }
)


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


def _are_equivalent(a: str, b: str) -> bool:
    """Return True if a and b are in the same CRS equivalence group."""
    return any(a in group and b in group for group in _CRS_EQUIVALENCE_GROUPS)


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
        allow_equiv = bool(contract.geometry and contract.geometry.allow_equivalent_crs)
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
        if observed == expected:
            return CheckResult(
                check=self.name,
                status="pass",
                severity="info",
                message=f"CRS matches contract: {observed}",
            )
        if allow_equiv and _are_equivalent(observed, expected):
            return CheckResult(
                check=self.name,
                status="pass",
                severity="info",
                message=(
                    f"CRS is equivalent to contract: {observed!r} ≡ {expected!r} "
                    f"(allow_equivalent_crs: true)."
                ),
            )
        return CheckResult(
            check=self.name,
            status="fail",
            severity="error",
            message="CRS metadata differs from contract.",
            expected=expected,
            observed=observed,
            why_it_matters=(
                "Coordinate axis order and downstream spatial operations may behave differently."
            ),
            suggestion=(
                f"Normalise CRS metadata before export or set allow_equivalent_crs: true "
                f"in the contract if {observed!r} and {expected!r} are equivalent."
            ),
        )


class CRSAxisOrderCheck(BaseCheck):
    """Warn when the dataset CRS has a lat-first (y,x) axis order.

    The GeoParquet spec requires coordinates to be stored in (lon, lat) / (x, y)
    order regardless of what the CRS authority says. CRS codes like EPSG:4326
    officially declare lat-first, which creates ambiguity: data written by
    compliant tools will be lon/lat, but the CRS label suggests lat/lon to
    readers that honour the EPSG axis order. Flagging this prompts teams to
    either switch to OGC:CRS84 (which explicitly declares lon/lat) or add a
    comment in their pipeline.
    """

    name = "crs.axis_order"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        observed = _observed_crs(info)
        if not observed:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no CRS detected.",
            )
        if observed in _LAT_FIRST_CRS:
            return CheckResult(
                check=self.name,
                status="warn",
                severity="warn",
                message=(
                    f"{observed!r} officially declares a lat-first (y, x) axis order, "
                    f"but GeoParquet requires coordinates in (lon, lat) / (x, y) order."
                ),
                observed=observed,
                why_it_matters=(
                    "Tools that honour the EPSG axis order will swap x and y coordinates, "
                    "causing silent misplacement of geometries."
                ),
                suggestion=(
                    "Use OGC:CRS84 instead of EPSG:4326 to make the lon/lat axis order "
                    "unambiguous, or add allow_equivalent_crs: true if both labels are "
                    "used in your pipeline."
                ),
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"CRS {observed!r} has unambiguous (x, y) / (lon, lat) axis order.",
        )


def run_crs_checks(
    info: DatasetInfo,
    contract: Contract | None = None,
) -> list[CheckResult]:
    return [c.run(info, contract) for c in [CRSExistsCheck(), CRSMatchCheck(), CRSAxisOrderCheck()]]
