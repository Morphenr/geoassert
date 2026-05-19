# CLAUDE.md — geoassert

## What this project is

`geoassert` is a Python library and CLI for contract-based validation of geospatial data pipelines.
It is **not** a GIS analysis library, a GeoPandas replacement, or a spatial database.
It sits above existing geospatial tools as a lightweight validation layer.

See `.github/geoassert.md` for the full project brief.

## Architecture

```
src/geoassert/
  __init__.py        public API: validate(), profile(), load_contract()
  cli.py             typer CLI (4 commands: profile, init-contract, validate, geoparquet check)
  runner.py          ValidationRunner — orchestrates checks for a dataset + contract
  result.py          ValidationResult, CheckResult (dataclasses, no deps beyond stdlib)
  exceptions.py      GeoAssertError, ContractError (exit 2), DataReadError (exit 3), InternalError (exit 4)
  contracts/
    schema.py        Pydantic v2 Contract model and sub-models
    loader.py        load_contract(path) → Contract; raises ContractError on bad YAML
  checks/
    base.py          BaseCheck ABC: name: str, run(info, contract) → CheckResult
    geoparquet.py    GeoParquet metadata checks (no extras needed)
    crs.py           CRS existence and match checks (no extras needed)
    bounds.py        Spatial bounds checks (no extras needed)
    geometry.py      Geometry validity/type checks (requires shapely extra)
    attributes.py    Attribute null/unique/range checks (pure pyarrow)
  engines/
    pyarrow.py       DatasetInfo dataclass + read_geoparquet_info() — CORE, no extras
    shapely.py       wkb_column_to_geometries(), count_invalid(), etc. (shapely extra)
    geopandas.py     read_geoparquet() wrapper (geopandas extra)
    duckdb.py        get_connection(), query_parquet() (duckdb extra)
  reports/
    markdown.py      render_validation_result(result) → str
    json.py          thin wrapper over result.to_json()
    github.py        render_github_annotations() — emits ::error/::warning workflow commands
  profiling/
    profiler.py      profile_dataset(), generate_contract_yaml()
```

## Key design decisions

- **src layout** (`src/geoassert/`): standard for libraries; tests import the installed package.
- **Core deps only**: `pyarrow`, `pydantic`, `pyyaml`, `typer`, `rich`. Everything else is an optional extra.
- **DatasetInfo** is the central data object passed to all checks. It contains Parquet schema + geo metadata without reading all rows.
- **Checks are classes** inheriting `BaseCheck`, not plain functions, so they are easy to discover and extend.
- **Checks that need row-level data** (geometry validity) read the table lazily inside `run()`.
- **shapely checks** guard their import with a try/except and return `status="skip"` if the extra is missing.
- **Exit codes**: 0=pass, 1=validation fail, 2=bad contract, 3=bad data, 4=internal.
- **Contract YAML schema** is defined in pydantic; invalid contracts raise `ContractError` with a human-readable message.

## Development priorities (from project brief)

1. Make `geoassert profile` useful.
2. Make `geoassert validate` deterministic.
3. Make failure messages excellent (expected / observed / why / suggestion).
4. Make GeoParquet checks strong.
5. Make contracts easy to generate and edit.
6. Make CI integration frictionless.
7. Add broader engines and integrations only after the core experience is solid.

## Running tests

```bash
uv sync --extra dev
uv run pytest
```

## Linting — MUST run before every commit

CI enforces both lint and format checks (`ruff check` + `ruff format --check`) over all of `src/` and `tests/`. Always run the full suite before committing:

```bash
python3 -m ruff check src tests
python3 -m ruff format --check src tests
```

To auto-fix and format in one step:

```bash
python3 -m ruff check src tests --fix
python3 -m ruff format src tests
```

**Critical:** CI runs `uvx ruff check src tests` and `uvx ruff format --check src tests`. Running ruff only against new or changed files is not sufficient — always target the full `src` and `tests` directories.

## Adding a new check

1. Add a class in the appropriate `checks/*.py` module inheriting `BaseCheck`.
2. Set `name = "category.check_name"` (dot-namespaced).
3. Implement `run(self, info, contract) -> CheckResult`.
4. Add the instance to the `run_*_checks()` list at the bottom of the module.
5. Add tests in `tests/test_checks/`.

## Adding a new CLI command

Use `@app.command()` in `cli.py`. Use `@geoparquet_app.command()` for `geoassert geoparquet <cmd>`.

## Non-goals

Do not build: a full GIS analysis library, a GeoPandas replacement, a spatial database, a web UI,
automatic geometry repair, every file format, every warehouse integration, or a complex plugin
ecosystem before core checks work.
