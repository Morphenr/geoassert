# geoassert — Project Brief

## One-line concept

`geoassert` is a Python library and CLI for contract-based validation of geospatial data pipelines.

## Core positioning

`geoassert` should be:

> Data contracts for geospatial datasets.

It should validate geospatial pipeline outputs before bad data reaches downstream maps, models, analytics, dashboards, or warehouse tables.

The package should focus on production data engineering workflows, not exploratory GIS analysis.

## Target users

Primary users:

- Data engineers working with geospatial datasets
- Analytics engineers using dbt or warehouse-native spatial data
- Python developers building geospatial ETL pipelines
- ML/data science teams using spatial features
- Teams publishing or consuming GeoParquet datasets

Secondary users:

- GIS analysts who need repeatable validation
- Open data maintainers
- Cloud-native geospatial practitioners

## Main use case

A user has a geospatial dataset, such as a GeoParquet file, and wants to assert that it satisfies a contract:

```bash
geoassert validate data/buildings.parquet --contract contracts/buildings.yml
```

The command should return:

- clear pass/fail status
- human-readable CLI output
- machine-readable JSON
- optional Markdown report
- CI-friendly exit codes
- actionable error messages

## Product promise

`geoassert` validates:

- geometry column presence
- geometry type
- geometry validity
- empty geometries
- CRS metadata
- spatial bounds
- GeoParquet metadata
- nulls and duplicates
- attribute-level constraints
- spatial coverage and drift in later versions

## Why this project should exist

Existing Python geospatial libraries are strong for analysis and transformation.

Examples:

- GeoPandas: geospatial dataframe operations
- Shapely: geometry operations
- PyProj: coordinate reference systems
- PyArrow: Parquet/Arrow support
- DuckDB Spatial: local SQL-based spatial analysis
- GeoParquet: cloud-native geospatial file format
- Great Expectations / Pandera: general data validation

However, there is a gap for a small, practical, CI-friendly tool focused specifically on geospatial data contracts.

`geoassert` should not try to replace GeoPandas, Shapely, DuckDB, Pandera, Great Expectations, or dbt.

It should sit above them as a validation layer.

## Design principles

### 1. Contract-first

The main abstraction is a geospatial data contract.

Example contract:

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
    country: GB

attributes:
  building_id:
    nullable: false
    unique: true
  height_m:
    nullable: true
    min: 0
    max: 400
```

### 2. CLI-first, Python-friendly

The package should be usable from both command line and Python.

CLI examples:

```bash
geoassert profile data/buildings.parquet
geoassert init-contract data/buildings.parquet > contracts/buildings.yml
geoassert validate data/buildings.parquet --contract contracts/buildings.yml
geoassert geoparquet check data/buildings.parquet
```

Python examples:

```python
import geoassert as ga

result = ga.validate(
    "data/buildings.parquet",
    contract="contracts/buildings.yml",
)

assert result.passed
```

### 3. CI-native

`geoassert` should be easy to run in GitHub Actions, pre-commit, and other CI systems.

Example GitHub Actions usage:

```yaml
- name: Validate geospatial datasets
  run: geoassert validate data/*.parquet --contract contracts/*.yml --format github
```

The tool should support:

- deterministic exit codes
- JSON output
- Markdown output
- GitHub annotations
- JUnit XML later
- HTML reports later

Suggested exit codes:

| Code | Meaning |
|---:|---|
| 0 | all checks passed |
| 1 | validation failures |
| 2 | invalid contract/configuration |
| 3 | unreadable input data |
| 4 | internal error |

### 4. GeoParquet-native

GeoParquet should be the flagship format.

Initial GeoParquet checks should include:

- `geo` metadata exists
- primary geometry column exists
- geometry column exists in the Parquet schema
- encoding is valid or recognised
- CRS metadata is present and parseable
- declared geometry types match observed geometry types
- dataset-level bbox exists when expected
- bbox metadata is consistent with actual data where feasible
- row group bbox/statistics checks later

Example command:

```bash
geoassert geoparquet check data/buildings.parquet
```

### 5. Lightweight by default

Avoid making the default install too heavy.

Suggested extras:

```bash
pip install geoassert
pip install "geoassert[geopandas]"
pip install "geoassert[duckdb]"
pip install "geoassert[polars]"
pip install "geoassert[dbt]"
pip install "geoassert[all]"
```

Suggested dependency layers:

| Layer | Purpose |
|---|---|
| core | contracts, CLI, reporting, Parquet metadata |
| shapely extra | geometry parsing and validity |
| geopandas extra | broad file format support |
| duckdb extra | scalable local spatial SQL checks |
| polars extra | high-performance dataframe checks |
| dbt extra | dbt integration later |

### 6. Actionable errors

Every failed check should explain:

- what failed
- what was expected
- what was observed
- why it matters
- suggested fix
- severity
- affected row count where available

Example failure:

```json
{
  "check": "geometry.crs",
  "status": "fail",
  "severity": "error",
  "expected": "EPSG:4326",
  "observed": "OGC:CRS84",
  "message": "CRS metadata differs from contract.",
  "why_it_matters": "Coordinate axis order and downstream spatial operations may behave differently.",
  "suggestion": "Normalise CRS metadata before export or set allow_equivalent_crs=true if intentional."
}
```

### 7. Warnings versus failures

Not every issue should fail a pipeline.

Contracts should support severity levels.

Example:

```yaml
geometry:
  valid:
    enabled: true
    severity: error
  mixed_types:
    enabled: true
    severity: warn
  empty:
    enabled: true
    severity: error
```

Suggested default severities:

| Issue | Default severity |
|---|---|
| missing geometry column | error |
| unreadable file | error |
| invalid GeoParquet metadata | error |
| wrong CRS | error |
| invalid geometries | error |
| empty geometries | error or warning |
| mixed geometry types | warning |
| missing bbox metadata | warning |
| bbox inconsistent with data | error |
| duplicate geometries | warning |
| suspicious lat/lon swap | warning |

### 8. Validation-first, repair-later

The initial project should validate and explain.

It should not silently repair data.

Repair commands can come later and must be explicit.

Possible later command:

```bash
geoassert repair data/buildings.parquet --method make-valid --out data/buildings_fixed.parquet
```

## MVP scope

Version 0.1 should include:

### CLI commands

```bash
geoassert profile <path>
geoassert init-contract <path>
geoassert validate <path> --contract <contract.yml>
geoassert geoparquet check <path>
```

### Supported input

Start with:

- GeoParquet
- regular Parquet with WKB geometry column if practical

Add later:

- GeoJSON
- FlatGeobuf
- GeoPackage
- Shapefile
- PostGIS
- DuckDB tables
- cloud object stores

### Core checks

Version 0.1 checks:

- file can be opened
- row count
- geometry column exists
- geometry type distribution
- CRS detected
- CRS equals expected CRS
- empty geometry count
- invalid geometry count
- total bounds
- bounds within expected bbox/country if configured
- attribute null checks
- attribute uniqueness checks
- attribute min/max checks
- GeoParquet metadata validity
- output JSON report
- output Markdown report

### Contract generation

Provide a command to generate a starter contract from an existing dataset:

```bash
geoassert init-contract data/buildings.parquet > contracts/buildings.yml
```

This should infer:

- dataset name
- format
- geometry column
- observed CRS
- observed geometry types
- row count
- observed bounds
- candidate unique columns
- nullable columns
- numeric column ranges

Generated contracts should be conservative and editable.

## Later roadmap

### Version 0.2

- stronger YAML schema validation
- GitHub Actions output
- pre-commit hook
- JUnit XML output
- richer Markdown reports
- sampling support for large files
- configurable severity

### Version 0.3

- DuckDB backend
- directory/dataset validation
- partition validation
- row group metadata checks
- bbox consistency checks
- cloud path support

### Version 0.4

- dbt package or dbt macros
- warehouse-native spatial tests
- PostGIS support
- BigQuery GIS support
- Snowflake support

### Version 0.5

- spatial drift checks
- H3 coverage checks
- spatial train/test leakage checks
- modelling-oriented checks
- HTML reports

## Suggested package architecture

```text
geoassert/
  __init__.py
  cli.py
  contracts/
    __init__.py
    schema.py
    loader.py
  checks/
    __init__.py
    base.py
    geometry.py
    crs.py
    bounds.py
    attributes.py
    geoparquet.py
  engines/
    __init__.py
    pyarrow.py
    shapely.py
    duckdb.py
    geopandas.py
  reports/
    __init__.py
    json.py
    markdown.py
    github.py
  profiling/
    __init__.py
    profiler.py
  exceptions.py
  result.py
```

## Suggested public API

```python
from geoassert import validate, profile, load_contract

contract = load_contract("contracts/buildings.yml")
result = validate("data/buildings.parquet", contract=contract)

if not result.passed:
    print(result.to_markdown())
```

Possible result model:

```python
class ValidationResult:
    passed: bool
    failures: list[CheckResult]
    warnings: list[CheckResult]
    stats: dict

    def to_json(self) -> str: ...
    def to_markdown(self) -> str: ...
```

Possible check result model:

```python
class CheckResult:
    check: str
    status: Literal["pass", "warn", "fail", "skip"]
    severity: Literal["info", "warn", "error"]
    message: str
    expected: Any | None
    observed: Any | None
    affected_rows: int | None
    suggestion: str | None
```

## Important checks to implement early

### Geometry checks

- geometry column exists
- allowed geometry type
- no empty geometries
- valid geometries
- no null geometries
- optional duplicate geometry ratio
- optional min/max area
- optional min/max length

### CRS checks

- CRS exists
- CRS matches expected CRS
- CRS is parseable
- optional equivalent CRS handling
- warning for likely lat/lon swap

### Bounds checks

- dataset bounds available
- dataset bounds within expected bbox
- row-level geometries inside expected bbox
- country/region preset later

### Attribute checks

- required columns exist
- nullable / non-nullable
- uniqueness
- min/max for numeric fields
- allowed values
- regex/pattern checks later

### GeoParquet checks

- file is valid Parquet
- `geo` metadata exists
- primary geometry column declared
- geometry column exists
- geometry encoding is recognised
- CRS metadata parseable
- geometry type metadata plausible
- bbox metadata present if required
- bbox metadata consistent with observed bounds

## Documentation requirements

The README should immediately show:

1. what problem `geoassert` solves
2. install command
3. one simple validation command
4. one contract example
5. one failing output example
6. GitHub Actions usage
7. Python API usage
8. roadmap

Suggested README opening:

```markdown
# geoassert

Data contracts for geospatial pipelines.

`geoassert` validates GeoParquet and other geospatial datasets before bad geometry, CRS mistakes, broken metadata or spatial coverage gaps reach downstream maps, models and analytics.
```

## Example README command flow

```bash
pip install geoassert

geoassert profile data/buildings.parquet

geoassert init-contract data/buildings.parquet > contracts/buildings.yml

geoassert validate data/buildings.parquet --contract contracts/buildings.yml
```

## Example output

```text
Dataset: data/buildings.parquet

Rows: 1,284,920
Geometry column: geometry
Geometry types:
  Polygon: 99.8%
  MultiPolygon: 0.2%

CRS: EPSG:4326
Bounds: [-8.65, 49.86, 1.76, 60.86]

Checks:
  PASS geoparquet.metadata
  PASS geometry.column_exists
  PASS geometry.type
  PASS geometry.crs
  FAIL geometry.valid
  WARN geometry.duplicates

Failures:
  geometry.valid
    Expected: all geometries valid
    Observed: 1,284 invalid geometries
    Suggestion: inspect invalid geometries or repair explicitly with a make-valid workflow
```

## Adoption strategy

Prioritise GitHub usability.

Things that help adoption:

- simple CLI
- good README
- realistic examples
- GitHub Actions snippet
- useful failure messages
- generated starter contracts
- lightweight install
- clear roadmap
- issue templates for check requests
- public example datasets
- badges once stable

Good first examples:

- Overture Maps buildings
- OpenStreetMap extracts
- administrative boundaries
- H3-indexed mobility-style data
- sample broken GeoParquet files

## Non-goals for early versions

Do not start by building:

- a full GIS analysis library
- a GeoPandas replacement
- a spatial database
- a web UI
- automatic geometry repair
- every file format
- every warehouse integration
- a complex plugin ecosystem before core checks work

## North-star differentiator

The project should be:

> GeoParquet-native, CI-native, contract-first geospatial validation for Python data engineering workflows.

## Development priorities

1. Make `geoassert profile` useful.
2. Make `geoassert validate` deterministic.
3. Make failure messages excellent.
4. Make GeoParquet checks strong.
5. Make contracts easy to generate and edit.
6. Make CI integration frictionless.
7. Add broader engines and integrations only after the core experience is solid.
