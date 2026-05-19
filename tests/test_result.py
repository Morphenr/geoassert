"""Tests for result models."""

from __future__ import annotations

import json

from geoassert.result import CheckResult, ValidationResult


def test_check_result_to_dict_omits_none():
    c = CheckResult(check="foo.bar", status="pass", severity="info", message="ok")
    d = c.to_dict()
    assert "suggestion" not in d
    assert d["status"] == "pass"


def test_validation_result_to_json():
    r = ValidationResult(
        passed=True,
        checks=[CheckResult(check="x", status="pass", severity="info", message="ok")],
    )
    parsed = json.loads(r.to_json())
    assert parsed["passed"] is True
    assert len(parsed["checks"]) == 1


def test_validation_result_to_markdown_contains_heading():
    r = ValidationResult(
        passed=False,
        failures=[
            CheckResult(
                check="a.b",
                status="fail",
                severity="error",
                message="bad thing",
                suggestion="fix it",
            ),
        ],
        checks=[
            CheckResult(check="a.b", status="fail", severity="error", message="bad thing"),
        ],
    )
    md = r.to_markdown()
    assert "# geoassert" in md
    assert "FAILED" in md
    assert "a.b" in md
