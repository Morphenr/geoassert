# Changelog

All notable changes to geoassert will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.2.0] — Unreleased

### Added

**Stronger YAML schema validation**
- `geometry.crs` must be in `AUTHORITY:CODE` format (e.g. `EPSG:4326`)
- `geometry.type` values validated against the WKT geometry type set
- `bounds.within.bbox` must have exactly 4 values with `minx < maxx` and `miny < maxy`
- `attributes.<col>.min` must be ≤ `max` when both are provided

**Pre-commit hook**
- `.pre-commit-hooks.yaml` — `geoassert-validate` and `geoassert-geoparquet-check` hooks for use with [pre-commit](https://pre-commit.com/)

**JUnit XML output**
- `--format junit` on `geoassert validate` emits JUnit XML to stdout
- `--junit-out <path>` writes JUnit XML to a file alongside any other format (useful for GitHub Actions test reporters)

**Richer Markdown reports**
- Summary stats table: checks run / passed / warnings / failed / skipped
- Checks grouped by category (geoparquet, crs, bounds, geometry, attributes)

**Sampling support for large files**
- `--sample N` on `geoassert validate` limits row-level checks (attributes, geometry validity/type/empty) to a random sample of N rows
- Metadata-only checks (CRS, bounds, GeoParquet metadata) always run against the full file

**Configurable severity**
- `severity:` section in contract YAML allows per-check severity overrides:
  ```yaml
  severity:
    crs.match: warn        # downgrade CRS mismatch from error to warn
    geometry.valid: error  # enforce geometry validity as an error
  ```

### Fixed
- `GeometryTypeCheck` used `shapely.get_type_id().__class__.__name__` which always returned `"int"`; fixed to use `g.geom_type`
- `_make_geo_metadata` in test helpers used `geometry_types or ["Point"]` which coerced an empty list to `["Point"]`

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
