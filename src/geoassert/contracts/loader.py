"""Contract YAML loader."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from geoassert.contracts.schema import Contract
from geoassert.exceptions import ContractError


def load_contract(path: Path | str) -> Contract:
    """Parse a YAML contract file into a Contract model."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise ContractError(f"Contract file not found: {path}")
    except yaml.YAMLError as exc:
        raise ContractError(f"Invalid YAML in contract {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ContractError(f"Contract must be a YAML mapping, got {type(raw).__name__}")

    try:
        return Contract.model_validate(raw)
    except ValidationError as exc:
        raise ContractError(f"Contract validation failed:\n{exc}") from exc
