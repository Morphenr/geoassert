"""Tests for the validate_source() public API and run_validation_from_info()."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pyarrow as pa

from geoassert.engines.pyarrow import DatasetInfo
from geoassert.runner import run_validation_from_info

sys.path.insert(0, str(Path(__file__).parents[2]))
from tests.conftest import make_contract  # noqa: E402


def _wkb_point(x: float, y: float) -> bytes:
    return struct.pack("<bIdd", 1, 1, x, y)


def _make_warehouse_info(source_type: str = "postgis", n_rows: int = 3) -> DatasetInfo:
    wkb_data = [_wkb_point(float(i), float(i)) for i in range(n_rows)]
    tbl = pa.table({"geometry": pa.array(wkb_data, type=pa.binary())})
    geo_metadata = {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {
            "geometry": {
                "encoding": "WKB",
                "geometry_types": [],
                "crs": {
                    "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
                    "type": "GeographicCRS",
                    "name": "EPSG:4326",
                    "id": {"authority": "EPSG", "code": 4326},
                },
            }
        },
    }
    return DatasetInfo(
        path=f"{source_type}://db/schema/table",
        schema=tbl.schema,
        num_rows=n_rows,
        geo_metadata=geo_metadata,
        source_type=source_type,
        table=tbl,
    )


class TestRunValidationFromInfo:
    def test_returns_validation_result(self) -> None:
        from geoassert.result import ValidationResult

        info = _make_warehouse_info("postgis")
        contract = make_contract()
        result = run_validation_from_info(info, contract)
        assert isinstance(result, ValidationResult)

    def test_geoparquet_checks_skipped_for_warehouse(self) -> None:
        info = _make_warehouse_info("bigquery")
        contract = make_contract()
        result = run_validation_from_info(info, contract)
        gp_checks = [c for c in result.checks if c.check == "geoparquet"]
        assert all(c.status == "skip" for c in gp_checks)

    def test_stats_include_source_type(self) -> None:
        info = _make_warehouse_info("snowflake")
        contract = make_contract()
        result = run_validation_from_info(info, contract)
        assert result.stats["source_type"] == "snowflake"

    def test_stats_include_row_count(self) -> None:
        info = _make_warehouse_info("postgis", n_rows=7)
        contract = make_contract()
        result = run_validation_from_info(info, contract)
        assert result.stats["rows"] == 7

    def test_crs_check_runs_for_warehouse(self) -> None:
        info = _make_warehouse_info("postgis")
        contract = make_contract()
        result = run_validation_from_info(info, contract)
        crs_checks = [c for c in result.checks if "crs" in c.check]
        assert len(crs_checks) > 0

    def test_bounds_check_runs_for_warehouse(self) -> None:
        info = _make_warehouse_info("postgis")
        contract = make_contract(bounds={"min_x": -180, "max_x": 180, "min_y": -90, "max_y": 90})
        result = run_validation_from_info(info, contract)
        bounds_checks = [c for c in result.checks if "bounds" in c.check]
        assert len(bounds_checks) > 0


class TestValidateSourcePublicAPI:
    def test_validate_source_accepts_dataset_info(self) -> None:
        import geoassert as ga

        info = _make_warehouse_info("postgis")
        contract = make_contract()
        result = ga.validate_source(info, contract)
        assert result is not None

    def test_validate_source_accepts_contract_path(self, tmp_path: Path) -> None:
        import geoassert as ga

        contract_path = tmp_path / "contract.yml"
        contract_path.write_text("dataset: test\n", encoding="utf-8")

        info = _make_warehouse_info("bigquery")
        result = ga.validate_source(info, contract_path)
        assert result.stats["source_type"] == "bigquery"
