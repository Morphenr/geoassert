# Contributing to geoassert

Thank you for your interest in contributing.

## Quick start

```bash
git clone https://github.com/Morphenr/geoassert.git
cd geoassert
uv sync --extra dev
uv run pytest
```

Or with pip:

```bash
pip install -e ".[dev]"
pytest
```

## Ways to contribute

- **Bug reports** — use the [bug report template](https://github.com/Morphenr/geoassert/issues/new?template=bug_report.yml)
- **Check requests** — use the [check request template](https://github.com/Morphenr/geoassert/issues/new?template=check_request.yml)
- **Code** — see the guide below

## Adding a new check

1. Pick the right module under `src/geoassert/checks/`:

   | Module | When to use |
   |---|---|
   | `geoparquet.py` | Parquet/GeoParquet metadata only — no extras needed |
   | `crs.py` | CRS from metadata — no extras needed |
   | `bounds.py` | Spatial bounds from metadata — no extras needed |
   | `attributes.py` | Column-level checks using PyArrow — no extras needed |
   | `geometry.py` | Row-level geometry ops — requires `shapely` extra |

2. Subclass `BaseCheck`:

   ```python
   from geoassert.checks.base import BaseCheck
   from geoassert.result import CheckResult

   class MyNewCheck(BaseCheck):
       name = "category.my_check"   # dot-namespaced

       def run(self, info, contract=None) -> CheckResult:
           ...
   ```

3. Add it to the `run_*_checks()` list at the bottom of the module.

4. Write tests in `tests/test_checks/`. Use the `write_test_geoparquet()` helper from `tests/conftest.py` to create fixture files without needing external data.

5. Document the failure message: every `status="fail"` result should have `expected`, `observed`, `why_it_matters`, and `suggestion` populated.

## Code style

```bash
make lint      # ruff check
make format    # ruff format
make typecheck # mypy
make test      # pytest
make all       # lint + typecheck + test
```

All CI checks must pass. New checks need tests. No partial implementations — stubs that skip gracefully are fine, half-written checks that fail silently are not.

## Failure message quality

The project prioritises actionable error messages. Every failure should answer:

- What failed?
- What was expected vs. observed?
- Why does it matter?
- How to fix it?

See the `why_it_matters` and `suggestion` fields on `CheckResult`.

## Submitting a PR

- Branch from `main`.
- Keep commits focused — one logical change per commit.
- Fill in the PR template.
- Ensure `make all` passes locally before opening the PR.
