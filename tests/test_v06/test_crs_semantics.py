"""Tests for v0.6 CRS semantic checks: equivalence and axis order."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa

from geoassert.checks.crs import CRSAxisOrderCheck, CRSMatchCheck, _are_equivalent
from geoassert.contracts.schema import Contract
from geoassert.engines.pyarrow import DatasetInfo


def _geo_meta(crs_authority: str, crs_code: int | str) -> dict:
    return {
        "primary_column": "geometry",
        "columns": {
            "geometry": {
                "encoding": "WKB",
                "crs": {"id": {"authority": crs_authority, "code": crs_code}},
            }
        },
    }


def _info(crs_authority: str = "EPSG", crs_code: int | str = 4326) -> DatasetInfo:
    return DatasetInfo(
        path=Path("/tmp/x.parquet"),
        schema=pa.schema([pa.field("geometry", pa.binary())]),
        num_rows=10,
        geo_metadata=_geo_meta(crs_authority, crs_code),
    )


def _contract(crs: str, allow_equiv: bool = False) -> Contract:
    return Contract.model_validate({"geometry": {"crs": crs, "allow_equivalent_crs": allow_equiv}})


# ── _are_equivalent ────────────────────────────────────────────────────────────


class TestAreEquivalent:
    def test_epsg4326_equals_ogc_crs84(self) -> None:
        assert _are_equivalent("EPSG:4326", "OGC:CRS84")

    def test_ogc_crs84_equals_epsg4326(self) -> None:
        assert _are_equivalent("OGC:CRS84", "EPSG:4326")

    def test_crs84_alias(self) -> None:
        assert _are_equivalent("CRS84", "EPSG:4326")

    def test_different_crs_not_equivalent(self) -> None:
        assert not _are_equivalent("EPSG:4326", "EPSG:3857")

    def test_same_crs_is_equivalent(self) -> None:
        assert _are_equivalent("EPSG:4326", "EPSG:4326")

    def test_web_mercator_group(self) -> None:
        assert _are_equivalent("EPSG:3857", "EPSG:900913")
        assert _are_equivalent("EPSG:3857", "EPSG:3785")

    def test_etrs89_group(self) -> None:
        assert _are_equivalent("EPSG:4258", "urn:ogc:def:crs:EPSG::4258")

    def test_unknown_crs_not_equivalent(self) -> None:
        assert not _are_equivalent("EPSG:9999", "EPSG:4326")


# ── CRSMatchCheck with allow_equivalent_crs ────────────────────────────────────


class TestCRSMatchEquivalence:
    def test_exact_match_passes(self) -> None:
        check = CRSMatchCheck()
        result = check.run(_info("EPSG", 4326), _contract("EPSG:4326"))
        assert result.status == "pass"

    def test_mismatch_fails_without_flag(self) -> None:
        check = CRSMatchCheck()
        result = check.run(_info("OGC", "CRS84"), _contract("EPSG:4326", allow_equiv=False))
        assert result.status == "fail"

    def test_equivalent_passes_with_flag(self) -> None:
        check = CRSMatchCheck()
        result = check.run(_info("OGC", "CRS84"), _contract("EPSG:4326", allow_equiv=True))
        assert result.status == "pass"
        assert "equivalent" in result.message.lower()

    def test_non_equivalent_fails_even_with_flag(self) -> None:
        check = CRSMatchCheck()
        result = check.run(_info("EPSG", 3857), _contract("EPSG:4326", allow_equiv=True))
        assert result.status == "fail"

    def test_no_crs_in_data_fails(self) -> None:
        info = DatasetInfo(
            path=Path("/tmp/x.parquet"),
            schema=pa.schema([]),
            num_rows=0,
            geo_metadata={"primary_column": "geometry", "columns": {"geometry": {}}},
        )
        result = CRSMatchCheck().run(info, _contract("EPSG:4326"))
        assert result.status == "fail"

    def test_no_contract_crs_skips(self) -> None:
        result = CRSMatchCheck().run(_info(), Contract.model_validate({}))
        assert result.status == "skip"

    def test_suggestion_mentions_allow_equivalent_crs(self) -> None:
        check = CRSMatchCheck()
        result = check.run(_info("OGC", "CRS84"), _contract("EPSG:4326", allow_equiv=False))
        assert result.suggestion is not None
        assert "allow_equivalent_crs" in result.suggestion


# ── CRSAxisOrderCheck ──────────────────────────────────────────────────────────


class TestCRSAxisOrderCheck:
    def test_epsg4326_warns(self) -> None:
        result = CRSAxisOrderCheck().run(_info("EPSG", 4326))
        assert result.status == "warn"

    def test_epsg4258_warns(self) -> None:
        result = CRSAxisOrderCheck().run(_info("EPSG", 4258))
        assert result.status == "warn"

    def test_ogc_crs84_passes(self) -> None:
        result = CRSAxisOrderCheck().run(_info("OGC", "CRS84"))
        assert result.status == "pass"

    def test_epsg3857_passes(self) -> None:
        result = CRSAxisOrderCheck().run(_info("EPSG", 3857))
        assert result.status == "pass"

    def test_no_crs_skips(self) -> None:
        info = DatasetInfo(
            path=Path("/tmp/x.parquet"),
            schema=pa.schema([]),
            num_rows=0,
            geo_metadata={},
        )
        result = CRSAxisOrderCheck().run(info)
        assert result.status == "skip"

    def test_warn_message_mentions_axis_order(self) -> None:
        result = CRSAxisOrderCheck().run(_info("EPSG", 4326))
        assert "axis" in result.message.lower() or "lat" in result.message.lower()

    def test_suggestion_mentions_ogc_crs84(self) -> None:
        result = CRSAxisOrderCheck().run(_info("EPSG", 4326))
        assert result.suggestion is not None
        assert "OGC:CRS84" in result.suggestion
