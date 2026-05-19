"""GeoParquet metadata checks (no extras required)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from geoassert.checks.base import BaseCheck
from geoassert.result import CheckResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo

_KNOWN_ENCODINGS = {"WKB", "WKT", "point", "linestring", "polygon",
                    "multipoint", "multilinestring", "multipolygon",
                    "geometrycollection"}


class GeoMetadataCheck(BaseCheck):
    name = "geoparquet.geo_metadata"

    def run(self, info: "DatasetInfo", contract: "Contract | None" = None) -> CheckResult:
        if info.geo_metadata is None:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message="No 'geo' key found in Parquet file metadata.",
                expected="geo metadata key present",
                observed="absent",
                why_it_matters="Without geo metadata, downstream tools cannot discover the geometry column or CRS.",
                suggestion="Ensure the file was written as GeoParquet (e.g. via geopandas.to_parquet or lonboard).",
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message="GeoParquet geo metadata is present.",
        )


class PrimaryColumnCheck(BaseCheck):
    name = "geoparquet.primary_column"

    def run(self, info: "DatasetInfo", contract: "Contract | None" = None) -> CheckResult:
        if info.geo_metadata is None:
            return CheckResult(check=self.name, status="skip", severity="info",
                               message="Skipped: no geo metadata.")
        primary = info.geo_metadata.get("primary_column")
        if not primary:
            return CheckResult(
                check=self.name, status="fail", severity="error",
                message="No primary_column declared in geo metadata.",
                suggestion="Ensure the GeoParquet writer sets the primary_column field.",
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message=f"Primary column: {primary!r}.",
        )


class ColumnInSchemaCheck(BaseCheck):
    name = "geoparquet.column_in_schema"

    def run(self, info: "DatasetInfo", contract: "Contract | None" = None) -> CheckResult:
        if info.geo_metadata is None:
            return CheckResult(check=self.name, status="skip", severity="info",
                               message="Skipped: no geo metadata.")
        columns = info.geo_metadata.get("columns", {})
        schema_names = set(info.schema.names)
        missing = [col for col in columns if col not in schema_names]
        if missing:
            return CheckResult(
                check=self.name, status="fail", severity="error",
                message="Geometry column(s) declared in geo metadata not found in Parquet schema.",
                observed=missing,
                suggestion="Ensure geometry column names in geo metadata match the actual Parquet schema.",
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message="All declared geometry columns are present in schema.",
        )


class EncodingCheck(BaseCheck):
    name = "geoparquet.encoding"

    def run(self, info: "DatasetInfo", contract: "Contract | None" = None) -> CheckResult:
        if info.geo_metadata is None:
            return CheckResult(check=self.name, status="skip", severity="info",
                               message="Skipped: no geo metadata.")
        columns = info.geo_metadata.get("columns", {})
        unknown = {
            col: meta.get("encoding", "")
            for col, meta in columns.items()
            if meta.get("encoding", "").upper() not in {e.upper() for e in _KNOWN_ENCODINGS}
        }
        if unknown:
            return CheckResult(
                check=self.name, status="warn", severity="warn",
                message=f"Unrecognised geometry encoding(s): {unknown}",
                suggestion="Check that the encoding field uses a recognised GeoParquet encoding.",
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message="All geometry encodings are recognised.",
        )


class CRSParseableCheck(BaseCheck):
    name = "geoparquet.crs_parseable"

    def run(self, info: "DatasetInfo", contract: "Contract | None" = None) -> CheckResult:
        if info.geo_metadata is None:
            return CheckResult(check=self.name, status="skip", severity="info",
                               message="Skipped: no geo metadata.")
        columns = info.geo_metadata.get("columns", {})
        missing_crs = [col for col, meta in columns.items() if not meta.get("crs")]
        if missing_crs:
            return CheckResult(
                check=self.name, status="warn", severity="warn",
                message=f"CRS metadata missing or empty for column(s): {missing_crs}",
                suggestion=(
                    "Include CRS metadata in GeoParquet output to ensure interoperability. "
                    "If the dataset is intentionally CRS-less, this warning can be suppressed."
                ),
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message="CRS metadata is present for all geometry columns.",
        )


class GeometryTypeMetaCheck(BaseCheck):
    name = "geoparquet.geometry_types"

    def run(self, info: "DatasetInfo", contract: "Contract | None" = None) -> CheckResult:
        if info.geo_metadata is None:
            return CheckResult(check=self.name, status="skip", severity="info",
                               message="Skipped: no geo metadata.")
        columns = info.geo_metadata.get("columns", {})
        empty_type_cols = [
            col for col, meta in columns.items()
            if "geometry_types" in meta and not meta["geometry_types"]
        ]
        if empty_type_cols:
            return CheckResult(
                check=self.name, status="warn", severity="warn",
                message=f"geometry_types is an empty list for column(s): {empty_type_cols}",
                suggestion=(
                    "Declare the expected geometry types in the GeoParquet metadata "
                    "to enable type validation by downstream tools."
                ),
            )
        return CheckResult(
            check=self.name, status="pass", severity="info",
            message="geometry_types metadata looks plausible.",
        )


def run_metadata_checks(
    info: "DatasetInfo",
    contract: "Contract | None" = None,
) -> list[CheckResult]:
    """Run all GeoParquet metadata checks and return results."""
    checks: list[BaseCheck] = [
        GeoMetadataCheck(),
        PrimaryColumnCheck(),
        ColumnInSchemaCheck(),
        EncodingCheck(),
        CRSParseableCheck(),
        GeometryTypeMetaCheck(),
    ]
    return [c.run(info, contract) for c in checks]
