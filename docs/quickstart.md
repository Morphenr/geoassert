# Quickstart

This guide walks through the typical `geoassert` workflow: profile a dataset, generate a contract, validate it, and integrate with CI.

## 1. Install

```bash
pip install "geoassert[shapely]"
```

The `shapely` extra enables geometry validity, type, and bbox consistency checks. Everything else (CRS, bounds, attributes, GeoParquet metadata) works with the base install.

## 2. Profile your dataset

`geoassert profile` gives you a quick summary of your dataset without writing a contract.

```bash
geoassert profile data/buildings.parquet
```

```
──────────────────────── buildings.parquet ────────────────────────
  Rows:           120,000
  Columns:        5
  Geometry col:   geometry
  Geometry types: ['Polygon']
  CRS:            EPSG:4326
  Bounds:         [-0.51, 51.28, 0.33, 51.69]
```

As JSON:

```bash
geoassert profile data/buildings.parquet --format json
```

## 3. Generate a starter contract

```bash
geoassert init-contract data/buildings.parquet > contracts/buildings.yml
```

The generated contract captures the observed CRS, geometry types, bounds, and column types. Edit it to tighten the constraints before committing.

```yaml
geoassert_version: "0.1"
dataset: buildings

geometry:
  column: geometry
  type:
    - Polygon
  crs: EPSG:4326
  valid: true
  allow_empty: false

bounds:
  within:
    bbox: [-1.0, 51.0, 1.0, 52.0]

attributes:
  building_id:
    nullable: false
    unique: true
  height_m:
    nullable: true
    min: 0
    max: 400
```

## 4. Validate

```bash
geoassert validate data/buildings.parquet --contract contracts/buildings.yml
```

```
──────────────────────── buildings.parquet ────────────────────────
  PASS  geoparquet.geo_metadata
  PASS  geoparquet.primary_column
  PASS  geoparquet.column_in_schema
  PASS  geoparquet.encoding
  PASS  geoparquet.crs_parseable
  PASS  geoparquet.geometry_types
  PASS  geoparquet.row_group_stats
  PASS  crs.exists
  PASS  crs.match
  PASS  bounds.available
  PASS  bounds.within
  PASS  bounds.bbox_consistency
  PASS  attributes.building_id.exists
  PASS  attributes.building_id.nullable
  PASS  attributes.building_id.unique
  PASS  attributes.height_m.exists
  PASS  attributes.height_m.nullable
  PASS  attributes.height_m.range

All checks passed.
```

Exit code `0` on success, `1` on any failures.

## 5. Validate a directory

Pass a directory to validate every `.parquet` file inside it, including partition-level checks:

```bash
geoassert validate data/partitioned/ --contract contracts/buildings.yml
```

## 6. Check GeoParquet metadata only

```bash
geoassert geoparquet check data/buildings.parquet
```

This runs metadata-only checks without needing a contract — useful for a quick sanity check on any GeoParquet file.

## 7. Output formats

```bash
# Machine-readable JSON
geoassert validate data/buildings.parquet --contract contracts/buildings.yml --format json

# Markdown report
geoassert validate data/buildings.parquet --contract contracts/buildings.yml --format markdown

# GitHub Actions annotations
geoassert validate data/buildings.parquet --contract contracts/buildings.yml --format github

# JUnit XML (for CI test reporters)
geoassert validate data/buildings.parquet --contract contracts/buildings.yml --format junit
```

## 8. Python API

```python
import geoassert as ga

result = ga.validate(
    "data/buildings.parquet",
    contract="contracts/buildings.yml",
)

print(f"Passed: {result.passed}")
print(f"Failures: {len(result.failures)}")
print(f"Warnings: {len(result.warnings)}")

for check in result.checks:
    print(f"  {check.status.upper():4}  {check.check}")

# Render as Markdown
print(result.to_markdown())

# Inspect a specific failure
for f in result.failures:
    print(f.check, "—", f.message)
    if f.suggestion:
        print("  Suggestion:", f.suggestion)
```
