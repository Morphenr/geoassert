"""Validation result models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class CheckResult:
    check: str
    status: Literal["pass", "warn", "fail", "skip"]
    severity: Literal["info", "warn", "error"]
    message: str
    expected: Any | None = None
    observed: Any | None = None
    affected_rows: int | None = None
    suggestion: str | None = None
    why_it_matters: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class ValidationResult:
    passed: bool
    failures: list[CheckResult] = field(default_factory=list)
    warnings: list[CheckResult] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "stats": self.stats,
            "checks": [c.to_dict() for c in self.checks],
            "failures": [c.to_dict() for c in self.failures],
            "warnings": [c.to_dict() for c in self.warnings],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_markdown(self) -> str:
        from geoassert.reports.markdown import render_validation_result

        return render_validation_result(self)
