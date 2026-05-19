# Contracts

A contract is a YAML file that describes what a valid dataset looks like. `geoassert` validates the dataset against the contract and reports any violations.

## Generate a starter contract

```bash
geoassert init-contract data/buildings.parquet > contracts/buildings.yml
```

Edit the generated file to tighten the constraints. The generated contract is conservative — it describes what the dataset *currently* looks like, not what it *should* look like.

## Full schema reference

```yaml
# Optional — reserved for future versioning
geoassert_version: "0.1"

# Human-readable dataset name (used in reports)
dataset: buildings

# ── Geometry ──────────────────────────────────────────────────────────────────

geometry:
  # Geometry column name (default: "geometry")
  column: geometry

  # Allowed geometry types — WKT type names
  # Validation requires geoassert[shapely]
  type:
    - Polygon
    - MultiPolygon

  # Expected CRS in AUTHORITY:CODE format
  crs: EPSG:4326

  # Fail if any invalid geometries are found (requires shapely)
  valid: true

  # Fail if any empty geometries are found (requires shapely)
  # Set to true to allow empty geometries (check still warns)
  allow_empty: false

# ── Bounds ────────────────────────────────────────────────────────────────────

bounds:
  within:
    # [minx, miny, maxx, maxy] — dataset must be contained within this bbox
    bbox: [-8.65, 49.86, 1.76, 60.86]

# ── Attributes ────────────────────────────────────────────────────────────────

attributes:
  building_id:
    nullable: false   # fail if any null values found
    unique: true      # fail if any duplicate values found

  height_m:
    nullable: true    # null values allowed
    min: 0            # fail if observed min < 0
    max: 400          # fail if observed max > 400

  category:
    nullable: false

# ── Severity overrides ────────────────────────────────────────────────────────

# Override the default severity for specific checks.
# Valid values: "info", "warn", "error"
# "error" checks cause exit code 1; "warn" checks do not (unless --fail-on-warn)
severity:
  crs.match: warn             # downgrade from error — tolerate equivalent CRS
  bounds.bbox_consistency: warn  # already warn by default
```

## Field reference

### `geometry`

| Field | Type | Default | Description |
|---|---|---|---|
| `column` | string | `"geometry"` | Name of the geometry column |
| `type` | list[string] | — | Allowed WKT geometry type names. If absent, type is not checked. |
| `crs` | string | — | Expected CRS in `AUTHORITY:CODE` format (e.g. `EPSG:4326`) |
| `valid` | bool | — | If `true`, fails when invalid geometries are found |
| `allow_empty` | bool | `false` | If `false`, fails when empty geometries are found |

Valid geometry type names: `Point`, `MultiPoint`, `LineString`, `MultiLineString`, `Polygon`, `MultiPolygon`, `GeometryCollection`

### `bounds.within`

| Field | Type | Description |
|---|---|---|
| `bbox` | list[float] | `[minx, miny, maxx, maxy]` — dataset must be contained within this bbox. `minx < maxx` and `miny < maxy` are validated at contract load time. |

### `attributes.<column>`

| Field | Type | Default | Description |
|---|---|---|---|
| `nullable` | bool | `true` | If `false`, fails when the column has any null values |
| `unique` | bool | `false` | If `true`, fails when any duplicate values are found |
| `min` | number | — | Fails when the observed column minimum is less than this value |
| `max` | number | — | Fails when the observed column maximum exceeds this value |

### `severity`

A dictionary mapping check names to severity levels. Valid levels:

| Level | Effect |
|---|---|
| `info` | Check result is recorded but never causes a failure |
| `warn` | Check appears as a warning; does not affect exit code unless `--fail-on-warn` is set |
| `error` | Check failure causes exit code 1 (default for most checks) |

Check names use dot notation matching the check's `name` field, e.g. `crs.match`, `geometry.valid`, `bounds.within`.

## Validation errors at load time

`geoassert` validates the contract itself on load. The following will cause a `ContractError` (exit code 2):

- `geometry.crs` not in `AUTHORITY:CODE` format
- `geometry.type` contains an unrecognised WKT type name
- `bounds.within.bbox` does not have exactly 4 values, or `minx >= maxx`, or `miny >= maxy`
- `attributes.<col>.min > attributes.<col>.max`
