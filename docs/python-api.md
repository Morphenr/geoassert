# Python API

## Public functions

::: geoassert.validate

::: geoassert.validate_directory

::: geoassert.profile

::: geoassert.load_contract

---

## Result types

::: geoassert.result.ValidationResult
    options:
      members:
        - passed
        - failures
        - warnings
        - checks
        - stats
        - to_dict
        - to_json
        - to_markdown

::: geoassert.result.CheckResult
    options:
      members:
        - check
        - status
        - severity
        - message
        - expected
        - observed
        - affected_rows
        - suggestion
        - why_it_matters
        - to_dict

---

## Contract model

::: geoassert.contracts.schema.Contract

---

## Usage patterns

### Basic validation

```python
import geoassert as ga

result = ga.validate(
    "data/buildings.parquet",
    contract="contracts/buildings.yml",
)

if not result.passed:
    for failure in result.failures:
        print(f"{failure.check}: {failure.message}")
        if failure.suggestion:
            print(f"  → {failure.suggestion}")
```

### Assert in tests

```python
import geoassert as ga

def test_buildings_dataset():
    result = ga.validate(
        "data/buildings.parquet",
        contract="contracts/buildings.yml",
    )
    assert result.passed, result.to_markdown()
```

### Sampling for large files

Row-level checks (geometry validity, attribute null/unique/range) can be expensive on large files. Use `sample` to limit them to a random subset while still running all metadata checks on the full file.

```python
result = ga.validate(
    "data/large.parquet",
    contract="contracts/large.yml",
    sample=50_000,
)
```

### DuckDB engine

For attribute checks on large files, the DuckDB engine avoids loading columns into memory:

```python
result = ga.validate(
    "data/large.parquet",
    contract="contracts/large.yml",
    engine="duckdb",
)
```

Requires `pip install "geoassert[duckdb]"`.

### Directory validation

```python
results = ga.validate_directory(
    "data/partitioned/",
    contract="contracts/buildings.yml",
)

# First result is the directory-level partition summary
dir_summary = results[0]
file_results = results[1:]

all_passed = all(r.passed for r in file_results)
```

### Cloud paths

Cloud URIs are supported transparently — no extra configuration needed:

```python
result = ga.validate(
    "s3://my-bucket/data/buildings.parquet",
    contract="contracts/buildings.yml",
)
```

Supported URI schemes: `s3://`, `gs://`, `az://`

### Programmatic contract

```python
from geoassert.contracts.schema import Contract

contract = Contract.model_validate({
    "dataset": "buildings",
    "geometry": {"column": "geometry", "crs": "EPSG:4326", "valid": True},
    "bounds": {"within": {"bbox": [-8.65, 49.86, 1.76, 60.86]}},
    "attributes": {
        "building_id": {"nullable": False, "unique": True},
    },
})

result = ga.validate("data/buildings.parquet", contract=contract)
```

### Working with results

```python
result = ga.validate("data/buildings.parquet", contract="contracts/buildings.yml")

# Render as Markdown
print(result.to_markdown())

# Render as JSON
import json
print(json.dumps(result.to_dict(), indent=2))

# Filter to specific categories
geo_checks = [c for c in result.checks if c.check.startswith("geometry.")]

# Summary stats
n_pass = sum(1 for c in result.checks if c.status == "pass")
n_fail = len(result.failures)
n_warn = len(result.warnings)
print(f"{n_pass} passed, {n_fail} failed, {n_warn} warnings")
```
