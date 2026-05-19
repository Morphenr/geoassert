"""CLI smoke tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from geoassert.cli import app
from tests.conftest import write_test_geoparquet

runner = CliRunner()


def test_profile_text(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "data.parquet")
    result = runner.invoke(app, ["profile", str(path)])
    assert result.exit_code == 0
    assert "Rows" in result.output


def test_profile_json(tmp_path: Path) -> None:
    import json

    path = write_test_geoparquet(tmp_path / "data.parquet")
    result = runner.invoke(app, ["profile", str(path), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["rows"] == 3


def test_profile_missing_file() -> None:
    result = runner.invoke(app, ["profile", "/no/such/file.parquet"])
    assert result.exit_code == 3


def test_init_contract(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "data.parquet")
    result = runner.invoke(app, ["init-contract", str(path)])
    assert result.exit_code == 0
    assert "geoassert_version" in result.output


def test_geoparquet_check_pass(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "data.parquet")
    result = runner.invoke(app, ["geoparquet", "check", str(path)])
    assert result.exit_code == 0


def test_geoparquet_check_no_meta(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "no_meta.parquet", include_geo_meta=False)
    result = runner.invoke(app, ["geoparquet", "check", str(path)])
    assert result.exit_code == 1


def test_validate_with_contract(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "data.parquet")
    contract_path = tmp_path / "contract.yml"
    contract_path.write_text("dataset: test\n")
    result = runner.invoke(app, ["validate", str(path), "--contract", str(contract_path)])
    assert result.exit_code == 0


def test_validate_missing_contract(tmp_path: Path) -> None:
    path = write_test_geoparquet(tmp_path / "data.parquet")
    result = runner.invoke(app, ["validate", str(path), "--contract", "/no/contract.yml"])
    assert result.exit_code == 2
