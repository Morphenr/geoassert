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
                check=self.name, status="fail", severity="error",
                message=f"Geometry column {col!r} not found in dataset.",
                expected=col,
                observed=info.schema.names,
                suggestion=f"Check the column name. Available columns: {info.schema.names}",
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message=f"Geometry column {col!r} found.",
        )


class GeometryTypeCheck(BaseCheck):
    name = "geometry.type"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        if not (contract and contract.geometry and contract.geometry.type):
            return CheckResult(check=self.name, status="skip", severity="info",
                               message="Skipped: no geometry.type constraint in contract.")

        from geoassert.engines.pyarrow import read_table
        from geoassert.engines.shapely import wkb_column_to_geometries

        col = contract.geometry.column
        table = read_table(info.path, columns=[col])
        geoms = wkb_column_to_geometries(table.column(col))

        import shapely
        observed_types: set[str] = set()
        for g in geoms:
            if g is not None:
                observed_types.add(shapely.get_type_id(g).__class__.__name__)

        allowed = set(contract.geometry.type)
        disallowed = observed_types - allowed
        if disallowed:
            return CheckResult(
                check=self.name, status="fail", severity="error",
                message="Geometry types outside the allowed set observed.",
                expected=sorted(allowed),
                observed=sorted(observed_types),
                suggestion=(
                    f"Update the contract type list or filter/convert geometries:"
                    f" {sorted(disallowed)}"
                ),
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message=f"All geometry types within allowed set: {sorted(allowed)}.",
        )


class GeometryValidCheck(BaseCheck):
    name = "geometry.valid"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        from geoassert.engines.pyarrow import read_table
        from geoassert.engines.shapely import count_invalid, wkb_column_to_geometries

        col = contract.geometry.column if contract and contract.geometry else "geometry"
        if col not in info.schema.names:
            return CheckResult(check=self.name, status="skip", severity="info",
                               message=f"Skipped: column {col!r} not in schema.")

        table = read_table(info.path, columns=[col])
        geoms = wkb_column_to_geometries(table.column(col))
        n_invalid = count_invalid(geoms)

        if n_invalid > 0:
            return CheckResult(
                check=self.name, status="fail", severity="error",
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
            check=self.name, status="pass", severity="info",
            message="All geometries are valid.",
        )


class GeometryEmptyCheck(BaseCheck):
    name = "geometry.empty"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        allow_empty = contract.geometry.allow_empty if contract and contract.geometry else False
        col = contract.geometry.column if contract and contract.geometry else "geometry"
        if col not in info.schema.names:
            return CheckResult(check=self.name, status="skip", severity="info",
                               message=f"Skipped: column {col!r} not in schema.")

        from geoassert.engines.pyarrow import read_table
        from geoassert.engines.shapely import count_empty, wkb_column_to_geometries

        table = read_table(info.path, columns=[col])
        geoms = wkb_column_to_geometries(table.column(col))
        n_empty = count_empty(geoms)

        if n_empty > 0 and not allow_empty:
            return CheckResult(
                check=self.name, status="fail", severity="error",
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
                check=self.name, status="warn", severity="warn",
                message=(
                    f"{n_empty:,} empty geometr{'y' if n_empty == 1 else 'ies'}"
                    " found (allow_empty=true)."
                ),
                affected_rows=n_empty,
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message="No empty geometries.",
        )


def run_geometry_checks(
    info: DatasetInfo,
    contract: Contract | None = None,
) -> list[CheckResult]:
    checks: list[BaseCheck] = [
        GeometryColumnExistsCheck(),
        GeometryValidCheck(),
        GeometryEmptyCheck(),
        GeometryTypeCheck(),
    ]
    return [c.run(info, contract) for c in checks]
