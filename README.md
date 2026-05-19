# geoassert

**Validate GeoParquet files before bad data reaches production.**

`geoassert` is a Python library and CLI that runs contract-based validation on geospatial datasets — GeoParquet files, PostGIS tables, BigQuery GIS tables, Snowflake geometry columns, and dbt model outputs. It catches CRS mismatches, broken metadata, invalid geometries, out-of-bounds data, and attribute problems before they silently corrupt downstream maps, models, and analytics.

```bash
pip install geoassert
geoassert validate data/buildings.parquet --contract contracts/buildings.yml
```

![geoassert demo](https://raw.githubusercontent.com/Morphenr/geoassert/main/demo/demo.gif)

---

## Why geoassert?

Geospatial data fails in ways general-purpose validators don't understand:

- A GeoParquet file with an empty or stale bounding box in its metadata
- A CRS that looks right but has swapped lat/lon axes
- A PostGIS export where 3% of polygons are topologically invalid
- A partitioned dataset where one month quietly changed schema

`geoassert` sits above GeoPandas, Shapely, and PyArrow as a **lightweight validation layer** — fast enough to run in every CI job, specific enough to catch the problems that matter.

---

## Install

```bash
pip install geoassert
```

Optional extras for richer checks:

```bash
pip install "geoassert[shapely]"    # geometry validity and type checks
pip install "geoassert[duckdb]"     # scalable attribute checks via DuckDB SQL
pip install "geoassert[postgis]"    # validate PostGIS tables directly
pip install "geoassert[bigquery]"   # validate BigQuery GIS tables
pip install "geoassert[snowflake]"  # validate Snowflake geometry columns
pip install "geoassert[all]"        # everything
```

---

## Reproducible quickstart

A 120-row sample GeoParquet file and matching contract are bundled under `examples/` — every command below runs against them out of the box.

```bash
git clone https://github.com/Morphenr/geoassert
cd geoassert
pip install "geoassert[shapely]"

# 1. Profile the sample dataset
geoassert profile examples/buildings.parquet

# 2. Validate against the bundled contract
geoassert validate examples/buildings.parquet --contract examples/buildings_contract.yml
```

Expected output:

```
──────────────── buildings.parquet ────────────────
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
  WARN  bounds.bbox_consistency
  PASS  geometry.column_exists
  PASS  geometry.valid
  PASS  geometry.empty
  PASS  geometry.type
  PASS  attributes.building_id.exists
  PASS  attributes.building_id.nullable
  PASS  attributes.building_id.unique
  PASS  attributes.height_m.exists
  PASS  attributes.height_m.nullable
  PASS  attributes.height_m.range

All checks passed.
```

See [`examples/buildings.parquet`](examples/buildings.parquet) and [`examples/buildings_contract.yml`](examples/buildings_contract.yml).  
Full walkthrough: [Quickstart →](https://morphenr.github.io/geoassert/quickstart/)

---

## Typical workflow

```bash
# 1. Profile a dataset — no contract needed
geoassert profile examples/buildings.parquet

# 2. Generate a starter contract from the data
geoassert init-contract examples/buildings.parquet > contracts/my_buildings.yml

# 3. Edit the contract to tighten constraints, then validate
geoassert validate examples/buildings.parquet --contract examples/buildings_contract.yml

# 4. Validate a whole directory of partitioned files
geoassert validate data/partitioned/ --contract contracts/buildings.yml
```

---

## Contract format

```yaml
dataset: buildings

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

## What it checks

| Category | Checks |
|---|---|
| **GeoParquet** | geo metadata present, primary column, schema, encoding, CRS parseable, geometry types, row group statistics |
| **CRS** | CRS present, CRS matches contract |
| **Bounds** | bbox metadata present, dataset within expected bbox, declared bbox matches actual geometry bounds |
| **Geometry** | column exists, validity, empty geometries, type distribution |
| **Attributes** | column exists, nullable, unique, min/max range |
| **Partitions** | Hive structure detected, schema consistency across partition files |

---

## Warehouse support

Validate GeoParquet files, PostGIS tables, BigQuery GIS tables, and Snowflake geometry columns against the same contract format:

```bash
# PostGIS
geoassert validate postgis://user:pass@host/db/public/buildings \
  --contract contracts/buildings.yml

# BigQuery
geoassert validate bigquery://my-project/my_dataset/buildings \
  --contract contracts/buildings.yml

# Snowflake
geoassert validate snowflake://myaccount/MY_DB/PUBLIC/BUILDINGS \
  --contract contracts/buildings.yml \
  --sf-user myuser --sf-password secret
```

Or via Python:

```python
from geoassert.engines.postgis import read_postgis_info
import geoassert as ga

info = read_postgis_info("postgresql://user:pass@host/db", "buildings")
result = ga.validate_source(info, "contracts/buildings.yml")
```

---

## dbt integration

```bash
# List all models in the dbt manifest
geoassert dbt list

# Validate a specific model
geoassert dbt validate buildings \
  --contract contracts/buildings.yml \
  --dsn postgresql://user:pass@host/db
```

---

## CI integration

```yaml
- name: Validate GeoParquet files
  run: |
    pip install geoassert
    geoassert validate data/buildings.parquet \
      --contract contracts/buildings.yml \
      --format github
```

`--format github` emits `::error` and `::warning` annotations directly in the GitHub Actions UI.

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
  "suggestion": "Normalise CRS metadata before export or set allow_equivalent_crs: true if intentional."
}
```

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

| Version | Status | Highlights |
|---|---|---|
| **v0.1** | ✅ shipped | Core checks: GeoParquet, CRS, bounds, geometry, attributes |
| **v0.2** | ✅ shipped | GitHub Actions annotations, JUnit XML, sampling, configurable severity |
| **v0.3** | ✅ shipped | DuckDB backend, cloud paths (S3/GCS/Azure), partition validation, row group checks |
| **v0.4** | ✅ shipped | PostGIS, BigQuery GIS, Snowflake engines; dbt integration; `validate_source()` API |
| **v0.5** | planned | Spatial drift checks, H3 coverage validation, HTML reports |

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
