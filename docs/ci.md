# CI integration

## GitHub Actions

### Basic validation

```yaml
- name: Validate geospatial datasets
  run: |
    pip install geoassert
    geoassert validate data/buildings.parquet \
      --contract contracts/buildings.yml
```

Exit code `1` automatically fails the step if any checks fail.

### GitHub annotations

Use `--format github` to emit inline annotations directly in the pull request diff:

```yaml
- name: Validate geospatial datasets
  run: |
    pip install "geoassert[shapely]"
    geoassert validate data/buildings.parquet \
      --contract contracts/buildings.yml \
      --format github
```

Failures appear as `::error` and warnings as `::warning` annotations in the Actions UI, linked to the relevant file paths.

### JUnit XML for test reporters

```yaml
- name: Validate geospatial datasets
  run: |
    pip install geoassert
    geoassert validate data/buildings.parquet \
      --contract contracts/buildings.yml \
      --junit-out test-results/geoassert.xml

- name: Publish test results
  uses: EnricoMi/publish-unit-test-result-action@v2
  if: always()
  with:
    files: test-results/geoassert.xml
```

### Validate a full directory

```yaml
- name: Validate partitioned dataset
  run: |
    pip install geoassert
    geoassert validate data/partitioned/ \
      --contract contracts/buildings.yml \
      --format github
```

### Cache dependencies

```yaml
- name: Install geoassert
  run: pip install "geoassert[shapely]"

- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: geoassert-${{ hashFiles('contracts/*.yml') }}
```

### Full example workflow

```yaml
name: Validate datasets

on:
  push:
    paths:
      - 'data/**'
      - 'contracts/**'
  pull_request:
    paths:
      - 'data/**'
      - 'contracts/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          lfs: true   # if data files are stored in Git LFS

      - name: Install geoassert
        run: pip install "geoassert[shapely]"

      - name: Validate buildings dataset
        run: |
          geoassert validate data/buildings.parquet \
            --contract contracts/buildings.yml \
            --format github \
            --junit-out test-results/buildings.xml

      - name: Publish test results
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: test-results/*.xml
```

---

## pre-commit

Add `geoassert` as a pre-commit hook to validate datasets before each commit.

**.pre-commit-config.yaml:**

```yaml
repos:
  - repo: https://github.com/Morphenr/geoassert
    rev: v0.3.0
    hooks:
      # Validate against a contract
      - id: geoassert-validate
        args: [--contract, contracts/buildings.yml]
        files: data/.*\.parquet$

      # GeoParquet metadata check only (no contract needed)
      - id: geoassert-geoparquet-check
        files: \.parquet$
```

The `geoassert-validate` hook runs `geoassert validate` on any staged `.parquet` file. It passes the file path as the first argument, so the `args` list must include `--contract`.

The `geoassert-geoparquet-check` hook is contract-free and checks GeoParquet metadata validity for any Parquet file.

---

## dbt

A `dbt` integration is planned for a future release. The recommended pattern until then is to run `geoassert` in the CI step that follows `dbt run`:

```yaml
- name: Run dbt
  run: dbt run --target prod

- name: Validate dbt outputs
  run: |
    pip install geoassert
    geoassert validate exports/buildings.parquet \
      --contract contracts/buildings.yml \
      --format github
```

---

## Python test suite

Use `geoassert` inside pytest to assert dataset quality as part of your test suite:

```python
import pytest
import geoassert as ga

@pytest.fixture(scope="session")
def buildings_result():
    return ga.validate(
        "data/buildings.parquet",
        contract="contracts/buildings.yml",
    )

def test_buildings_pass(buildings_result):
    assert buildings_result.passed, buildings_result.to_markdown()

def test_no_crs_failures(buildings_result):
    crs_fails = [c for c in buildings_result.failures if c.check.startswith("crs.")]
    assert not crs_fails

def test_geometry_valid(buildings_result):
    validity_check = next(
        (c for c in buildings_result.checks if c.check == "geometry.valid"), None
    )
    assert validity_check is not None
    assert validity_check.status == "pass"
```

---

## Makefile

```makefile
.PHONY: validate

validate:
	geoassert validate data/buildings.parquet \
		--contract contracts/buildings.yml \
		--format github
```

```bash
make validate
```
