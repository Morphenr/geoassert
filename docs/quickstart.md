# Quickstart

This guide is fully reproducible. A sample GeoParquet file and matching contract are bundled in the repository — every command below runs against them out of the box.

## 0. Get the sample files

Clone the repo to get `examples/buildings.parquet` and `examples/buildings_contract.yml`:

```bash
git clone https://github.com/Morphenr/geoassert
cd geoassert
```

Or regenerate the sample dataset yourself (requires only `pyarrow`):

```bash
python scripts/make_demo_data.py
```

## 1. Install

```bash
pip install "geoassert[shapely]"
```

The `shapely` extra enables geometry validity, type, and bbox consistency checks. Everything else (CRS, bounds, attributes, GeoParquet metadata) works with the base install.

## 2. Profile the sample dataset

```bash
geoassert profile examples/buildings.parquet
```

```
──────────────────── buildings.parquet ────────────────────────
  Rows:           120
  Columns:        4
  Geometry col:   geometry
  Geometry types: ['Polygon']
  CRS:            EPSG:4326
  Bounds:         [-0.5, 51.3, 0.201, 51.601]
```

`profile` gives you an instant summary without writing a contract — useful as a first sanity check on any GeoParquet file.

As JSON:

```bash
geoassert profile examples/buildings.parquet --format json
```

## 3. Look at the bundled contract

The file [`examples/buildings_contract.yml`](https://github.com/Morphenr/geoassert/blob/main/examples/buildings_contract.yml) was generated from the sample data and then tightened by hand:

```yaml
dataset: buildings

geometry:
  column: geometry
  type:
    - Polygon
  crs: EPSG:4326
  allow_empty: false

bounds:
  within:
    bbox: [-1.0, 51.0, 1.0, 52.0]   # Greater London area

attributes:
  building_id:
    nullable: false
    unique: true
  height_m:
    nullable: true
    min: 0
    max: 400
```

To generate a starter contract from your own data:

```bash
geoassert init-contract examples/buildings.parquet > my_contract.yml
```

## 4. Validate

```bash
geoassert validate examples/buildings.parquet --contract examples/buildings_contract.yml
```

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

The `bounds.bbox_consistency` warning means the bbox declared in the GeoParquet file metadata doesn't precisely match the actual bounding box computed from the geometries — a common metadata imprecision that's a warning, not a failure.

Exit code `0` on success (warnings do not cause failure unless you pass `--fail-on-warn`). Exit `1` on failures.

## 5. See what a failure looks like

Tighten a constraint to force a failure. Create `contracts/strict.yml`:

```yaml
dataset: buildings

geometry:
  column: geometry
  crs: EPSG:4326
  valid: true

bounds:
  within:
    bbox: [-0.1, 51.4, 0.1, 51.5]   # deliberately narrow — most buildings are outside
```

```bash
geoassert validate examples/buildings.parquet --contract contracts/strict.yml
```

```
──────────────── buildings.parquet ────────────────
  PASS  geoparquet.geo_metadata
  ...
  FAIL  bounds.within
       Expected:  all geometries within [-0.1, 51.4, 0.1, 51.5]
       Observed:  dataset bbox [-0.5, 51.3, 0.201, 51.601] extends outside the contract bbox
       Suggestion: Widen the bbox in your contract or filter the source data before export.

Failures:
  bounds.within
```

Exit code `1`.

## 6. Python API

The same validation works via Python:

```python
import geoassert as ga

result = ga.validate(
    "examples/buildings.parquet",
    contract="examples/buildings_contract.yml",
)

print(f"Passed: {result.passed}")
print(f"Checks: {len(result.checks)}")
print(f"Failures: {len(result.failures)}")

# Render a markdown report
if not result.passed:
    print(result.to_markdown())

# Inspect individual checks
for check in result.checks:
    print(f"  {check.status.upper():4}  {check.check}")

# Raise on failure
assert result.passed, f"{len(result.failures)} check(s) failed"
```

## 7. Check GeoParquet metadata only

No contract needed — runs metadata-only checks on any GeoParquet file:

```bash
geoassert geoparquet check examples/buildings.parquet
```

## 8. Validate a directory

Pass a directory to validate every `.parquet` file inside it, plus partition-level checks:

```bash
geoassert validate data/partitioned/ --contract examples/buildings_contract.yml
```

## 9. Output formats

```bash
# Machine-readable JSON
geoassert validate examples/buildings.parquet --contract examples/buildings_contract.yml --format json

# Markdown report
geoassert validate examples/buildings.parquet --contract examples/buildings_contract.yml --format markdown

# GitHub Actions annotations (::error / ::warning)
geoassert validate examples/buildings.parquet --contract examples/buildings_contract.yml --format github

# JUnit XML (for CI test reporters)
geoassert validate examples/buildings.parquet --contract examples/buildings_contract.yml --format junit
```

## 10. CI snippet

```yaml
- name: Validate GeoParquet files
  run: |
    pip install geoassert
    geoassert validate examples/buildings.parquet \
      --contract examples/buildings_contract.yml \
      --format github
```

`--format github` emits inline annotations on the Files tab of a pull request.

---

**Next steps:** [Contract reference →](contracts.md) | [All checks →](checks.md) | [CLI reference →](cli.md)
