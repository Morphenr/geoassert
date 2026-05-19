"""Tests for 0.2 stronger YAML schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from geoassert.contracts.schema import AttributeContract, BoundsWithinConfig, GeometryContract

# ── GeometryContract.crs ──────────────────────────────────────────────────────


def test_geometry_crs_valid_epsg() -> None:
    g = GeometryContract(crs="EPSG:4326")
    assert g.crs == "EPSG:4326"


def test_geometry_crs_valid_ogc() -> None:
    g = GeometryContract(crs="OGC:CRS84")
    assert g.crs == "OGC:CRS84"


def test_geometry_crs_none_is_allowed() -> None:
    g = GeometryContract(crs=None)
    assert g.crs is None


def test_geometry_crs_invalid_format_raises() -> None:
    with pytest.raises(ValidationError, match="AUTHORITY:CODE"):
        GeometryContract(crs="just-a-string")


def test_geometry_crs_bare_number_raises() -> None:
    with pytest.raises(ValidationError):
        GeometryContract(crs="4326")


# ── GeometryContract.type ─────────────────────────────────────────────────────


def test_geometry_type_valid_types() -> None:
    g = GeometryContract(type=["Point", "MultiPoint", "Polygon"])
    assert g.type == ["Point", "MultiPoint", "Polygon"]


def test_geometry_type_unknown_raises() -> None:
    with pytest.raises(ValidationError, match="Unknown geometry type"):
        GeometryContract(type=["Point", "NotAType"])


def test_geometry_type_none_is_allowed() -> None:
    g = GeometryContract(type=None)
    assert g.type is None


# ── BoundsWithinConfig.bbox ───────────────────────────────────────────────────


def test_bbox_valid() -> None:
    b = BoundsWithinConfig(bbox=[-10.0, -5.0, 10.0, 5.0])
    assert b.bbox == [-10.0, -5.0, 10.0, 5.0]


def test_bbox_wrong_length_raises() -> None:
    with pytest.raises(ValidationError, match="exactly 4"):
        BoundsWithinConfig(bbox=[-10.0, -5.0, 10.0])


def test_bbox_minx_gte_maxx_raises() -> None:
    with pytest.raises(ValidationError, match="minx"):
        BoundsWithinConfig(bbox=[10.0, -5.0, 5.0, 5.0])


def test_bbox_miny_gte_maxy_raises() -> None:
    with pytest.raises(ValidationError, match="miny"):
        BoundsWithinConfig(bbox=[-10.0, 5.0, 10.0, 5.0])


def test_bbox_none_is_allowed() -> None:
    b = BoundsWithinConfig(bbox=None)
    assert b.bbox is None


# ── AttributeContract min/max ─────────────────────────────────────────────────


def test_attribute_min_lt_max_is_valid() -> None:
    a = AttributeContract(min=0.0, max=100.0)
    assert a.min == 0.0
    assert a.max == 100.0


def test_attribute_min_eq_max_is_valid() -> None:
    a = AttributeContract(min=5.0, max=5.0)
    assert a.min == 5.0


def test_attribute_min_gt_max_raises() -> None:
    with pytest.raises(ValidationError, match="min"):
        AttributeContract(min=100.0, max=0.0)


def test_attribute_min_only_is_valid() -> None:
    a = AttributeContract(min=0.0)
    assert a.max is None


def test_attribute_max_only_is_valid() -> None:
    a = AttributeContract(max=100.0)
    assert a.min is None
