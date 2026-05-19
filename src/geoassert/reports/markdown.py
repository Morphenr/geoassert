"""Markdown report renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geoassert.result import CheckResult, ValidationResult

_STATUS_ICON = {"pass": "✅", "warn": "⚠️", "fail": "❌", "skip": "⏭️"}


def render_validation_result(result: ValidationResult) -> str:
    lines: list[str] = []
    path = result.stats.get("path", "Dataset")
    overall = "PASSED ✅" if result.passed else "FAILED ❌"

    lines += [
        "# geoassert validation report",
        "",
        f"**Dataset:** `{path}`  ",
        f"**Result:** {overall}  ",
    ]
    if result.stats.get("rows") is not None:
        lines.append(f"**Rows:** {result.stats['rows']:,}  ")
    lines.append("")

    # Stats table
    n_pass = sum(1 for c in result.checks if c.status == "pass")
    n_warn = len(result.warnings)
    n_fail = len(result.failures)
    n_skip = sum(1 for c in result.checks if c.status == "skip")
    lines += [
        "## Summary",
        "",
        "| Checks run | Passed | Warnings | Failed | Skipped |",
        "|:----------:|:------:|:--------:|:------:|:-------:|",
        f"| {len(result.checks)} | {n_pass} | {n_warn} | {n_fail} | {n_skip} |",
        "",
    ]

    # Checks grouped by category
    lines += ["## Checks", ""]
    for category, checks in _group_by_category(result.checks).items():
        lines.append(f"### {category}")
        lines.append("")
        lines.append("| Status | Check | Message |")
        lines.append("|--------|-------|---------|")
        for c in checks:
            icon = _STATUS_ICON.get(c.status, c.status)
            lines.append(f"| {icon} | `{c.check}` | {c.message} |")
        lines.append("")

    if result.failures:
        lines += ["## Failures", ""]
        for f in result.failures:
            lines.append(f"### `{f.check}`")
            lines.append("")
            lines.append(f"**Message:** {f.message}  ")
            if f.expected is not None:
                lines.append(f"**Expected:** `{f.expected}`  ")
            if f.observed is not None:
                lines.append(f"**Observed:** `{f.observed}`  ")
            if f.affected_rows is not None:
                lines.append(f"**Affected rows:** {f.affected_rows:,}  ")
            if f.why_it_matters:
                lines.append(f"**Why it matters:** {f.why_it_matters}  ")
            if f.suggestion:
                lines.append(f"**Suggestion:** {f.suggestion}  ")
            lines.append("")

    if result.warnings:
        lines += ["## Warnings", ""]
        for w in result.warnings:
            lines.append(f"- ⚠️ **`{w.check}`** — {w.message}")
            if w.suggestion:
                lines.append(f"  _{w.suggestion}_")
        lines.append("")

    return "\n".join(lines)


def _group_by_category(checks: list[CheckResult]) -> dict[str, list[CheckResult]]:
    groups: dict[str, list[CheckResult]] = {}
    for c in checks:
        cat = c.check.split(".")[0]
        groups.setdefault(cat, []).append(c)
    return groups
