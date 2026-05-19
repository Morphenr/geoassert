"""Tests for BboxConsistencyCheck."""

from __future__ import annotations

import struct

import pytest

shapely = pytest.importorskip("shapely")

from geoassert.checks.bounds import BboxConsistencyCheck
from geoassert.engines.pyarrow import read_geoparquet_info
from tests.conftest import write_test_geoparquet


def _box_wkb(x0: float, y0: float, x1: float, y1: float) -> bytes:
    ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    header = struct.pack("<bII", 1, 3, 1)
    ring_header = struct.pack("<I", len(ring))
    coords = b"".join(struct.pack("<dd", x, y) for x, y in ring)
    return header + ring_header + coords


def test_bbox_consistency_pass(tmp_path):
    # Declare bbox that exactly matches the polygon geometry
    p = write_test_geoparquet(
        tmp_path / "ok.parquet",
        n_rows=1,
        geometry_types=["Polygon"],
        bbox=[0.0, 0.0, 1.0, 1.0],
        wkb_factory=lambda i: _box_wkb(0.0, 0.0, 1.0, 1.0),
    )
    info = read_geoparquet_info(p)
    result = BboxConsistencyCheck().run(info)
    assert result.status == "pass"


def test_bbox_consistency_warn_on_mismatch(tmp_path):
    # Declare incorrect bbox for a geometry sitting at (0,0)-(1,1)
    p = write_test_geoparquet(
        tmp_path / "bad.parquet",
        n_rows=1,
        geometry_types=["Polygon"],
        bbox=[10.0, 10.0, 20.0, 20.0],  # wrong!
        wkb_factory=lambda i: _box_wkb(0.0, 0.0, 1.0, 1.0),
    )
    info = read_geoparquet_info(p)
    result = BboxConsistencyCheck().run(info)
    assert result.status == "warn"
    assert result.expected == [10.0, 10.0, 20.0, 20.0]


def test_bbox_consistency_skip_no_bbox(tmp_path):
    p = write_test_geoparquet(tmp_path / "nobbox.parquet", bbox=None)
    info = read_geoparquet_info(p)
    result = BboxConsistencyCheck().run(info)
    assert result.status == "skip"


def test_bbox_consistency_skip_no_geo_meta(tmp_path):
    p = write_test_geoparquet(tmp_path / "nometa.parquet", include_geo_meta=False)
    info = read_geoparquet_info(p)
    result = BboxConsistencyCheck().run(info)
    assert result.status == "skip"
