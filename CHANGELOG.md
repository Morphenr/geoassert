# Changelog

All notable changes to geoassert will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.4.0] — Unreleased

### Added

**Warehouse engines** — validate tables stored in cloud databases, not just files

- `geoassert[postgis]` — new `engines/postgis.py` with `read_postgis_info(dsn, table, ...)` → `DatasetInfo`
  - Connects via psycopg2; reads CRS from `geometry_columns` view; fetches geometries as WKB via `ST_AsWKB()`
  - Handles Decimal, datetime, date, bytes, and standard scalar types in `_rows_to_arrow()`
- `geoassert[bigquery]` — new `engines/bigquery.py` with `read_bigquery_info(project, dataset, table, ...)`
  - Uses `google-cloud-bigquery`; reads GEOGRAPHY as WKB via `ST_AsWKB()`; always EPSG:4326
- `geoassert[snowflake]` — new `engines/snowflake.py` with `read_snowflake_info(account, user, password, database, schema, table, ...)`
  - Uses `snowflake-connector-python`; reads GEOMETRY via `ST_ASEWKB()` using Snowflake's `EXCLUDE` syntax

**dbt integration** (`integrations/dbt.py`)
- `find_manifest(project_dir)` — locates `target/manifest.json` or `manifest.json` in project root
- `load_manifest(path)` — parses and validates manifest JSON
- `list_models(manifest)` → sorted `list[DbtModel]` — filters to `resource_type == "model"` nodes
- `get_model(manifest, model_name)` → `DbtModel` — lookup by model name with helpful error on miss
- `validate_dbt_model(model, contract_path, *, dsn, file_path, sample, engine)` → `ValidationResult`
  - Dispatches: `file_path` → file-based validation; `dsn` → PostGIS engine + `run_validation_from_info()`

**CLI additions**
- `geoassert dbt list [--project-dir] [--format text|json]` — list all models from the dbt manifest
- `geoassert dbt validate <model> --contract <file> [--dsn] [--path]` — validate a specific dbt model
- `geoassert validate` now accepts warehouse URIs:
  - `postgis://host/db/schema/table` or `postgresql://...` — routes to PostGIS engine
  - `bigquery://project/dataset/table` — routes to BigQuery engine (`--bq-project` for project override)
  - `snowflake://account/database/schema/table` — routes to Snowflake engine (requires `--sf-user`, `--sf-password`)
  - Warehouse flags: `--dsn`, `--geom-col`, `--bq-project`, `--sf-account`, `--sf-user`, `--sf-password`, `--sf-warehouse`

**Public API**
- `geoassert.validate_source(source_info, contract)` — validates a pre-built `DatasetInfo` from a warehouse engine; the programmatic equivalent of passing a warehouse URI to `validate`

### Changed
- `DatasetInfo` gains `source_type: str = "file"` and `table: pa.Table | None = None` fields
  - `source_type` is set by warehouse engines; `run_metadata_checks()` skips GeoParquet checks when it is not `"file"`
  - `table` holds the in-memory PyArrow table fetched from a warehouse; `read_table_for_check()` uses it transparently
- `runner.run_validation()` now delegates to new `run_validation_from_info(info, contract)` — the core pipeline is now reusable by warehouse engines
- `run_validation_from_info()` stats block always includes `source_type`

---

## [0.3.0] — Unreleased

### Added

**DuckDB attribute backend**
- `geoassert[duckdb]` extra now provides a real DuckDB engine for attribute checks
- `--engine duckdb` flag on `geoassert validate` routes null/unique/range checks through DuckDB instead of loading columns into memory — much faster on large files
- DuckDB reads cloud URIs (S3, GCS) natively without intermediate downloads
- New helpers in `engines/duckdb.py`: `count_nulls()`, `count_distinct()`, `count_non_null()`, `count_total()`, `get_min_max()`

**Directory & dataset validation**
- `geoassert validate <directory> --contract <file>` now accepts a directory and validates every `*.parquet` file found under it
- Python API: `geoassert.validate_directory(path, contract, pattern, sample, engine)` → `list[ValidationResult]`
- First result in the list is a directory-level summary including partition checks

**Partition validation** (`checks/partitions.py`)
- `partitions.detected` — detects Hive `col=val` directory structure; warns when directory contains Parquet files but no Hive partitioning
- `partitions.schema_consistency` — verifies all partition files share the same schema; fails on schema drift

**Row group metadata checks**
- `geoparquet.row_group_stats` — warns when row group column statistics are missing; missing stats prevent predicate pushdown and spatial filtering optimisations

**Bbox consistency check**
- `bounds.bbox_consistency` — compares the declared bbox in GeoParquet metadata to the actual bbox computed from geometries (requires `shapely` extra); warns on mismatch

**Cloud path support**
- `read_geoparquet_info()` and `read_table()` now detect `://` URIs and resolve them via `pyarrow.fs.FileSystem.from_uri()`, enabling transparent reads from S3, GCS, and Azure Blob Storage

### Changed
- `DatasetInfo` gains an `engine: str = "pyarrow"` field; set to `"duckdb"` to enable DuckDB dispatch in attribute checks
- `DatasetInfo.path` type widened to `Path | str` to support cloud URI strings
- `run_validation()` gains an `engine: str = "pyarrow"` parameter
- `geoassert validate` gains `--engine` (`-e`) option

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
