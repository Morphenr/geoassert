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
