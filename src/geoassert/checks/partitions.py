"""Partition-level checks for Hive-partitioned datasets."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from geoassert.checks.base import BaseCheck
from geoassert.result import CheckResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo


def _parquet_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.parquet"))


def _partition_columns(root: Path) -> list[str]:
    """Return Hive partition column names found in the directory tree."""
    cols: list[str] = []
    for p in root.rglob("*"):
        if p.is_dir() and "=" in p.name:
            col = p.name.split("=", 1)[0]
            if col not in cols:
                cols.append(col)
    return cols


class PartitionDetectedCheck(BaseCheck):
    name = "partitions.detected"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        path = Path(str(info.path))
        if not path.is_dir():
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: path is not a directory.",
            )
        cols = _partition_columns(path)
        files = _parquet_files(path)
        if not files:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message=f"No Parquet files found under {path}.",
            )
        if cols:
            return CheckResult(
                check=self.name,
                status="pass",
                severity="info",
                message=(
                    f"Hive partitioning detected: {cols}. "
                    f"{len(files)} Parquet file(s) across {len(cols)} partition column(s)."
                ),
                observed={"partition_columns": cols, "file_count": len(files)},
            )
        return CheckResult(
            check=self.name,
            status="warn",
            severity="warn",
            message=(
                f"Directory has {len(files)} Parquet file(s) but no Hive partition structure "
                "(col=val directories) was detected."
            ),
            suggestion=(
                "If this dataset is meant to be Hive-partitioned, "
                "check that directories follow the col=val naming convention."
            ),
        )


class PartitionSchemaConsistencyCheck(BaseCheck):
    name = "partitions.schema_consistency"

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        path = Path(str(info.path))
        if not path.is_dir():
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: path is not a directory.",
            )
        files = _parquet_files(path)
        if len(files) < 2:
            return CheckResult(
                check=self.name,
                status="skip",
                severity="info",
                message="Skipped: fewer than 2 Parquet files found; nothing to compare.",
            )

        import pyarrow.parquet as pq

        from geoassert.exceptions import DataReadError

        schemas: list[tuple[Path, object]] = []
        for f in files:
            try:
                schemas.append((f, pq.read_schema(f)))
            except Exception as exc:
                raise DataReadError(f"Cannot read schema of {f}: {exc}") from exc

        reference_path, reference_schema = schemas[0]
        mismatched: list[str] = []
        for f, schema in schemas[1:]:
            if schema != reference_schema:
                mismatched.append(str(f))

        if mismatched:
            return CheckResult(
                check=self.name,
                status="fail",
                severity="error",
                message=(
                    f"{len(mismatched)} partition file(s) have schemas that differ "
                    f"from the reference ({reference_path.name})."
                ),
                expected=str(reference_schema),
                observed=mismatched,
                suggestion=(
                    "Ensure all partition files are written with the same schema. "
                    "Schema drift often happens when partition files are appended "
                    "at different points in the pipeline."
                ),
            )
        return CheckResult(
            check=self.name,
            status="pass",
            severity="info",
            message=f"All {len(files)} partition files share the same schema.",
        )


def run_partition_checks(
    info: DatasetInfo,
    contract: Contract | None = None,
) -> list[CheckResult]:
    return [
        c.run(info, contract)
        for c in [PartitionDetectedCheck(), PartitionSchemaConsistencyCheck()]
    ]
