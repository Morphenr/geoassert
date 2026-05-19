"""Geometry validity and type checks (requires geoassert[shapely])."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geoassert.checks.base import BaseCheck
from geoassert.result import CheckResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo


class GeometryColumnExistsCheck(BaseCheck):
    name = "geometry.column_exists"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        col = contract.geometry.column if contract and contract.geometry else "geometry"
        if col not in info.schema.names:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message=f"Geometry column {col!r} not found in dataset.",
                expected=col,
                observed=info.schema.names,
                suggestion=f"Check the column name. Available columns: {info.schema.names}",
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"Geometry column {col!r} found.",
        )


class GeometryTypeCheck(BaseCheck):
    name = "geometry.type"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        if not (contract and contract.geometry and contract.geometry.type):
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no geometry.type constraint in contract.",
            )

        from geoassert.engines.pyarrow import read_table_for_check
        from geoassert.engines.shapely import wkb_column_to_geometries

        col = contract.geometry.column
        table = read_table_for_check(info, columns=[col])
        geoms = wkb_column_to_geometries(table.column(col))

        observed_types: set[str] = set()
        for g in geoms:
            if g is not None:
                observed_types.add(g.geom_type)

        allowed = set(contract.geometry.type)
        disallowed = observed_types - allowed
        if disallowed:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message="Geometry types outside the allowed set observed.",
                expected=sorted(allowed),
                observed=sorted(observed_types),
                suggestion=(
                    f"Update the contract type list or filter/convert geometries:"
                    f" {sorted(disallowed)}"
                ),
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"All geometry types within allowed set: {sorted(allowed)}.",
        )


class GeometryValidCheck(BaseCheck):
    name = "geometry.valid"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        from geoassert.engines.pyarrow import read_table_for_check
        from geoassert.engines.shapely import count_invalid, wkb_column_to_geometries

        col = contract.geometry.column if contract and contract.geometry else "geometry"
        if col not in info.schema.names:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message=f"Skipped: column {col!r} not in schema.",
            )

        table = read_table_for_check(info, columns=[col])
        geoms = wkb_column_to_geometries(table.column(col))
        n_invalid = count_invalid(geoms)

        if n_invalid > 0:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message=f"{n_invalid:,} invalid geometr{'y' if n_invalid == 1 else 'ies'} found.",
                expected="all geometries valid",
                observed=f"{n_invalid:,} invalid",
                affected_rows=n_invalid,
                suggestion=(
                    "Inspect invalid geometries or repair them explicitly"
                    " with a make-valid workflow."
                    " Run: geoassert repair --method make-valid (future command)."
                ),
                why_it_matters=(
                    "Invalid geometries cause silent errors in spatial joins,"
                    " area calculations, and map rendering."
                ),
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message="All geometries are valid.",
        )


class GeometryEmptyCheck(BaseCheck):
    name = "geometry.empty"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        allow_empty = contract.geometry.allow_empty if contract and contract.geometry else False
        col = contract.geometry.column if contract and contract.geometry else "geometry"
        if col not in info.schema.names:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message=f"Skipped: column {col!r} not in schema.",
            )

        from geoassert.engines.pyarrow import read_table_for_check
        from geoassert.engines.shapely import count_empty, wkb_column_to_geometries

        table = read_table_for_check(info, columns=[col])
        geoms = wkb_column_to_geometries(table.column(col))
        n_empty = count_empty(geoms)

        if n_empty > 0 and not allow_empty:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message=f"{n_empty:,} empty geometr{'y' if n_empty == 1 else 'ies'} found.",
                expected="no empty geometries",
                observed=f"{n_empty:,} empty",
                affected_rows=n_empty,
                suggestion=(
                    "Filter out empty geometries before export"
                    " or set allow_empty: true in the contract."
                ),
            )
        if n_empty > 0:
            return CheckResult(
                check=self.name,
                status="warn",
                severity="warn",
                message=(
                    f"{n_empty:,} empty geometr{'y' if n_empty == 1 else 'ies'}"
                    " found (allow_empty=true)."
                ),
                affected_rows=n_empty,
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message="No empty geometries.",
        )


class GeometryDimensionsCheck(BaseCheck):
    """Check whether geometry coordinates have Z (3D) dimensions.

    Parses WKB geometry type bytes directly — no shapely required.
    Handles both ISO WKB (Z types are 1001-1007) and EWKB (high bit flag).
    """

    name = "geometry.has_z"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        expected_dims = contract.geometry.dimensions if contract and contract.geometry else "any"
        col = contract.geometry.column if contract and contract.geometry else "geometry"

        if expected_dims == "any":
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no geometry.dimensions constraint in contract.",
            )
        if col not in info.schema.names:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message=f"Skipped: column {col!r} not in schema.",
            )

        from geoassert.engines.pyarrow import read_table_for_check

        table = read_table_for_check(info, columns=[col])
        col_array = table.column(col)

        has_z_count = 0
        total = 0
        for chunk in col_array.chunks:
            for val in chunk:
                if val.is_valid and val.as_py() is not None:
                    wkb: bytes = val.as_py()
                    if _wkb_has_z(wkb):
                        has_z_count += 1
                    total += 1

        if expected_dims == "2D" and has_z_count > 0:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message=f"{has_z_count:,} of {total:,} geometries have Z coordinates (3D).",
                expected="2D geometries (no Z)",
                observed=f"{has_z_count:,} geometries with Z",
                affected_rows=has_z_count,
                suggestion=(
                    "Drop Z coordinates before export, or set geometry.dimensions: '3D' "
                    "or 'any' in the contract."
                ),
            )
        if expected_dims == "3D" and has_z_count < total:
            missing = total - has_z_count
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message=f"{missing:,} of {total:,} geometries are 2D (missing Z coordinates).",
                expected="3D geometries (all with Z)",
                observed=f"{missing:,} 2D geometries",
                affected_rows=missing,
                suggestion=(
                    "Add Z coordinates before export, or set geometry.dimensions: '2D' "
                    "or 'any' in the contract."
                ),
            )
        z_status = "3D" if has_z_count == total else "2D"
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"Geometry dimensions match contract: all geometries are {z_status}.",
        )


class GeometryAntimeridianCheck(BaseCheck):
    """Warn if the dataset bbox suggests geometries may cross the antimeridian.

    Uses metadata only — reads the declared bbox from GeoParquet column metadata.
    A dataset whose declared bbox spans more than 180 degrees of longitude, or
    whose minx and maxx lie on opposite sides of the ±170° threshold, is flagged.
    This is a heuristic; the check is skipped for non-file sources and when no
    bbox metadata is present.
    """

    name = "geometry.antimeridian"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        if not info.geo_metadata:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no geo metadata available.",
            )
        primary = info.geo_metadata.get("primary_column")
        if not primary:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no primary geometry column declared.",
            )
        bbox = info.geo_metadata.get("columns", {}).get(primary, {}).get("bbox")
        if not bbox or len(bbox) < 4:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: no bbox in column metadata.",
            )
        minx, _miny, maxx, _maxy = bbox[0], bbox[1], bbox[2], bbox[3]
        lon_span = maxx - minx
        # Heuristic: either the span exceeds 180°, or data sits in both far-west
        # (<-150°) and far-east (>150°) simultaneously.
        crosses = lon_span > 180 or (minx < -150 and maxx > 150)
        if crosses:
            return CheckResult(
                check=self.name,
                status="warn",
                severity="warn",
                message=(
                    f"Dataset bbox [{minx:.3f}, …, {maxx:.3f}] may cross the antimeridian "
                    f"(longitude span {lon_span:.1f}°)."
                ),
                observed=f"bbox minx={minx}, maxx={maxx}, span={lon_span:.1f}°",
                why_it_matters=(
                    "Geometries that cross ±180° longitude are often rendered incorrectly "
                    "as continent-spanning bands. Spatial joins and area calculations "
                    "will also produce wrong results."
                ),
                suggestion=(
                    "Split geometries at the antimeridian, or verify that the bbox "
                    "reflects intentional global coverage rather than a wrapping artefact."
                ),
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"Dataset bbox does not suggest antimeridian crossing (span {lon_span:.1f}°).",
        )


def _wkb_has_z(wkb: bytes) -> bool:
    """Return True if the WKB geometry encodes Z coordinates."""
    if len(wkb) < 5:
        return False
    byte_order = wkb[0]
    if byte_order == 1:  # little-endian
        geom_type = int.from_bytes(wkb[1:5], "little")
    else:  # big-endian
        geom_type = int.from_bytes(wkb[1:5], "big")
    # EWKB: Z flag in high bit
    if geom_type & 0x80000000:
        return True
    # ISO WKB: Z types are 1001-1007 (base + 1000), ZM are 3001-3007 (base + 3000)
    base = geom_type & 0xFFFF
    return 1001 <= base <= 1007 or 3001 <= base <= 3007


def run_geometry_checks(
    info: DatasetInfo,
    contract: Contract | None = None,
) -> list[CheckResult]:
    checks: list[BaseCheck] = [
        GeometryColumnExistsCheck(),
        GeometryValidCheck(),
        GeometryEmptyCheck(),
        GeometryTypeCheck(),
        GeometryDimensionsCheck(),
        GeometryAntimeridianCheck(),
    ]
    return [c.run(info, contract) for c in checks]
