# geoassert

**Validate GeoParquet files before bad data reaches production.**

`geoassert` is a Python library and CLI that runs contract-based validation on geospatial datasets — GeoParquet files, PostGIS tables, BigQuery GIS tables, Snowflake geometry columns, and dbt model outputs. It catches CRS mismatches, broken metadata, invalid geometries, out-of-bounds data, and attribute problems before they silently corrupt downstream maps, models, and analytics.

```bash
pip install geoassert
geoassert validate data/buildings.parquet --contract contracts/buildings.yml
```

![geoassert demo](../demo/demo.gif)

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

Optional extras:

```bash
pip install "geoassert[shapely]"    # geometry validity and type checks
pip install "geoassert[duckdb]"     # scalable attribute checks via DuckDB SQL
pip install "geoassert[postgis]"    # validate PostGIS tables directly
pip install "geoassert[bigquery]"   # validate BigQuery GIS tables
pip install "geoassert[snowflake]"  # validate Snowflake geometry columns
pip install "geoassert[all]"        # everything
```

---

## Thirty-second example

A sample dataset and contract are bundled in the repository:

```bash
git clone https://github.com/Morphenr/geoassert
cd geoassert
pip install "geoassert[shapely]"

geoassert validate data/buildings.parquet --contract contracts/buildings.yml
```

→ Full walkthrough: [Quickstart](quickstart.md)

---

## What it checks

| Category | Checks |
|---|---|
| **GeoParquet** | geo metadata, primary column, schema, encoding, CRS parseable, geometry types, row group statistics |
| **CRS** | CRS present, CRS matches contract |
| **Bounds** | bbox metadata present, dataset within expected bbox, declared bbox matches actual geometry bounds |
| **Geometry** | column exists, validity, empty geometries, type distribution |
| **Attributes** | column exists, nullable, unique, min/max range |
| **Partitions** | Hive structure detected, schema consistency across partition files |

---

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | All checks passed |
| `1` | One or more validation failures |
| `2` | Invalid contract or configuration |
| `3` | Unreadable input data |
| `4` | Internal error |

---

## Roadmap

| Version | Status | Highlights |
|---|---|---|
| **v0.1** | ✅ shipped | Core checks: GeoParquet, CRS, bounds, geometry, attributes |
| **v0.2** | ✅ shipped | GitHub Actions annotations, JUnit XML, sampling, severity control |
| **v0.3** | ✅ shipped | DuckDB backend, cloud paths, partition validation, row group checks |
| **v0.4** | ✅ shipped | PostGIS, BigQuery GIS, Snowflake; dbt integration; `validate_source()` API |
| **v0.5** | planned | Spatial drift checks, H3 coverage validation, HTML reports |
