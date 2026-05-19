# Changelog

All notable changes to geoassert will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.1.0] — Unreleased

Initial release.

### Added

**CLI commands**
- `geoassert profile <path>` — profile a GeoParquet dataset (rows, columns, CRS, bounds, geometry types)
- `geoassert init-contract <path>` — generate a conservative starter contract YAML from an existing dataset
- `geoassert validate <path> --contract <contract.yml>` — validate a dataset against a contract with exit codes, JSON, Markdown, and GitHub Actions output formats
- `geoassert geoparquet check <path>` — standalone GeoParquet metadata check

**Checks**
- `geoparquet.geo_metadata` — geo metadata key present in Parquet file
- `geoparquet.primary_column` — primary geometry column declared
- `geoparquet.column_in_schema` — declared geometry columns present in Parquet schema
- `geoparquet.encoding` — geometry encoding is a recognised GeoParquet encoding
- `geoparquet.crs_parseable` — CRS metadata present and non-empty
- `geoparquet.geometry_types` — geometry_types metadata plausible
- `crs.exists` — CRS can be detected from dataset metadata
- `crs.match` — observed CRS matches contract
- `bounds.available` — bbox metadata present in GeoParquet column metadata
- `bounds.within` — dataset bounds within contract bbox
- `geometry.column_exists` — geometry column present in schema
- `geometry.valid` — all geometries valid (requires `shapely` extra)
- `geometry.empty` — no empty geometries (requires `shapely` extra)
- `geometry.type` — observed geometry types match contract allow-list (requires `shapely` extra)
- `attributes.<col>.exists` — required column present
- `attributes.<col>.nullable` — non-nullable columns have no null values
- `attributes.<col>.unique` — unique columns have no duplicate values
- `attributes.<col>.range` — numeric columns within min/max bounds

**Output formats**
- Text (default, Rich-formatted)
- JSON (`--format json`)
- Markdown (`--format markdown`)
- GitHub Actions annotations (`--format github`)

**Python API**
- `geoassert.validate(path, contract)` → `ValidationResult`
- `geoassert.profile(path)` → `dict`
- `geoassert.load_contract(path)` → `Contract`

**Contract schema**
- `geometry` — column, type, CRS, validity, empty, null constraints
- `bounds.within` — bbox constraint
- `attributes` — per-column nullable, unique, min, max

**Extras**
- `geoassert[shapely]` — geometry validity and type checks
- `geoassert[geopandas]` — GeoPandas engine
- `geoassert[duckdb]` — DuckDB spatial engine
- `geoassert[polars]` — Polars engine (planned)
- `geoassert[all]` — all optional extras

[Unreleased]: https://github.com/Morphenr/geoassert/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Morphenr/geoassert/releases/tag/v0.1.0
