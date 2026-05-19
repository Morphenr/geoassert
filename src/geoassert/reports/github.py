"""GitHub Actions annotation output."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from geoassert.result import ValidationResult


def render_github_annotations(result: ValidationResult, console: Console) -> None:
    """Emit ::error and ::warning workflow commands for GitHub Actions."""
    for check in result.checks:
        if check.status == "fail":
            console.print(
                f"::error title=geoassert/{check.check}::{check.message}"
                + (f" Suggestion: {check.suggestion}" if check.suggestion else ""),
                highlight=False,
            )
        elif check.status == "warn":
            console.print(
                f"::warning title=geoassert/{check.check}::{check.message}"
                + (f" Suggestion: {check.suggestion}" if check.suggestion else ""),
                highlight=False,
            )
