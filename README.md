# geoassert

Data contracts for geospatial pipelines.

`geoassert` validates GeoParquet and other geospatial datasets before bad geometry, CRS mistakes, broken metadata, or spatial coverage gaps reach downstream maps, models, and analytics.

![geoassert demo](demo/demo.gif)

---

## Install

```bash
pip install geoassert
```

Optional extras for richer checks:

```bash
pip install "geoassert[shapely]"    # geometry validity, type checks
pip install "geoassert[geopandas]"  # broader file format support
pip install "geoassert[duckdb]"     # scalable local spatial SQL
pip install "geoassert[all]"        # everything
```

---

## Quickstart

```bash
# Profile a dataset
geoassert profile data/buildings.parquet

# Generate a starter contract
geoassert init-contract data/buildings.parquet > contracts/buildings.yml

# Validate against a contract
geoassert validate data/buildings.parquet --contract contracts/buildings.yml

# Check GeoParquet metadata
geoassert geoparquet check data/buildings.parquet
```

---

## Example output

```
─── buildings.parquet ──────────────────────────────────────────
  PASS  geoparquet.geo_metadata
  PASS  geoparquet.primary_column
  PASS  geoparquet.column_in_schema
  PASS  geoparquet.encoding
  PASS  geoparquet.crs_parseable
  PASS  crs.exists
  PASS  crs.match
  PASS  bounds.within
  FAIL  geometry.valid
  WARN  geometry.empty

Failures:
  geometry.valid
    Expected:   all geometries valid
    Observed:   1,284 invalid geometries
    Rows:       1,284
    Suggestion: Inspect invalid geometries or repair them explicitly with a
                make-valid workflow.
```

---

## Contract example

```yaml
geoassert_version: "0.1"

dataset: buildings

source:
  path: data/buildings.parquet
  format: geoparquet

geometry:
  column: geometry
  type:
    - Polygon
    - MultiPolygon
  crs: EPSG:4326
  valid: true
  allow_empty: false

bounds:
  within:
    bbox: [-8.65, 49.86, 1.76, 60.86]   # Great Britain

attributes:
  building_id:
    nullable: false
    unique: true
  height_m:
    nullable: true
    min: 0
    max: 400
```

---

## Failure messages

Every failed check explains what failed, what was expected, what was observed, and how to fix it:

```json
{
  "check": "crs.match",
  "status": "fail",
  "severity": "error",
  "expected": "EPSG:4326",
  "observed": "OGC:CRS84",
  "message": "CRS metadata differs from contract.",
  "why_it_matters": "Coordinate axis order and downstream spatial operations may behave differently.",
  "suggestion": "Normalise CRS metadata before export or set allow_equivalent_crs: true if intentional."
}
```

---

## GitHub Actions

```yaml
- name: Validate geospatial datasets
  run: |
    pip install geoassert
    geoassert validate data/buildings.parquet \
      --contract contracts/buildings.yml \
      --format github
```

Use `--format github` to emit `::error` and `::warning` annotations in the Actions UI.

---

## Python API

```python
import geoassert as ga

result = ga.validate(
    "data/buildings.parquet",
    contract="contracts/buildings.yml",
)

if not result.passed:
    print(result.to_markdown())

assert result.passed
```

---

## Checks (v0.1)

| Category | Check |
|---|---|
| GeoParquet | geo metadata, primary column, schema consistency, encoding, CRS parseable, geometry types |
| CRS | CRS exists, CRS matches contract |
| Bounds | bounds available, dataset within expected bbox |
| Geometry | column exists, validity, empty geometries, type distribution |
| Attributes | column exists, nullable, unique, min/max range |

---

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | all checks passed |
| 1 | validation failures |
| 2 | invalid contract / configuration |
| 3 | unreadable input data |
| 4 | internal error |

---

## Roadmap

**v0.2** — GitHub Actions annotations, pre-commit hook, JUnit XML, sampling, configurable severity  
**v0.3** — DuckDB backend, cloud paths, partition validation, row group checks  
**v0.4** — dbt package, PostGIS, BigQuery GIS, Snowflake  
**v0.5** — spatial drift checks, H3 coverage, HTML reports

---

## Non-goals

`geoassert` is not a GIS analysis library, a GeoPandas replacement, or a spatial database. It sits above them as a validation layer.

---

## Contributing

Bug reports and check requests welcome — use the GitHub issue templates.

```bash
git clone https://github.com/Morphenr/geoassert
cd geoassert
uv sync --extra dev
uv run pytest
```
