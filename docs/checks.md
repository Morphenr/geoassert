# Checks reference

Every check has a dot-namespaced name, a default severity, and returns one of four statuses:

| Status | Meaning |
|---|---|
| `pass` | Check succeeded |
| `warn` | Check found an issue but did not fail |
| `fail` | Check found a violation |
| `skip` | Check was not applicable (missing optional extra, no constraint in contract, etc.) |

---

## GeoParquet metadata checks

These checks run on every GeoParquet file. They read only file-level Parquet metadata — no rows are loaded.

### `geoparquet.geo_metadata`

**Default severity:** error

Verifies that the Parquet file contains a `geo` key in its file-level metadata, which is required by the [GeoParquet specification](https://geoparquet.org/).

- **Fail:** `geo` key absent from Parquet metadata
- **Pass:** `geo` key present

### `geoparquet.primary_column`

**Default severity:** error

Checks that the `primary_column` field is declared in the `geo` metadata.

- **Fail:** `primary_column` missing or empty
- **Skip:** No `geo` metadata

### `geoparquet.column_in_schema`

**Default severity:** error

Checks that every geometry column declared in `geo.columns` actually exists in the Parquet schema.

- **Fail:** One or more declared geometry columns are absent from the schema
- **Skip:** No `geo` metadata

### `geoparquet.encoding`

**Default severity:** warn

Checks that the geometry encoding for each column is a recognised GeoParquet encoding (`WKB`, `WKT`, `point`, `linestring`, etc.).

- **Warn:** Unknown encoding found
- **Pass:** All encodings recognised
- **Skip:** No `geo` metadata

### `geoparquet.crs_parseable`

**Default severity:** warn

Checks that CRS metadata is present and non-empty for each declared geometry column.

- **Warn:** CRS metadata missing or empty for one or more columns
- **Pass:** CRS present for all columns
- **Skip:** No `geo` metadata

### `geoparquet.geometry_types`

**Default severity:** warn

Checks that the `geometry_types` field in `geo` metadata is not an empty list. An empty list means downstream tools cannot discover the geometry type.

- **Warn:** `geometry_types` is an empty list for one or more columns
- **Pass:** `geometry_types` is non-empty
- **Skip:** No `geo` metadata

### `geoparquet.row_group_stats`

**Default severity:** warn

Checks that Parquet row group column statistics are present. Missing statistics disable predicate pushdown in DuckDB, BigQuery, and other query engines, causing significantly slower spatial queries.

- **Warn:** Statistics missing for one or more columns in any row group
- **Pass:** Statistics present for all columns in all row groups

---

## CRS checks

### `crs.exists`

**Default severity:** error

Checks that a CRS can be detected from the dataset's GeoParquet metadata.

- **Fail:** No CRS found
- **Pass:** CRS detected

### `crs.match`

**Default severity:** error

Checks that the observed CRS matches the `geometry.crs` value in the contract.

- **Fail:** CRS differs from contract
- **Skip:** No `geometry.crs` in contract, or no CRS in data

---

## Bounds checks

### `bounds.available`

**Default severity:** warn

Checks that a bounding box is declared in the GeoParquet column metadata (`geo.columns.<col>.bbox`). Without a declared bbox, tools cannot use metadata-level spatial filtering.

- **Warn:** No bbox in column metadata
- **Pass:** bbox present

### `bounds.within`

**Default severity:** error

Checks that the dataset's declared bbox is fully contained within the expected bbox from the contract (`bounds.within.bbox`). Uses metadata only — does not read geometry rows.

- **Fail:** Dataset bbox extends beyond contract bbox
- **Warn:** Cannot verify — no bbox in dataset metadata
- **Skip:** No `bounds.within` constraint in contract

### `bounds.bbox_consistency`

**Default severity:** warn

Compares the declared bbox in GeoParquet metadata to the actual bbox computed from geometries. A mismatch indicates stale metadata — often from incremental appends without updating the metadata.

Requires `geoassert[shapely]`.

- **Warn:** Declared bbox differs from actual computed bounds by more than 1e-6
- **Pass:** Declared and actual bounds match
- **Skip:** No declared bbox, geometry column absent, or shapely not installed

---

## Geometry checks

All geometry checks require `geoassert[shapely]`. Without it, they return `skip`.

### `geometry.column_exists`

**Default severity:** error

Checks that the geometry column named in the contract (default: `geometry`) exists in the schema.

- **Fail:** Column not found
- **Pass:** Column present

### `geometry.valid`

**Default severity:** error

Counts geometries that fail the [DE-9IM validity criterion](https://en.wikipedia.org/wiki/DE-9IM). Invalid geometries cause silent errors in spatial joins, area calculations, and map rendering.

- **Fail:** One or more invalid geometries found (reports count)
- **Pass:** All geometries valid
- **Skip:** Geometry column absent

### `geometry.empty`

**Default severity:** error (or warn when `allow_empty: true`)

Counts empty geometries (`POINT EMPTY`, etc.).

- **Fail:** Empty geometries found and `allow_empty: false`
- **Warn:** Empty geometries found and `allow_empty: true`
- **Pass:** No empty geometries
- **Skip:** Geometry column absent

### `geometry.type`

**Default severity:** error

Checks that all observed geometry types are within the allowed set from `geometry.type` in the contract.

- **Fail:** Geometry types outside the allowed set observed
- **Pass:** All types within the allowed set
- **Skip:** No `geometry.type` constraint in contract

---

## Attribute checks

Attribute checks are named `attributes.<column>.<check>`.

### `attributes.<col>.exists`

**Default severity:** error

Checks that the column is present in the schema.

- **Fail:** Column not found

### `attributes.<col>.nullable`

**Default severity:** error

When `nullable: false`, checks that the column has no null values.

- **Fail:** Null values found
- **Pass:** No nulls, or `nullable: true`
- **Skip:** Column absent

### `attributes.<col>.unique`

**Default severity:** error

When `unique: true`, checks that all values are distinct.

- **Fail:** Duplicate values found (reports count)
- **Pass:** All values unique
- **Skip:** Column absent

### `attributes.<col>.range`

**Default severity:** error

When `min` or `max` is set, checks that the observed column minimum/maximum is within bounds.

- **Fail:** Observed min < contract min, or observed max > contract max
- **Pass:** Range within bounds
- **Skip:** Column absent or all values null

---

## Partition checks

Partition checks run automatically when validating a directory. They inspect the directory structure rather than individual file contents.

### `partitions.detected`

**Default severity:** warn (on no Hive structure), error (no files)

Checks whether the directory contains a Hive-style `col=val` partition structure.

- **Pass:** Hive partitioning detected
- **Warn:** Directory contains Parquet files but no `col=val` subdirectories
- **Fail:** No Parquet files found in the directory
- **Skip:** Path is not a directory

### `partitions.schema_consistency`

**Default severity:** error

Reads the schema from every Parquet file under the directory and checks they all match. Schema drift — where later partition files have different column names or types — is a common and difficult-to-catch pipeline bug.

- **Fail:** One or more files have a different schema from the reference (first) file
- **Pass:** All schemas match
- **Skip:** Fewer than 2 files found, or path is not a directory
