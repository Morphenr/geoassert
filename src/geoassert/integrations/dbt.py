"""dbt integration — discover and validate dbt model outputs.

Reads dbt's ``target/manifest.json`` to locate model materializations, then
runs geoassert validation against each model's output.

No additional dependencies required beyond geoassert core.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DbtModel:
    """Represents a single dbt model parsed from the manifest."""

    unique_id: str
    name: str
    materialized: str  # "table" | "view" | "incremental" | "ephemeral"
    database: str
    schema: str
    alias: str
    relation_name: str | None = None
    tags: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return f"{self.database}.{self.schema}.{self.alias}"

    @property
    def project(self) -> str:
        """Extract the dbt project name from the unique_id."""
        parts = self.unique_id.split(".")
        return parts[1] if len(parts) >= 2 else ""


def find_manifest(project_dir: Path | str | None = None) -> Path:
    """Locate dbt's manifest.json, searching common locations.

    Args:
        project_dir: dbt project root. Defaults to the current directory.

    Returns:
        Path to manifest.json.

    Raises:
        FileNotFoundError: If no manifest.json can be found.
    """
    root = Path(project_dir) if project_dir else Path.cwd()
    candidates = [
        root / "target" / "manifest.json",
        root / "manifest.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No manifest.json found. Run 'dbt compile' or 'dbt run' first.\n"
        f"Searched: {[str(c) for c in candidates]}"
    )


def load_manifest(manifest_path: Path | str) -> dict[str, Any]:
    """Load and parse a dbt manifest.json file."""
    path = Path(manifest_path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid manifest.json at {path}: {exc}") from exc


def list_models(manifest: dict[str, Any]) -> list[DbtModel]:
    """Extract all model nodes from a dbt manifest.

    Args:
        manifest: Parsed manifest.json dictionary.

    Returns:
        List of :class:`DbtModel` objects, one per model node.
    """
    models: list[DbtModel] = []
    for uid, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") != "model":
            continue
        config = node.get("config", {})
        models.append(
            DbtModel(
                unique_id=uid,
                name=node.get("name", ""),
                materialized=config.get("materialized", "table"),
                database=node.get("database", ""),
                schema=node.get("schema", ""),
                alias=node.get("alias", node.get("name", "")),
                relation_name=node.get("relation_name"),
                tags=node.get("tags", []),
                meta=node.get("meta", {}),
            )
        )
    return sorted(models, key=lambda m: m.name)


def get_model(manifest: dict[str, Any], model_name: str) -> DbtModel:
    """Find a specific model by name.

    Args:
        manifest: Parsed manifest.json dictionary.
        model_name: Model name (not unique_id — just the model name).

    Returns:
        The matching :class:`DbtModel`.

    Raises:
        KeyError: If no model with that name exists.
    """
    all_models = {m.name: m for m in list_models(manifest)}
    if model_name not in all_models:
        available = sorted(all_models)
        raise KeyError(f"Model {model_name!r} not found in manifest. Available models: {available}")
    return all_models[model_name]


def validate_dbt_model(
    model: DbtModel,
    contract_path: Path | str,
    *,
    dsn: str | None = None,
    file_path: Path | str | None = None,
    sample: int | None = None,
    engine: str = "pyarrow",
) -> Any:
    """Validate a dbt model output against a geoassert contract.

    Dispatches based on materialization type and available connection info:

    - If ``file_path`` is provided, validates that file directly.
    - If ``dsn`` is provided and the model materializes to a PostGIS table,
      uses the PostGIS engine.
    - Otherwise raises ``ValueError`` with guidance.

    Args:
        model: A :class:`DbtModel` from :func:`list_models`.
        contract_path: Path to the geoassert contract YAML.
        dsn: PostgreSQL DSN for PostGIS-materialized models.
        file_path: Direct path override to a Parquet file.
        sample: Row limit for row-level checks.
        engine: Compute engine (``"pyarrow"`` or ``"duckdb"``).

    Returns:
        A :class:`~geoassert.result.ValidationResult`.
    """
    from geoassert.contracts.loader import load_contract
    from geoassert.runner import run_validation, run_validation_from_info

    contract = load_contract(contract_path)

    # Explicit file path override
    if file_path is not None:
        return run_validation(file_path, contract, sample=sample, engine=engine)

    # PostGIS table
    if dsn is not None:
        from geoassert.engines.postgis import read_postgis_info

        info = read_postgis_info(
            dsn,
            model.alias,
            schema=model.schema,
            sample=sample,
        )
        return run_validation_from_info(info, contract)

    raise ValueError(
        f"Cannot validate model {model.name!r} (materialized as {model.materialized!r}) "
        "without connection information.\n"
        "Provide --dsn for PostGIS models or --path for file-based models."
    )
