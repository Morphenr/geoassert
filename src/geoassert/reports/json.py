"""JSON report renderer."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geoassert.result import ValidationResult


def render_json(result: ValidationResult, indent: int = 2) -> str:
    return result.to_json(indent=indent)
