# CLI reference

```
geoassert [OPTIONS] COMMAND [ARGS]...
```

---

## `geoassert profile`

Profile a geospatial dataset and print key facts.

```bash
geoassert profile PATH [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--format`, `-f` | `text` | Output format: `text` \| `json` |

**Example**

```bash
geoassert profile data/buildings.parquet
geoassert profile data/buildings.parquet --format json
```

---

## `geoassert init-contract`

Generate a starter contract YAML from an existing dataset and print it to stdout.

```bash
geoassert init-contract PATH [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--out`, `-o` | stdout | Write contract to this file instead of stdout |

**Example**

```bash
# Print to stdout
geoassert init-contract data/buildings.parquet

# Write to file
geoassert init-contract data/buildings.parquet --out contracts/buildings.yml
```

The generated contract is conservative — it records what the dataset currently looks like. Edit it to add or tighten constraints before committing.

---

## `geoassert validate`

Validate a dataset or directory of datasets against a contract.

```bash
geoassert validate PATH --contract CONTRACT [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--contract`, `-c` | **required** | Path to the contract YAML |
| `--format`, `-f` | `text` | Output format: `text` \| `json` \| `markdown` \| `github` \| `junit` |
| `--sample`, `-n` | — | Row limit for row-level checks. Metadata checks always run on the full file. |
| `--engine`, `-e` | `pyarrow` | Compute engine for attribute checks: `pyarrow` \| `duckdb` |
| `--fail-on-warn` | `false` | Exit 1 when warnings are present |
| `--junit-out` | — | Write JUnit XML to this file alongside the main output format |

**Warehouse options** (used when `PATH` is a warehouse URI):

| Option | Description |
|---|---|
| `--geom-col` | Geometry column name (default: `geometry`) |
| `--dsn` | PostgreSQL DSN for PostGIS sources (alternative to embedding credentials in the URI) |
| `--bq-project` | GCP project ID override for BigQuery sources |
| `--sf-account` | Snowflake account identifier |
| `--sf-user` | Snowflake username |
| `--sf-password` | Snowflake password |
| `--sf-warehouse` | Snowflake virtual warehouse name |

**Exit codes**

| Code | Meaning |
|---:|---|
| `0` | All checks passed |
| `1` | One or more failures (or warnings with `--fail-on-warn`) |
| `2` | Invalid contract |
| `3` | Unreadable input data |
| `4` | Internal error |

**Examples**

```bash
# Basic validation
geoassert validate data/buildings.parquet --contract contracts/buildings.yml

# PostGIS table
geoassert validate postgis://user:pass@host/db/public/buildings \
  --contract contracts/buildings.yml

# BigQuery table
geoassert validate bigquery://my-project/my_dataset/buildings \
  --contract contracts/buildings.yml

# Snowflake table
geoassert validate snowflake://myaccount/MY_DB/PUBLIC/BUILDINGS \
  --contract contracts/buildings.yml \
  --sf-user myuser --sf-password secret

# GitHub Actions annotations
geoassert validate data/buildings.parquet \
  --contract contracts/buildings.yml \
  --format github

# JSON output piped to jq
geoassert validate data/buildings.parquet \
  --contract contracts/buildings.yml \
  --format json | jq '.failures[]'

# JUnit XML for CI test reporters, plus console output
geoassert validate data/buildings.parquet \
  --contract contracts/buildings.yml \
  --junit-out test-results/geoassert.xml

# Sample 10,000 rows for large file attribute checks
geoassert validate data/large.parquet \
  --contract contracts/large.yml \
  --sample 10000

# Fast attribute checks via DuckDB
geoassert validate data/large.parquet \
  --contract contracts/large.yml \
  --engine duckdb

# Validate an entire directory (runs partition checks too)
geoassert validate data/partitioned/ --contract contracts/buildings.yml
```

---

## `geoassert dbt list`

List all models found in the dbt `manifest.json`.

```bash
geoassert dbt list [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--project-dir`, `-p` | current directory | dbt project root containing `target/manifest.json` |
| `--format`, `-f` | `text` | Output format: `text` \| `json` |

**Example**

```bash
geoassert dbt list
geoassert dbt list --project-dir /path/to/dbt/project --format json
```

---

## `geoassert dbt validate`

Validate a dbt model output against a contract. The model is located in the manifest; its materialization determines where the data is read from.

```bash
geoassert dbt validate MODEL_NAME --contract CONTRACT [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--contract`, `-c` | **required** | Path to the contract YAML |
| `--project-dir`, `-p` | current directory | dbt project root |
| `--format`, `-f` | `text` | Output format: `text` \| `json` \| `markdown` \| `github` \| `junit` |
| `--fail-on-warn` | `false` | Exit 1 on warnings |
| `--sample`, `-n` | — | Row limit for row-level checks |
| `--engine`, `-e` | `pyarrow` | Compute engine: `pyarrow` \| `duckdb` |
| `--dsn` | — | PostgreSQL DSN for PostGIS-materialised models |
| `--path` | — | Direct file path override (Parquet file for this model) |
| `--junit-out` | — | Write JUnit XML to this file |

**Examples**

```bash
# Validate a model discovered from the manifest
geoassert dbt validate buildings --contract contracts/buildings.yml

# Validate a PostGIS-materialised model
geoassert dbt validate buildings \
  --contract contracts/buildings.yml \
  --dsn postgresql://user:pass@host/db

# Override the file path directly
geoassert dbt validate buildings \
  --contract contracts/buildings.yml \
  --path exports/buildings.parquet
```

---

## `geoassert geoparquet check`

Run GeoParquet metadata checks on a file without a contract.

```bash
geoassert geoparquet check PATH [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--format`, `-f` | `text` | Output format: `text` \| `json` |

**Example**

```bash
geoassert geoparquet check data/buildings.parquet
```

Useful as a quick sanity check on any GeoParquet file — no contract needed.
