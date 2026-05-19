"""Generate demo GeoParquet files used by the VHS tape recording."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
CONTRACTS = ROOT / "contracts"
EXAMPLES = ROOT / "examples"
DATA.mkdir(exist_ok=True)
CONTRACTS.mkdir(exist_ok=True)
EXAMPLES.mkdir(exist_ok=True)


def _wkb_point(x: float, y: float) -> bytes:
    return struct.pack("<bIdd", 1, 1, x, y)


def _wkb_polygon(x0: float, y0: float, x1: float, y1: float) -> bytes:
    ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    header = struct.pack("<bII", 1, 3, 1)
    ring_header = struct.pack("<I", len(ring))
    coords = b"".join(struct.pack("<dd", x, y) for x, y in ring)
    return header + ring_header + coords


# ── buildings_ok.parquet ──────────────────────────────────────────────────────
# Passes all checks in the demo contract

import random

random.seed(42)
n = 120
lon = [round(random.uniform(-0.5, 0.2), 6) for _ in range(n)]
lat = [round(random.uniform(51.3, 51.6), 6) for _ in range(n)]
geom = [_wkb_polygon(lo, la, lo + 0.001, la + 0.001) for lo, la in zip(lon, lat)]

table = pa.table(
    {
        "geometry": pa.array(geom, type=pa.binary()),
        "building_id": pa.array(list(range(1, n + 1)), type=pa.int64()),
        "height_m": pa.array([round(random.uniform(3.0, 80.0), 1) for _ in range(n)]),
        "name": pa.array([f"Building {i}" for i in range(1, n + 1)]),
    }
)

crs_json = {
    "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
    "type": "GeographicCRS",
    "name": "EPSG:4326",
    "id": {"authority": "EPSG", "code": 4326},
}
geo_meta = {
    "version": "1.1.0",
    "primary_column": "geometry",
    "columns": {
        "geometry": {
            "encoding": "WKB",
            "crs": crs_json,
            "geometry_types": ["Polygon"],
            "bbox": [-0.5, 51.3, 0.201, 51.601],
        }
    },
}
table = table.replace_schema_metadata({b"geo": json.dumps(geo_meta).encode()})
pq.write_table(table, DATA / "buildings.parquet")
pq.write_table(table, EXAMPLES / "buildings.parquet")
print(f"Wrote {DATA / 'buildings.parquet'}  ({n} rows)")
print(f"Wrote {EXAMPLES / 'buildings.parquet'}  ({n} rows)")

# ── demo contract ─────────────────────────────────────────────────────────────

contract_yaml = """\
geoassert_version: "0.1"

dataset: buildings

geometry:
  column: geometry
  type:
    - Polygon
  crs: EPSG:4326
  allow_empty: false

bounds:
  within:
    bbox: [-1.0, 51.0, 1.0, 52.0]

attributes:
  building_id:
    nullable: false
    unique: true
  height_m:
    nullable: true
    min: 0
    max: 400
"""
(CONTRACTS / "buildings.yml").write_text(contract_yaml)
(EXAMPLES / "buildings_contract.yml").write_text(contract_yaml)
print(f"Wrote {CONTRACTS / 'buildings.yml'}")
print(f"Wrote {EXAMPLES / 'buildings_contract.yml'}")
