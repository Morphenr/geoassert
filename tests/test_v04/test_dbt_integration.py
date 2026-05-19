"""Tests for the dbt integration module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoassert.integrations.dbt import (
    DbtModel,
    find_manifest,
    get_model,
    list_models,
    load_manifest,
)

# ── manifest fixtures ──────────────────────────────────────────────────────────

MINIMAL_MANIFEST: dict = {
    "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v10.json"},
    "nodes": {
        "model.my_project.buildings": {
            "resource_type": "model",
            "name": "buildings",
            "database": "my_db",
            "schema": "public",
            "alias": "buildings",
            "relation_name": '"my_db"."public"."buildings"',
            "tags": ["geo", "nightly"],
            "meta": {"owner": "geo-team"},
            "config": {"materialized": "table"},
        },
        "model.my_project.roads": {
            "resource_type": "model",
            "name": "roads",
            "database": "my_db",
            "schema": "public",
            "alias": "roads",
            "relation_name": '"my_db"."public"."roads"',
            "tags": [],
            "meta": {},
            "config": {"materialized": "view"},
        },
        "test.my_project.not_null_buildings_id": {
            "resource_type": "test",
            "name": "not_null_buildings_id",
        },
    },
}


@pytest.fixture()
def manifest_file(tmp_path: Path) -> Path:
    path = tmp_path / "target" / "manifest.json"
    path.parent.mkdir()
    path.write_text(json.dumps(MINIMAL_MANIFEST), encoding="utf-8")
    return path


# ── find_manifest ──────────────────────────────────────────────────────────────


def test_find_manifest_target_subdir(manifest_file: Path) -> None:
    project_dir = manifest_file.parent.parent
    found = find_manifest(project_dir)
    assert found == manifest_file


def test_find_manifest_root_fallback(tmp_path: Path) -> None:
    root_manifest = tmp_path / "manifest.json"
    root_manifest.write_text(json.dumps(MINIMAL_MANIFEST), encoding="utf-8")
    found = find_manifest(tmp_path)
    assert found == root_manifest


def test_find_manifest_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="manifest.json"):
        find_manifest(tmp_path)


# ── load_manifest ──────────────────────────────────────────────────────────────


def test_load_manifest_valid(manifest_file: Path) -> None:
    manifest = load_manifest(manifest_file)
    assert "nodes" in manifest


def test_load_manifest_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "manifest.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid manifest.json"):
        load_manifest(bad)


# ── list_models ────────────────────────────────────────────────────────────────


def test_list_models_filters_tests(manifest_file: Path) -> None:
    manifest = load_manifest(manifest_file)
    models = list_models(manifest)
    names = [m.name for m in models]
    assert "buildings" in names
    assert "roads" in names
    assert "not_null_buildings_id" not in names


def test_list_models_sorted_by_name(manifest_file: Path) -> None:
    manifest = load_manifest(manifest_file)
    models = list_models(manifest)
    assert [m.name for m in models] == sorted(m.name for m in models)


def test_list_models_populates_fields(manifest_file: Path) -> None:
    manifest = load_manifest(manifest_file)
    models = {m.name: m for m in list_models(manifest)}
    b = models["buildings"]
    assert b.materialized == "table"
    assert b.database == "my_db"
    assert b.schema == "public"
    assert b.alias == "buildings"
    assert b.tags == ["geo", "nightly"]
    assert b.meta == {"owner": "geo-team"}


def test_list_models_empty_manifest() -> None:
    models = list_models({"nodes": {}})
    assert models == []


# ── get_model ──────────────────────────────────────────────────────────────────


def test_get_model_found(manifest_file: Path) -> None:
    manifest = load_manifest(manifest_file)
    model = get_model(manifest, "roads")
    assert model.name == "roads"
    assert model.materialized == "view"


def test_get_model_not_found(manifest_file: Path) -> None:
    manifest = load_manifest(manifest_file)
    with pytest.raises(KeyError, match="not_a_model"):
        get_model(manifest, "not_a_model")


# ── DbtModel properties ────────────────────────────────────────────────────────


def test_dbt_model_full_name() -> None:
    model = DbtModel(
        unique_id="model.proj.buildings",
        name="buildings",
        materialized="table",
        database="my_db",
        schema="public",
        alias="buildings",
    )
    assert model.full_name == "my_db.public.buildings"


def test_dbt_model_project_extracted_from_unique_id() -> None:
    model = DbtModel(
        unique_id="model.my_project.buildings",
        name="buildings",
        materialized="table",
        database="db",
        schema="s",
        alias="buildings",
    )
    assert model.project == "my_project"


# ── validate_dbt_model ─────────────────────────────────────────────────────────


def test_validate_dbt_model_file_path(tmp_path: Path) -> None:
    """validate_dbt_model with file_path delegates to run_validation."""
    import sys

    sys.path.insert(0, str(Path(__file__).parents[2]))
    from tests.conftest import write_test_geoparquet  # noqa: E402

    parquet = write_test_geoparquet(tmp_path / "buildings.parquet")
    contract_path = tmp_path / "contract.yml"
    contract_path.write_text("dataset: buildings\n", encoding="utf-8")

    model = DbtModel(
        unique_id="model.proj.buildings",
        name="buildings",
        materialized="table",
        database="db",
        schema="public",
        alias="buildings",
    )

    from geoassert.integrations.dbt import validate_dbt_model

    result = validate_dbt_model(model, contract_path, file_path=parquet)
    assert result is not None


def test_validate_dbt_model_no_connection_raises(tmp_path: Path) -> None:
    contract_path = tmp_path / "contract.yml"
    contract_path.write_text("dataset: buildings\n", encoding="utf-8")

    model = DbtModel(
        unique_id="model.proj.buildings",
        name="buildings",
        materialized="table",
        database="db",
        schema="public",
        alias="buildings",
    )

    from geoassert.integrations.dbt import validate_dbt_model

    with pytest.raises(ValueError, match="Cannot validate model"):
        validate_dbt_model(model, contract_path)
