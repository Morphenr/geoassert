# geoassert

**Data contracts for geospatial pipelines.**

`geoassert` validates GeoParquet and other geospatial datasets before bad geometry, CRS mistakes, broken metadata, or spatial coverage gaps reach downstream maps, models, and analytics.

![geoassert demo](../demo/demo.gif)

---

## Install

```bash
pip install geoassert
```

Optional extras for richer checks:

```bash
pip install "geoassert[shapely]"    # geometry validity and type checks
pip install "geoassert[duckdb]"     # fast attribute checks via DuckDB
pip install "geoassert[geopandas]"  # broader file format support
pip install "geoassert[all]"        # everything
```

---

## Thirty-second example

```bash
# Profile a dataset
geoassert profile data/buildings.parquet

# Generate a starter contract
geoassert init-contract data/buildings.parquet > contracts/buildings.yml

# Validate against the contract
geoassert validate data/buildings.parquet --contract contracts/buildings.yml
```

```python
import geoassert as ga

result = ga.validate(
    "data/buildings.parquet",
    contract="contracts/buildings.yml",
)
if not result.passed:
    print(result.to_markdown())
```

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

## Why geoassert?

Geospatial data breaks in specific, quiet ways: a CRS that looks right but has swapped axes, an exported GeoParquet file with an empty bbox, a partitioned dataset where one month silently changed schema. General-purpose data quality tools don't understand these failure modes.

`geoassert` is not a GIS analysis library. It sits above GeoPandas, Shapely, and PyArrow as a thin validation layer — lightweight enough to run in every CI job, specific enough to catch the problems that matter in geospatial pipelines.
