"""Tests for the HTML report renderer and --report-out CLI flag."""

from __future__ import annotations

from pathlib import Path

import pytest

from geoassert.result import CheckResult, ValidationResult


def _make_result(
    *,
    passed: bool = True,
    n_pass: int = 2,
    n_warn: int = 0,
    n_fail: int = 0,
    path: str = "test.parquet",
    rows: int = 100,
) -> ValidationResult:
    checks: list[CheckResult] = []
    for i in range(n_pass):
        checks.append(
            CheckResult(check=f"crs.check{i}", status="pass", severity="info", message="OK")
        )
    for i in range(n_warn):
        checks.append(
            CheckResult(
                check=f"bounds.warn{i}",
                status="warn",
                severity="warn",
                message="Possible issue",
                suggestion="Check your data.",
            )
        )
    for i in range(n_fail):
        checks.append(
            CheckResult(
                check=f"geometry.fail{i}",
                status="fail",
                severity="error",
                message="Something broke",
                expected="valid",
                observed="invalid",
                affected_rows=3,
                why_it_matters="Breaks spatial joins.",
                suggestion="Fix geometry.",
            )
        )
    failures = [c for c in checks if c.status == "fail"]
    warnings = [c for c in checks if c.status == "warn"]
    return ValidationResult(
        passed=passed,
        checks=checks,
        failures=failures,
        warnings=warnings,
        stats={"path": path, "rows": rows},
    )


class TestHtmlReport:
    def test_render_returns_string(self) -> None:
        result = _make_result()
        html = result.to_html()
        assert isinstance(html, str)

    def test_contains_doctype(self) -> None:
        html = _make_result().to_html()
        assert "<!DOCTYPE html>" in html

    def test_contains_path(self) -> None:
        html = _make_result(path="data/buildings.parquet").to_html()
        assert "data/buildings.parquet" in html

    def test_passed_badge_present(self) -> None:
        html = _make_result(passed=True).to_html()
        assert "PASSED" in html

    def test_failed_badge_present(self) -> None:
        html = _make_result(passed=False, n_fail=1).to_html()
        assert "FAILED" in html

    def test_check_names_in_output(self) -> None:
        html = _make_result(n_pass=2).to_html()
        assert "crs.check0" in html
        assert "crs.check1" in html

    def test_failure_detail_section(self) -> None:
        html = _make_result(passed=False, n_fail=2).to_html()
        assert "Failures" in html
        assert "geometry.fail0" in html
        assert "geometry.fail1" in html

    def test_failure_expected_observed(self) -> None:
        html = _make_result(passed=False, n_fail=1).to_html()
        assert "Expected" in html
        assert "valid" in html
        assert "Observed" in html
        assert "invalid" in html

    def test_failure_suggestion_and_why(self) -> None:
        html = _make_result(passed=False, n_fail=1).to_html()
        assert "Fix geometry" in html
        assert "Breaks spatial joins" in html

    def test_warnings_section(self) -> None:
        html = _make_result(n_warn=1).to_html()
        assert "Warnings" in html
        assert "bounds.warn0" in html

    def test_summary_stats_present(self) -> None:
        html = _make_result(n_pass=3, n_warn=1, n_fail=2).to_html()
        assert "3" in html  # pass count
        assert "1" in html  # warn count
        assert "2" in html  # fail count

    def test_no_failures_section_when_clean(self) -> None:
        html = _make_result(passed=True, n_pass=3).to_html()
        assert "geometry.fail" not in html

    def test_html_escape_prevents_xss(self) -> None:
        result = _make_result()
        result.stats["path"] = "<script>alert('xss')</script>"
        html = result.to_html()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_row_count_shown(self) -> None:
        html = _make_result(rows=12345).to_html()
        assert "12,345" in html

    def test_skip_status_rendered(self) -> None:
        result = _make_result(n_pass=0)
        result.checks.append(
            CheckResult(
                check="geometry.valid", status="skip", severity="info", message="No shapely"
            )
        )
        html = result.to_html()
        assert "SKIP" in html


class TestReportOut:
    def test_report_out_writes_html(self, tmp_path: Path) -> None:

        from typer.testing import CliRunner

        from geoassert.cli import app

        parquet = Path("examples/buildings.parquet")
        contract = Path("examples/buildings_contract.yml")
        if not parquet.exists() or not contract.exists():
            pytest.skip("example files not present")

        out = tmp_path / "report.html"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "validate",
                str(parquet),
                "--contract",
                str(contract),
                "--format",
                "html",
                "--report-out",
                str(out),
            ],
        )
        assert out.exists(), f"report not written; exit={result.exit_code}"
        content = out.read_text()
        assert "<!DOCTYPE html>" in content
        assert "buildings" in content

    def test_report_out_writes_json(self, tmp_path: Path) -> None:
        import json

        from typer.testing import CliRunner

        from geoassert.cli import app

        parquet = Path("examples/buildings.parquet")
        contract = Path("examples/buildings_contract.yml")
        if not parquet.exists() or not contract.exists():
            pytest.skip("example files not present")

        out = tmp_path / "report.json"
        runner = CliRunner()
        runner.invoke(
            app,
            [
                "validate",
                str(parquet),
                "--contract",
                str(contract),
                "--format",
                "json",
                "--report-out",
                str(out),
            ],
        )
        assert out.exists()
        data = json.loads(out.read_text())
        assert "checks" in data

    def test_report_out_writes_markdown(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from geoassert.cli import app

        parquet = Path("examples/buildings.parquet")
        contract = Path("examples/buildings_contract.yml")
        if not parquet.exists() or not contract.exists():
            pytest.skip("example files not present")

        out = tmp_path / "report.md"
        runner = CliRunner()
        runner.invoke(
            app,
            [
                "validate",
                str(parquet),
                "--contract",
                str(contract),
                "--format",
                "markdown",
                "--report-out",
                str(out),
            ],
        )
        assert out.exists()
        content = out.read_text()
        assert "# geoassert" in content
