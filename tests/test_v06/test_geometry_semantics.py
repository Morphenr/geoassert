"""Tests for v0.6 geometry semantic checks: Z dimensions and antimeridian."""

from __future__ import annotations

import struct
from pathlib import Path

import pyarrow as pa
import pytest

from geoassert.checks.geometry import (
    GeometryAntimeridianCheck,
    GeometryDimensionsCheck,
    _wkb_has_z,
)
from geoassert.contracts.schema import Contract
from geoassert.engines.pyarrow import DatasetInfo

# ── WKB helpers ────────────────────────────────────────────────────────────────


def _wkb_point_2d(x: float = 1.0, y: float = 2.0) -> bytes:
    return struct.pack("<bIdd", 1, 1, x, y)


def _wkb_point_z_iso(x: float = 1.0, y: float = 2.0, z: float = 3.0) -> bytes:
    # ISO WKB PointZ type = 1001
    return struct.pack("<bIddd", 1, 1001, x, y, z)


def _wkb_point_z_ewkb(x: float = 1.0, y: float = 2.0, z: float = 3.0) -> bytes:
    # EWKB: Z flag = 0x80000000 | 1
    return struct.pack("<bIddd", 1, 0x80000001, x, y, z)


def _wkb_point_zm(x: float = 1.0, y: float = 2.0, z: float = 3.0, m: float = 0.0) -> bytes:
    # ISO WKB PointZM = 3001
    return struct.pack("<bIdddd", 1, 3001, x, y, z, m)


def _info_with_wkb(wkb_rows: list[bytes | None], geo_meta: dict | None = None) -> DatasetInfo:
    arrays: list = [pa.array(wkb_rows, type=pa.binary())]
    table = pa.table({"geometry": arrays[0]})
    return DatasetInfo(
        path=Path("/tmp/x.parquet"),
        schema=table.schema,
        num_rows=len(wkb_rows),
        geo_metadata=geo_meta
        or {
            "primary_column": "geometry",
            "columns": {"geometry": {"encoding": "WKB", "bbox": [-10.0, -10.0, 10.0, 10.0]}},
        },
        table=table,
    )


def _contract_dims(dims: str) -> Contract:
    return Contract.model_validate({"geometry": {"dimensions": dims}})


# ── _wkb_has_z ─────────────────────────────────────────────────────────────────


class TestWkbHasZ:
    def test_2d_point_no_z(self) -> None:
        assert not _wkb_has_z(_wkb_point_2d())

    def test_iso_pointz_has_z(self) -> None:
        assert _wkb_has_z(_wkb_point_z_iso())

    def test_ewkb_pointz_has_z(self) -> None:
        assert _wkb_has_z(_wkb_point_z_ewkb())

    def test_pointzm_has_z(self) -> None:
        assert _wkb_has_z(_wkb_point_zm())

    def test_empty_bytes_no_z(self) -> None:
        assert not _wkb_has_z(b"")

    def test_short_bytes_no_z(self) -> None:
        assert not _wkb_has_z(b"\x01\x00\x00")


# ── GeometryDimensionsCheck ────────────────────────────────────────────────────


class TestGeometryDimensionsCheck:
    def test_any_skips(self) -> None:
        info = _info_with_wkb([_wkb_point_2d()])
        result = GeometryDimensionsCheck().run(info, _contract_dims("any"))
        assert result.status == "skip"

    def test_2d_contract_2d_data_passes(self) -> None:
        info = _info_with_wkb([_wkb_point_2d(), _wkb_point_2d()])
        result = GeometryDimensionsCheck().run(info, _contract_dims("2D"))
        assert result.status == "pass"

    def test_2d_contract_3d_data_fails(self) -> None:
        info = _info_with_wkb([_wkb_point_2d(), _wkb_point_z_iso()])
        result = GeometryDimensionsCheck().run(info, _contract_dims("2D"))
        assert result.status == "fail"
        assert "Z" in result.message or "3D" in result.message

    def test_3d_contract_3d_data_passes(self) -> None:
        info = _info_with_wkb([_wkb_point_z_iso(), _wkb_point_z_ewkb()])
        result = GeometryDimensionsCheck().run(info, _contract_dims("3D"))
        assert result.status == "pass"

    def test_3d_contract_2d_data_fails(self) -> None:
        info = _info_with_wkb([_wkb_point_2d(), _wkb_point_z_iso()])
        result = GeometryDimensionsCheck().run(info, _contract_dims("3D"))
        assert result.status == "fail"
        assert "2D" in result.message or "missing" in result.message.lower()

    def test_ewkb_z_detected(self) -> None:
        info = _info_with_wkb([_wkb_point_z_ewkb()])
        result = GeometryDimensionsCheck().run(info, _contract_dims("2D"))
        assert result.status == "fail"

    def test_mixed_z_counts_affected_rows(self) -> None:
        wkbs = [_wkb_point_z_iso(), _wkb_point_z_iso(), _wkb_point_2d()]
        info = _info_with_wkb(wkbs)
        result = GeometryDimensionsCheck().run(info, _contract_dims("2D"))
        assert result.status == "fail"
        assert result.affected_rows == 2

    def test_missing_column_skips(self) -> None:
        info = DatasetInfo(
            path=Path("/tmp/x.parquet"),
            schema=pa.schema([pa.field("id", pa.int64())]),
            num_rows=1,
        )
        result = GeometryDimensionsCheck().run(info, _contract_dims("2D"))
        assert result.status == "skip"

    def test_no_contract_skips(self) -> None:
        info = _info_with_wkb([_wkb_point_2d()])
        result = GeometryDimensionsCheck().run(info, Contract.model_validate({}))
        assert result.status == "skip"


# ── GeometryAntimeridianCheck ──────────────────────────────────────────────────


def _info_with_bbox(minx: float, miny: float, maxx: float, maxy: float) -> DatasetInfo:
    return DatasetInfo(
        path=Path("/tmp/x.parquet"),
        schema=pa.schema([]),
        num_rows=10,
        geo_metadata={
            "primary_column": "geometry",
            "columns": {
                "geometry": {
                    "encoding": "WKB",
                    "bbox": [minx, miny, maxx, maxy],
                }
            },
        },
    )


class TestGeometryAntimeridianCheck:
    def test_normal_bbox_passes(self) -> None:
        info = _info_with_bbox(-8.0, 49.0, 2.0, 61.0)
        result = GeometryAntimeridianCheck().run(info)
        assert result.status == "pass"

    def test_wide_bbox_warns(self) -> None:
        # span > 180 degrees
        info = _info_with_bbox(-170.0, -10.0, 170.0, 10.0)
        result = GeometryAntimeridianCheck().run(info)
        assert result.status == "warn"

    def test_antimeridian_straddle_warns(self) -> None:
        # minx far west, maxx far east
        info = _info_with_bbox(-175.0, -10.0, 175.0, 10.0)
        result = GeometryAntimeridianCheck().run(info)
        assert result.status == "warn"

    def test_exactly_180_span_warns(self) -> None:
        info = _info_with_bbox(-90.0, -10.0, 91.0, 10.0)
        result = GeometryAntimeridianCheck().run(info)
        assert result.status == "warn"

    def test_global_coverage_warns(self) -> None:
        info = _info_with_bbox(-180.0, -90.0, 180.0, 90.0)
        result = GeometryAntimeridianCheck().run(info)
        assert result.status == "warn"

    def test_no_geo_metadata_skips(self) -> None:
        info = DatasetInfo(path=Path("/tmp/x.parquet"), schema=pa.schema([]), num_rows=0)
        result = GeometryAntimeridianCheck().run(info)
        assert result.status == "skip"

    def test_no_bbox_skips(self) -> None:
        info = DatasetInfo(
            path=Path("/tmp/x.parquet"),
            schema=pa.schema([]),
            num_rows=0,
            geo_metadata={
                "primary_column": "geometry",
                "columns": {"geometry": {"encoding": "WKB"}},
            },
        )
        result = GeometryAntimeridianCheck().run(info)
        assert result.status == "skip"

    def test_warn_message_includes_span(self) -> None:
        info = _info_with_bbox(-170.0, -10.0, 170.0, 10.0)
        result = GeometryAntimeridianCheck().run(info)
        assert "340" in result.message or "340.0" in result.message

    def test_suggestion_mentions_antimeridian(self) -> None:
        info = _info_with_bbox(-170.0, -10.0, 170.0, 10.0)
        result = GeometryAntimeridianCheck().run(info)
        assert result.suggestion is not None
        assert "antimeridian" in result.suggestion.lower()


# ── Contract schema: dimensions field ─────────────────────────────────────────


class TestDimensionsContractField:
    def test_default_is_any(self) -> None:
        c = Contract.model_validate({"geometry": {}})
        assert c.geometry is not None
        assert c.geometry.dimensions == "any"

    def test_2d_accepted(self) -> None:
        c = Contract.model_validate({"geometry": {"dimensions": "2D"}})
        assert c.geometry is not None
        assert c.geometry.dimensions == "2D"

    def test_3d_accepted(self) -> None:
        c = Contract.model_validate({"geometry": {"dimensions": "3D"}})
        assert c.geometry is not None
        assert c.geometry.dimensions == "3D"

    def test_invalid_value_raises(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Contract.model_validate({"geometry": {"dimensions": "4D"}})
