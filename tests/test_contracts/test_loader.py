"""Tests for contract loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from geoassert.contracts.loader import load_contract
from geoassert.contracts.schema import Contract
from geoassert.exceptions import ContractError

_VALID_YAML = """\
geoassert_version: "0.1"
dataset: buildings
source:
  path: data/buildings.parquet
  format: geoparquet
geometry:
  column: geometry
  type:
    - Polygon
    - MultiPolygon
  crs: EPSG:4326
  valid: true
  allow_empty: false
attributes:
  building_id:
    nullable: false
    unique: true
  height_m:
    nullable: true
    min: 0
    max: 400
"""


def test_load_valid_contract(tmp_path: Path) -> None:
    p = tmp_path / "contract.yml"
    p.write_text(_VALID_YAML)
    contract = load_contract(p)
    assert isinstance(contract, Contract)
    assert contract.dataset == "buildings"
    assert contract.geometry is not None
    assert contract.geometry.crs == "EPSG:4326"
    assert "building_id" in contract.attributes
    assert contract.attributes["building_id"].nullable is False
    assert contract.attributes["building_id"].unique is True
    assert contract.attributes["height_m"].max == 400.0


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ContractError, match="not found"):
        load_contract(tmp_path / "nope.yml")


def test_load_invalid_yaml_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.yml"
    p.write_text(":\n  - broken: [unclosed")
    with pytest.raises(ContractError):
        load_contract(p)


def test_load_minimal_contract(tmp_path: Path) -> None:
    p = tmp_path / "minimal.yml"
    p.write_text("dataset: minimal\n")
    contract = load_contract(p)
    assert contract.dataset == "minimal"
    assert contract.geometry is None
