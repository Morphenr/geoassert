"""HTML report renderer — produces a self-contained, styled validation report."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geoassert.result import CheckResult, ValidationResult

_STATUS_LABEL = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}
_STATUS_COLOR = {
    "pass": "#16a34a",
    "warn": "#b45309",
    "fail": "#dc2626",
    "skip": "#6b7280",
}
_STATUS_BG = {
    "pass": "#f0fdf4",
    "warn": "#fffbeb",
    "fail": "#fef2f2",
    "skip": "#f9fafb",
}

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: #111827;
  background: #f9fafb;
  padding: 2rem 1rem;
}
.card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  max-width: 960px;
  margin: 0 auto 1.5rem;
  padding: 1.5rem;
}
h1 { font-size: 1.25rem; font-weight: 700; margin-bottom: 0.25rem; }
h2 { font-size: 1rem; font-weight: 600; margin: 1.25rem 0 0.75rem; }
.meta { color: #6b7280; font-size: 0.875rem; }
.badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-weight: 600;
  font-size: 0.75rem;
  letter-spacing: 0.04em;
}
.badge-pass { background: #dcfce7; color: #15803d; }
.badge-warn { background: #fef9c3; color: #854d0e; }
.badge-fail { background: #fee2e2; color: #991b1b; }
.badge-skip { background: #f3f4f6; color: #4b5563; }
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.75rem;
  margin: 1rem 0;
}
.stat-box {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 0.75rem;
  text-align: center;
}
.stat-box .num { font-size: 1.75rem; font-weight: 700; }
.stat-box .lbl {
  font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;
}
.num-pass { color: #16a34a; }
.num-warn { color: #b45309; }
.num-fail { color: #dc2626; }
.num-skip { color: #6b7280; }
table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
th { text-align: left; padding: 0.5rem 0.75rem; font-weight: 600;
     border-bottom: 2px solid #e5e7eb; background: #f9fafb; }
td { padding: 0.45rem 0.75rem; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
tr:last-child td { border-bottom: none; }
.check-name { font-family: ui-monospace, "Cascadia Code", monospace; font-size: 0.8rem; }
.detail-block {
  border-left: 3px solid #e5e7eb;
  padding: 0.5rem 0.75rem;
  margin: 0.5rem 0;
  font-size: 0.8rem;
  color: #374151;
}
.detail-block.fail { border-color: #fca5a5; background: #fef2f2; }
.detail-block.warn { border-color: #fcd34d; background: #fffbeb; }
.kv { display: flex; gap: 0.5rem; margin: 0.15rem 0; }
.kv .k { font-weight: 600; min-width: 6rem; color: #6b7280; }
.footer { text-align: center; color: #9ca3af; font-size: 0.75rem; margin-top: 1rem; }
"""


def render_html(result: ValidationResult) -> str:
    path = html.escape(str(result.stats.get("path", "Dataset")))
    overall = "PASSED" if result.passed else "FAILED"
    overall_cls = "pass" if result.passed else "fail"

    n_pass = sum(1 for c in result.checks if c.status == "pass")
    n_warn = len(result.warnings)
    n_fail = len(result.failures)
    n_skip = sum(1 for c in result.checks if c.status == "skip")

    rows_str = ""
    if result.stats.get("rows") is not None:
        rows_str = f"<span class='meta'> · {result.stats['rows']:,} rows</span>"

    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        f"<title>geoassert — {path}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        '<div class="card">',
        "<h1>geoassert validation report</h1>",
        (
            f"<p class='meta'><strong>{path}</strong>{rows_str}"
            f" &nbsp;·&nbsp; <span class='badge badge-{overall_cls}'>{overall}</span></p>"
        ),
        '<div class="summary-grid">',
        _stat_box(str(n_pass), "Passed", "num-pass"),
        _stat_box(str(n_warn), "Warnings", "num-warn"),
        _stat_box(str(n_fail), "Failed", "num-fail"),
        _stat_box(str(n_skip), "Skipped", "num-skip"),
        "</div>",
        "</div>",
    ]

    # Checks table grouped by category
    parts.append('<div class="card">')
    parts.append("<h2>Checks</h2>")
    parts.append(
        "<table><thead><tr><th>Status</th><th>Check</th><th>Message</th></tr></thead><tbody>"
    )
    for c in result.checks:
        badge = f"<span class='badge badge-{c.status}'>{_STATUS_LABEL[c.status]}</span>"
        msg = html.escape(c.message)
        name = f"<span class='check-name'>{html.escape(c.check)}</span>"
        parts.append(f"<tr><td>{badge}</td><td>{name}</td><td>{msg}</td></tr>")
    parts.append("</tbody></table>")
    parts.append("</div>")

    # Failures detail
    if result.failures:
        parts.append('<div class="card">')
        parts.append("<h2>Failures</h2>")
        for f in result.failures:
            parts.append(_detail_block(f, "fail"))
        parts.append("</div>")

    # Warnings detail
    if result.warnings:
        parts.append('<div class="card">')
        parts.append("<h2>Warnings</h2>")
        for w in result.warnings:
            parts.append(_detail_block(w, "warn"))
        parts.append("</div>")

    parts += [
        "<p class='footer'>Generated by <strong>geoassert</strong></p>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)


def _stat_box(num: str, label: str, cls: str) -> str:
    return (
        f"<div class='stat-box'>"
        f"<div class='num {cls}'>{num}</div>"
        f"<div class='lbl'>{label}</div>"
        f"</div>"
    )


def _kv(label: str, value: str) -> str:
    return f"<div class='kv'><span class='k'>{label}</span><span>{value}</span></div>"


def _detail_block(c: CheckResult, kind: str) -> str:
    e = html.escape
    lines = [f"<div class='detail-block {kind}'>"]
    lines.append(f"<p><span class='check-name'><strong>{e(c.check)}</strong></span></p>")
    lines.append(_kv("Message", e(c.message)))
    if c.expected is not None:
        lines.append(_kv("Expected", f"<code>{e(str(c.expected))}</code>"))
    if c.observed is not None:
        lines.append(_kv("Observed", f"<code>{e(str(c.observed))}</code>"))
    if c.affected_rows is not None:
        lines.append(_kv("Affected rows", f"{c.affected_rows:,}"))
    if c.why_it_matters:
        lines.append(_kv("Why it matters", e(c.why_it_matters)))
    if c.suggestion:
        lines.append(_kv("Suggestion", e(c.suggestion)))
    lines.append("</div>")
    return "\n".join(lines)
