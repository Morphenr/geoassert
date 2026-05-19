"""JUnit XML report renderer.

Produces output compatible with GitHub Actions test reporters, Jenkins,
and other CI tools that consume JUnit XML.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element, SubElement, indent, tostring

if TYPE_CHECKING:
    from geoassert.result import ValidationResult


def render_junit(result: ValidationResult) -> str:
    """Return a JUnit XML string for the validation result."""
    dataset = str(result.stats.get("path", "dataset"))
    n_tests = len(result.checks)
    n_failures = len(result.failures)

    testsuites = Element(
        "testsuites",
        {"name": "geoassert", "tests": str(n_tests), "failures": str(n_failures), "errors": "0"},
    )
    suite = SubElement(
        testsuites,
        "testsuite",
        {"name": dataset, "tests": str(n_tests), "failures": str(n_failures)},
    )

    for check in result.checks:
        category = check.check.rsplit(".", 1)[0] if "." in check.check else "geoassert"
        case = SubElement(
            suite,
            "testcase",
            {"classname": f"geoassert.{category}", "name": check.check},
        )
        if check.status == "fail":
            parts = [check.message]
            if check.expected is not None:
                parts.append(f"Expected: {check.expected}")
            if check.observed is not None:
                parts.append(f"Observed: {check.observed}")
            if check.why_it_matters:
                parts.append(f"Why it matters: {check.why_it_matters}")
            if check.suggestion:
                parts.append(f"Suggestion: {check.suggestion}")
            failure = SubElement(
                case,
                "failure",
                {"type": "ValidationFailure", "message": check.message},
            )
            failure.text = "\n".join(parts)
        elif check.status == "skip":
            SubElement(case, "skipped", {"message": check.message})

    indent(testsuites, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(testsuites, encoding="unicode")
