# Engines

`geoassert` has two kinds of engines:

- **Compute engines** (`pyarrow`, `duckdb`) — control how attribute checks are executed against a dataset that has already been read.
- **Source engines** (PostGIS, BigQuery, Snowflake) — connect to a remote database or warehouse, pull the data, and hand a `DatasetInfo` to the standard check pipeline.

The compute engine does not affect metadata-only checks (GeoParquet, CRS, bounds) — those always use PyArrow's metadata reader.

---

## PyArrow (default)

The default engine reads columns into memory using PyArrow and computes null counts, distinct counts, and min/max with `pyarrow.compute`.

```bash
geoassert validate data/buildings.parquet --contract contracts/buildings.yml
# equivalent to --engine pyarrow
```

**When to use:**

- Files that fit comfortably in memory
- No DuckDB installed
- All other cases — it works everywhere

---

## DuckDB

The DuckDB engine pushes attribute checks directly into DuckDB SQL queries. Columns are never loaded into Python memory, making it significantly faster on large files.

```bash
pip install "geoassert[duckdb]"

geoassert validate data/buildings.parquet \
  --contract contracts/buildings.yml \
  --engine duckdb
```

```python
result = geoassert.validate(
    "data/buildings.parquet",
    contract="contracts/buildings.yml",
    engine="duckdb",
)
```

**When to use:**

- Large files (> a few GB)
- Files on cloud storage (DuckDB reads S3/GCS without downloading)
- High-frequency validation in pipelines

**What DuckDB handles:**

| Check | DuckDB query |
|---|---|
| `attributes.<col>.nullable` | `COUNT(*) WHERE col IS NULL` |
| `attributes.<col>.unique` | `COUNT(DISTINCT col)` vs `COUNT(*)` |
| `attributes.<col>.range` | `MIN(col), MAX(col)` |

---

## Cloud paths

Both engines support cloud URIs transparently. The path is detected by the presence of `://`.

```python
# S3
result = geoassert.validate("s3://my-bucket/data.parquet", contract=contract)

# Google Cloud Storage
result = geoassert.validate("gs://my-bucket/data.parquet", contract=contract)

# Azure Blob Storage
result = geoassert.validate("az://my-container/data.parquet", contract=contract)
```

**How it works:**

- `pyarrow.fs.FileSystem.from_uri()` resolves the filesystem from the URI
- The resolved filesystem is passed to `pyarrow.parquet.ParquetFile` and `read_table`
- DuckDB reads cloud URIs natively without any additional configuration

**Prerequisites for cloud reads:**

| URI scheme | Required package |
|---|---|
| `s3://` | `pyarrow[s3]` or `s3fs` |
| `gs://` | `gcsfs` |
| `az://` | `adlfs` |

Install alongside geoassert:

```bash
pip install "geoassert[duckdb]" s3fs   # S3 with DuckDB engine
pip install geoassert gcsfs            # GCS with PyArrow engine
```

---

## Sampling

Row-level checks can be limited to a random sample to speed up validation on large files. Metadata checks always run on the full file regardless of the sample setting.

```bash
geoassert validate data/large.parquet \
  --contract contracts/large.yml \
  --sample 50000
```

```python
result = geoassert.validate(
    "data/large.parquet",
    contract="contracts/large.yml",
    sample=50_000,
)
print(result.stats["sample"])  # 50000
```

The sample is drawn with `random.sample` — results are reproducible if you seed Python's random before calling `validate`.

**Checks affected by sampling:** geometry validity, geometry empty, geometry type, attribute nullable, attribute unique, attribute range.

**Checks not affected:** all GeoParquet metadata checks, CRS checks, bounds checks.

---

## Warehouse source engines

Warehouse engines connect to a remote database, read the relevant table, and produce a `DatasetInfo` that the standard check pipeline then validates. GeoParquet-specific checks are automatically skipped for warehouse sources.

Install the appropriate extra:

```bash
pip install "geoassert[postgis]"    # psycopg2-binary
pip install "geoassert[bigquery]"   # google-cloud-bigquery
pip install "geoassert[snowflake]"  # snowflake-connector-python
pip install "geoassert[all]"        # all of the above
```

### PostGIS

```bash
geoassert validate postgis://user:pass@host/db/public/buildings \
  --contract contracts/buildings.yml
```

```python
from geoassert.engines.postgis import read_postgis_info
import geoassert as ga

info = read_postgis_info("postgresql://user:pass@host/db", "buildings", schema="public")
result = ga.validate_source(info, "contracts/buildings.yml")
```

The engine queries geometry as WKB via `ST_AsWKB()`, looks up the SRID from `geometry_columns`, and constructs a CRS entry in the GeoParquet geo metadata format so that CRS checks work normally.

### BigQuery

BigQuery `GEOGRAPHY` columns are always WGS 84 (EPSG:4326); the engine hard-codes this as the CRS.

```bash
geoassert validate bigquery://my-project/my_dataset/buildings \
  --contract contracts/buildings.yml
```

```python
from geoassert.engines.bigquery import read_bigquery_info
import geoassert as ga

info = read_bigquery_info("my-project", "my_dataset", "buildings")
result = ga.validate_source(info, "contracts/buildings.yml")
```

### Snowflake

Snowflake geometry columns are fetched as EWKB via `ST_ASEWKB()`. Column names are lowercased automatically (Snowflake returns uppercase names by default).

```bash
geoassert validate snowflake://myaccount/MY_DB/PUBLIC/BUILDINGS \
  --contract contracts/buildings.yml \
  --sf-user myuser --sf-password secret
```

```python
from geoassert.engines.snowflake import read_snowflake_info
import geoassert as ga

info = read_snowflake_info(
    "myaccount", "myuser", "secret", "MY_DB", "PUBLIC", "BUILDINGS",
    warehouse="COMPUTE_WH",
)
result = ga.validate_source(info, "contracts/buildings.yml")
```
