"""CLI entry point."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from geoassert.exceptions import ContractError, DataReadError, GeoAssertError

app = typer.Typer(
    name="geoassert",
    help="Data contracts for geospatial pipelines.",
    add_completion=False,
    no_args_is_help=True,
)
geoparquet_app = typer.Typer(help="GeoParquet-specific checks.", no_args_is_help=True)
dbt_app = typer.Typer(
    help="dbt integration — discover and validate dbt model outputs.",
    no_args_is_help=True,
)
app.add_typer(geoparquet_app, name="geoparquet")
app.add_typer(dbt_app, name="dbt")

console = Console()
err = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        from geoassert import __version__

        console.print(f"geoassert {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    pass


_FORMAT_HELP = "Output format: text | json | markdown | html | github | junit"


@app.command()
def profile(
    path: Path = typer.Argument(..., help="Path to the dataset."),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text | json"),
) -> None:
    """Profile a geospatial dataset."""
    from geoassert.profiling.profiler import profile_dataset

    try:
        result = profile_dataset(path)
    except DataReadError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(3) from None
    except GeoAssertError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(4) from None

    if format == "json":
        import json

        console.print_json(json.dumps(result, default=str))
    else:
        _print_profile(result, path)


@app.command("init-contract")
def init_contract(
    path: Path = typer.Argument(..., help="Path to the dataset."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Write to file (default: stdout)."),
) -> None:
    """Generate a starter contract YAML from an existing dataset."""
    from geoassert.profiling.profiler import generate_contract_yaml

    try:
        yaml_str = generate_contract_yaml(path)
    except DataReadError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(3) from None

    if out:
        out.write_text(yaml_str)
        console.print(f"Contract written to [bold]{out}[/bold]")
    else:
        console.print(yaml_str, highlight=False)


@app.command()
def validate(
    path: str = typer.Argument(
        ...,
        help="Path/URI to dataset or directory. Supports s3://, gs://, az://, postgis://, bigquery://.",
    ),
    contract: Path = typer.Option(..., "--contract", "-c", help="Path to the contract YAML."),
    format: str = typer.Option("text", "--format", "-f", help=_FORMAT_HELP),
    fail_on_warn: bool = typer.Option(False, "--fail-on-warn", help="Exit 1 on warnings."),
    sample: int | None = typer.Option(
        None,
        "--sample",
        "-n",
        help="Row sample size for row-level checks (skips sampling when omitted).",
        min=1,
    ),
    engine: str = typer.Option(
        "pyarrow",
        "--engine",
        "-e",
        help="Compute engine for attribute checks: pyarrow | duckdb",
    ),
    junit_out: Path | None = typer.Option(
        None,
        "--junit-out",
        help="Write JUnit XML to this file (in addition to the chosen --format output).",
    ),
    report_out: Path | None = typer.Option(
        None,
        "--report-out",
        help="Write the formatted report to this file (format determined by --format).",
    ),
    # Warehouse connection options
    dsn: str | None = typer.Option(None, "--dsn", help="PostgreSQL DSN for PostGIS sources."),
    geom_col: str = typer.Option(
        "geometry", "--geom-col", help="Geometry column name (warehouse sources)."
    ),
    bq_project: str | None = typer.Option(
        None, "--bq-project", help="GCP project ID (BigQuery sources)."
    ),
    sf_account: str | None = typer.Option(
        None, "--sf-account", help="Snowflake account identifier."
    ),
    sf_user: str | None = typer.Option(None, "--sf-user", help="Snowflake username."),
    sf_password: str | None = typer.Option(None, "--sf-password", help="Snowflake password."),
    sf_warehouse: str | None = typer.Option(
        None, "--sf-warehouse", help="Snowflake virtual warehouse."
    ),
) -> None:
    """Validate a dataset or directory of datasets against a contract."""
    from geoassert.contracts.loader import load_contract

    try:
        loaded = load_contract(contract)
    except ContractError as exc:
        err.print(f"[red]Contract error:[/red] {exc}")
        raise typer.Exit(2) from None

    # Warehouse URI dispatch
    if path.startswith(("postgis://", "postgresql://")):
        _validate_postgis(
            path, loaded, format, fail_on_warn, sample, geom_col, junit_out, report_out
        )
        return
    if path.startswith("bigquery://"):
        _validate_bigquery(
            path, loaded, format, fail_on_warn, sample, geom_col, bq_project, junit_out, report_out
        )
        return
    if path.startswith("snowflake://"):
        _validate_snowflake(
            path,
            loaded,
            format,
            fail_on_warn,
            sample,
            geom_col,
            sf_account,
            sf_user,
            sf_password,
            sf_warehouse,
            junit_out,
            report_out,
        )
        return

    local_path = Path(path)
    if local_path.is_dir():
        _validate_directory(
            local_path, loaded, format, fail_on_warn, sample, engine, junit_out, report_out
        )
        return

    from geoassert.runner import run_validation

    try:
        result = run_validation(path, loaded, sample=sample, engine=engine)
    except DataReadError as exc:
        err.print(f"[red]Data error:[/red] {exc}")
        raise typer.Exit(3) from None
    except GeoAssertError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(4) from None

    _emit_result(result, format, console)

    if junit_out is not None:
        from geoassert.reports.junit import render_junit

        junit_out.write_text(render_junit(result), encoding="utf-8")

    if report_out is not None:
        _write_report_file(result, format, report_out)

    if not result.passed:
        raise typer.Exit(1)
    if fail_on_warn and result.warnings:
        raise typer.Exit(1)


def _validate_directory(
    path: Path,
    loaded: object,
    format: str,
    fail_on_warn: bool,
    sample: int | None,
    engine: str,
    junit_out: Path | None,
    report_out: Path | None = None,
) -> None:
    from geoassert.runner import validate_directory

    try:
        results = validate_directory(path, loaded, sample=sample, engine=engine)  # type: ignore[arg-type]
    except DataReadError as exc:
        err.print(f"[red]Data error:[/red] {exc}")
        raise typer.Exit(3) from None
    except GeoAssertError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(4) from None

    if not results:
        err.print(f"[yellow]No Parquet files found under {path}[/yellow]")
        raise typer.Exit(0)

    any_failed = False
    any_warned = False
    for result in results:
        _emit_result(result, format, console)
        if not result.passed:
            any_failed = True
        if result.warnings:
            any_warned = True

    if junit_out is not None:
        from geoassert.reports.junit import render_junit

        # Write only the last file result; directory result is first
        junit_out.write_text(render_junit(results[-1]), encoding="utf-8")

    if report_out is not None:
        _write_report_file(results[-1], format, report_out)

    if any_failed:
        raise typer.Exit(1)
    if fail_on_warn and any_warned:
        raise typer.Exit(1)


def _validate_postgis(
    uri: str,
    loaded: object,
    format: str,
    fail_on_warn: bool,
    sample: int | None,
    geom_col: str,
    junit_out: Path | None,
    report_out: Path | None = None,
) -> None:
    """Validate a PostGIS table via postgis:// or postgresql:// URI."""
    from urllib.parse import urlparse

    from geoassert.engines.postgis import read_postgis_info
    from geoassert.runner import run_validation_from_info

    parsed = urlparse(uri)
    # Rebuild DSN as postgresql://
    dsn = uri.replace("postgis://", "postgresql://", 1)
    # Table and schema from path: /schema/table or /table
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) >= 2:
        schema, table = path_parts[0], path_parts[1]
    else:
        schema, table = "public", path_parts[0]

    try:
        info = read_postgis_info(dsn, table, geom_col=geom_col, schema=schema, sample=sample)
        result = run_validation_from_info(info, loaded)  # type: ignore[arg-type]
    except DataReadError as exc:
        err.print(f"[red]Data error:[/red] {exc}")
        raise typer.Exit(3) from None
    except GeoAssertError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(4) from None

    _emit_result(result, format, console)
    if junit_out is not None:
        from geoassert.reports.junit import render_junit

        junit_out.write_text(render_junit(result), encoding="utf-8")
    if report_out is not None:
        _write_report_file(result, format, report_out)
    if not result.passed:
        raise typer.Exit(1)
    if fail_on_warn and result.warnings:
        raise typer.Exit(1)


def _validate_bigquery(
    uri: str,
    loaded: object,
    format: str,
    fail_on_warn: bool,
    sample: int | None,
    geom_col: str,
    bq_project: str | None,
    junit_out: Path | None,
    report_out: Path | None = None,
) -> None:
    """Validate a BigQuery table via bigquery://project/dataset/table URI."""
    from urllib.parse import urlparse

    from geoassert.engines.bigquery import read_bigquery_info
    from geoassert.runner import run_validation_from_info

    parsed = urlparse(uri)
    project = bq_project or parsed.netloc
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) < 2:
        err.print("[red]Error:[/red] BigQuery URI must be bigquery://project/dataset/table")
        raise typer.Exit(2)
    dataset, table = path_parts[0], path_parts[1]

    try:
        info = read_bigquery_info(project, dataset, table, geom_col=geom_col, sample=sample)
        result = run_validation_from_info(info, loaded)  # type: ignore[arg-type]
    except DataReadError as exc:
        err.print(f"[red]Data error:[/red] {exc}")
        raise typer.Exit(3) from None
    except GeoAssertError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(4) from None

    _emit_result(result, format, console)
    if junit_out is not None:
        from geoassert.reports.junit import render_junit

        junit_out.write_text(render_junit(result), encoding="utf-8")
    if report_out is not None:
        _write_report_file(result, format, report_out)
    if not result.passed:
        raise typer.Exit(1)
    if fail_on_warn and result.warnings:
        raise typer.Exit(1)


def _validate_snowflake(
    uri: str,
    loaded: object,
    format: str,
    fail_on_warn: bool,
    sample: int | None,
    geom_col: str,
    sf_account: str | None,
    sf_user: str | None,
    sf_password: str | None,
    sf_warehouse: str | None,
    junit_out: Path | None,
    report_out: Path | None = None,
) -> None:
    """Validate a Snowflake table via snowflake://account/database/schema/table URI."""
    from urllib.parse import urlparse

    from geoassert.engines.snowflake import read_snowflake_info
    from geoassert.runner import run_validation_from_info

    parsed = urlparse(uri)
    account = sf_account or parsed.netloc
    path_parts = parsed.path.strip("/").split("/")
    if len(path_parts) < 3:
        err.print(
            "[red]Error:[/red] Snowflake URI must be snowflake://account/database/schema/table"
        )
        raise typer.Exit(2)
    database, schema, table = path_parts[0], path_parts[1], path_parts[2]

    if not sf_user or not sf_password:
        err.print("[red]Error:[/red] --sf-user and --sf-password are required for Snowflake.")
        raise typer.Exit(2)

    try:
        info = read_snowflake_info(
            account,
            sf_user,
            sf_password,
            database,
            schema,
            table,
            geom_col=geom_col,
            warehouse=sf_warehouse,
            sample=sample,
        )
        result = run_validation_from_info(info, loaded)  # type: ignore[arg-type]
    except DataReadError as exc:
        err.print(f"[red]Data error:[/red] {exc}")
        raise typer.Exit(3) from None
    except GeoAssertError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(4) from None

    _emit_result(result, format, console)
    if junit_out is not None:
        from geoassert.reports.junit import render_junit

        junit_out.write_text(render_junit(result), encoding="utf-8")
    if report_out is not None:
        _write_report_file(result, format, report_out)
    if not result.passed:
        raise typer.Exit(1)
    if fail_on_warn and result.warnings:
        raise typer.Exit(1)


# ── dbt subcommands ────────────────────────────────────────────────────────────


@dbt_app.command("list")
def dbt_list(
    project_dir: Path | None = typer.Option(
        None, "--project-dir", "-p", help="dbt project root (default: current directory)."
    ),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text | json"),
) -> None:
    """List all models found in the dbt manifest."""
    from geoassert.integrations.dbt import find_manifest, list_models, load_manifest

    try:
        manifest_path = find_manifest(project_dir)
        manifest = load_manifest(manifest_path)
    except FileNotFoundError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(3) from None
    except ValueError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from None

    models = list_models(manifest)
    if not models:
        console.print("[yellow]No models found in manifest.[/yellow]")
        return

    if format == "json":
        import json

        console.print_json(
            json.dumps(
                [
                    {
                        "name": m.name,
                        "materialized": m.materialized,
                        "full_name": m.full_name,
                        "tags": m.tags,
                    }
                    for m in models
                ]
            )
        )
    else:
        console.print(f"[bold]Found {len(models)} model(s) in {manifest_path}[/bold]\n")
        for m in models:
            console.print(f"  [cyan]{m.name}[/cyan]  [dim]{m.materialized}[/dim]  {m.full_name}")


@dbt_app.command("validate")
def dbt_validate(
    model_name: str = typer.Argument(..., help="dbt model name to validate."),
    contract: Path = typer.Option(..., "--contract", "-c", help="Path to the contract YAML."),
    project_dir: Path | None = typer.Option(
        None, "--project-dir", "-p", help="dbt project root (default: current directory)."
    ),
    format: str = typer.Option("text", "--format", "-f", help=_FORMAT_HELP),
    fail_on_warn: bool = typer.Option(False, "--fail-on-warn", help="Exit 1 on warnings."),
    sample: int | None = typer.Option(None, "--sample", "-n", help="Row sample limit.", min=1),
    engine: str = typer.Option(
        "pyarrow", "--engine", "-e", help="Compute engine: pyarrow | duckdb"
    ),
    dsn: str | None = typer.Option(
        None, "--dsn", help="PostgreSQL DSN for PostGIS-materialized models."
    ),
    file_path: Path | None = typer.Option(
        None, "--path", help="Direct file path override (Parquet file for this model)."
    ),
    junit_out: Path | None = typer.Option(
        None, "--junit-out", help="Write JUnit XML to this file."
    ),
) -> None:
    """Validate a dbt model output against a contract."""
    from geoassert.integrations.dbt import (
        find_manifest,
        get_model,
        load_manifest,
        validate_dbt_model,
    )

    try:
        from geoassert.contracts.loader import load_contract as _load_contract

        loaded_contract = _load_contract(contract)  # noqa: F841
    except ContractError as exc:
        err.print(f"[red]Contract error:[/red] {exc}")
        raise typer.Exit(2) from None

    try:
        manifest_path = find_manifest(project_dir)
        manifest = load_manifest(manifest_path)
        model = get_model(manifest, model_name)
    except FileNotFoundError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(3) from None
    except (KeyError, ValueError) as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from None

    try:
        result = validate_dbt_model(
            model,
            contract,
            dsn=dsn,
            file_path=file_path,
            sample=sample,
            engine=engine,
        )
    except DataReadError as exc:
        err.print(f"[red]Data error:[/red] {exc}")
        raise typer.Exit(3) from None
    except (GeoAssertError, ValueError) as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(4) from None

    _emit_result(result, format, console)

    if junit_out is not None:
        from geoassert.reports.junit import render_junit

        junit_out.write_text(render_junit(result), encoding="utf-8")

    if not result.passed:
        raise typer.Exit(1)
    if fail_on_warn and result.warnings:
        raise typer.Exit(1)


def _emit_result(result: object, format: str, out: Console) -> None:
    from geoassert.result import ValidationResult

    assert isinstance(result, ValidationResult)
    if format == "json":
        out.print_json(result.to_json())
    elif format in ("markdown", "md"):
        out.print(result.to_markdown(), highlight=False)
    elif format == "html":
        out.print(result.to_html(), highlight=False)
    elif format == "github":
        from geoassert.reports.github import render_github_annotations

        render_github_annotations(result, out)
    elif format == "junit":
        from geoassert.reports.junit import render_junit

        out.print(render_junit(result), highlight=False)
    else:
        _print_validation_result(result)


def _write_report_file(result: object, format: str, path: Path) -> None:
    """Write the formatted report to *path* on disk."""
    from geoassert.reports.junit import render_junit
    from geoassert.result import ValidationResult

    assert isinstance(result, ValidationResult)
    if format == "json":
        path.write_text(result.to_json(), encoding="utf-8")
    elif format in ("markdown", "md"):
        path.write_text(result.to_markdown(), encoding="utf-8")
    elif format == "html":
        path.write_text(result.to_html(), encoding="utf-8")
    elif format == "junit":
        path.write_text(render_junit(result), encoding="utf-8")
    else:
        path.write_text(result.to_markdown(), encoding="utf-8")


@geoparquet_app.command("check")
def geoparquet_check(
    path: Path = typer.Argument(..., help="Path to the GeoParquet file."),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text | json"),
) -> None:
    """Check GeoParquet metadata validity."""
    from geoassert.checks.geoparquet import run_metadata_checks
    from geoassert.engines.pyarrow import read_geoparquet_info

    try:
        info = read_geoparquet_info(path)
    except DataReadError as exc:
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(3) from None

    checks = run_metadata_checks(info)
    failed = [c for c in checks if c.status == "fail"]

    if format == "json":
        import json

        console.print_json(json.dumps([c.to_dict() for c in checks], default=str))
    else:
        _print_check_list(checks, path)

    if failed:
        raise typer.Exit(1)


# ── rendering helpers ──────────────────────────────────────────────────────────

_STATUS_STYLE = {
    "pass": "[green]PASS[/green]",
    "warn": "[yellow]WARN[/yellow]",
    "fail": "[red]FAIL[/red]",
    "skip": "[dim]SKIP[/dim]",
}


def _print_profile(prof: dict, path: Path) -> None:
    console.rule(f"[bold]{path.name}")
    console.print(f"  Rows:          {prof.get('rows', '?'):,}")
    console.print(f"  Columns:       {prof.get('column_count', '?')}")
    if "geometry_column" in prof:
        console.print(f"  Geometry col:  {prof['geometry_column']}")
    if "geometry_types" in prof:
        console.print(f"  Geometry types: {prof['geometry_types']}")
    if "crs" in prof:
        console.print(f"  CRS:           {prof['crs']}")
    if "bounds" in prof:
        console.print(f"  Bounds:        {prof['bounds']}")


def _print_check_list(checks: list, path: Path) -> None:
    console.rule(f"[bold]{path.name}")
    for c in checks:
        label = _STATUS_STYLE.get(c.status, c.status)
        console.print(f"  {label}  {c.check}")
        if c.status in ("warn", "fail") and c.message:
            console.print(f"       {c.message}", style="dim")
        if c.suggestion:
            console.print(f"       Suggestion: {c.suggestion}", style="dim italic")


def _print_validation_result(result: object) -> None:
    from geoassert.result import ValidationResult

    assert isinstance(result, ValidationResult)

    _print_check_list(result.checks, Path(str(result.stats.get("path", "dataset"))))

    if result.stats.get("sample"):
        console.print(
            f"\n[dim]Row-level checks run on a sample of {result.stats['sample']:,} rows.[/dim]"
        )

    if result.failures:
        console.print()
        console.print("[bold red]Failures:[/bold red]")
        for f in result.failures:
            console.print(f"  [red]{f.check}[/red]")
            if f.expected is not None:
                console.print(f"    Expected:  {f.expected}")
            if f.observed is not None:
                console.print(f"    Observed:  {f.observed}")
            if f.affected_rows is not None:
                console.print(f"    Rows:      {f.affected_rows:,}")
            if f.suggestion:
                console.print(f"    Suggestion: {f.suggestion}", style="dim")
    elif not result.warnings:
        console.print()
        console.print("[green]All checks passed.[/green]")
