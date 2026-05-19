"""Tests for 0.2 report formats — JUnit XML and richer Markdown."""

from __future__ import annotations

from geoassert.reports.junit import render_junit
from geoassert.reports.markdown import render_validation_result
from geoassert.result import CheckResult, ValidationResult


def _make_result(
    passed: bool = True,
    checks: list[CheckResult] | None = None,
) -> ValidationResult:
    checks = checks or []
    failures = [c for c in checks if c.status == "fail"]
    warnings = [c for c in checks if c.status == "warn"]
    return ValidationResult(
        passed=passed,
        failures=failures,
        warnings=warnings,
        checks=checks,
        stats={"path": "data/test.parquet", "rows": 1000},
    )


# ── JUnit XML ─────────────────────────────────────────────────────────────────


def test_junit_xml_declaration() -> None:
    result = _make_result()
    xml = render_junit(result)
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')


def test_junit_xml_contains_testsuites() -> None:
    result = _make_result()
    xml = render_junit(result)
    assert "<testsuites" in xml
    assert "<testsuite" in xml


def test_junit_xml_pass_has_no_failure_element() -> None:
    checks = [
        CheckResult("crs.exists", "pass", "info", "CRS found."),
    ]
    xml = render_junit(_make_result(checks=checks))
    assert "<failure" not in xml


def test_junit_xml_fail_has_failure_element() -> None:
    checks = [
        CheckResult(
            "crs.match",
            "fail",
            "error",
            "CRS mismatch.",
            expected="EPSG:4326",
            observed="EPSG:32630",
            suggestion="Fix it.",
        ),
    ]
    xml = render_junit(_make_result(passed=False, checks=checks))
    assert "<failure" in xml
    assert "CRS mismatch." in xml
    assert "Expected: EPSG:4326" in xml
    assert "Suggestion: Fix it." in xml


def test_junit_xml_skip_has_skipped_element() -> None:
    checks = [
        CheckResult("bounds.within", "skip", "info", "No contract bounds."),
    ]
    xml = render_junit(_make_result(checks=checks))
    assert "<skipped" in xml


def test_junit_xml_test_counts_match() -> None:
    checks = [
        CheckResult("crs.exists", "pass", "info", "ok"),
        CheckResult("crs.match", "fail", "error", "bad"),
    ]
    xml = render_junit(_make_result(passed=False, checks=checks))
    assert 'tests="2"' in xml
    assert 'failures="1"' in xml


# ── Richer Markdown ───────────────────────────────────────────────────────────


def test_markdown_contains_summary_table() -> None:
    result = _make_result(checks=[CheckResult("crs.exists", "pass", "info", "ok")])
    md = render_validation_result(result)
    assert "## Summary" in md
    assert "| Checks run |" in md


def test_markdown_groups_checks_by_category() -> None:
    checks = [
        CheckResult("geoparquet.geo_metadata", "pass", "info", "ok"),
        CheckResult("crs.exists", "pass", "info", "ok"),
        CheckResult("bounds.available", "warn", "warn", "no bbox"),
    ]
    result = _make_result(checks=checks)
    md = render_validation_result(result)
    assert "### geoparquet" in md
    assert "### crs" in md
    assert "### bounds" in md


def test_markdown_shows_failures_section_when_failures_present() -> None:
    checks = [
        CheckResult(
            "crs.match",
            "fail",
            "error",
            "CRS mismatch.",
            expected="EPSG:4326",
            observed="EPSG:32630",
            why_it_matters="Axis order differs.",
            suggestion="Fix the CRS.",
        ),
    ]
    result = _make_result(passed=False, checks=checks)
    md = render_validation_result(result)
    assert "## Failures" in md
    assert "Expected" in md
    assert "Suggestion" in md
    assert "Why it matters" in md


def test_markdown_shows_warnings_section_when_warnings_present() -> None:
    checks = [
        CheckResult("bounds.available", "warn", "warn", "No bbox metadata.", suggestion="Add it."),
    ]
    result = _make_result(checks=checks)
    md = render_validation_result(result)
    assert "## Warnings" in md
    assert "Add it." in md


def test_markdown_passed_shows_green_icon() -> None:
    result = _make_result(passed=True)
    md = render_validation_result(result)
    assert "PASSED" in md


def test_markdown_failed_shows_red_icon() -> None:
    checks = [CheckResult("crs.match", "fail", "error", "bad")]
    result = _make_result(passed=False, checks=checks)
    md = render_validation_result(result)
    assert "FAILED" in md
