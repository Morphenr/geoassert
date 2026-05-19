"""Attribute-level checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyarrow.compute as pc

from geoassert.checks.base import BaseCheck
from geoassert.engines.pyarrow import read_table_for_check
from geoassert.result import CheckResult

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo


class AttributeExistsCheck(BaseCheck):
    name = "attributes.exists"

    def __init__(self, column: str) -> None:
        self.column = column

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        check_name = f"attributes.{self.column}.exists"
        if self.column not in info.schema.names:
            return CheckResult(
                check=check_name,
                status="fail",
                severity="error",
                message=f"Required column {self.column!r} not found in dataset.",
                expected=self.column,
                observed=info.schema.names,
            )
        return CheckResult(
            check=check_name,
            status="pass",
            severity="info",
            message=f"Column {self.column!r} present.",
        )


class AttributeNullCheck(BaseCheck):
    name = "attributes.nullable"

    def __init__(self, column: str, nullable: bool) -> None:
        self.column = column
        self.nullable = nullable

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        check_name = f"attributes.{self.column}.nullable"
        if self.column not in info.schema.names:
            return CheckResult(
                check=check_name,
                status="skip",
                severity="info",
                message=f"Skipped: column {self.column!r} not in schema.",
            )
        if self.nullable:
            return CheckResult(
                check=check_name,
                status="pass",
                severity="info",
                message=f"Column {self.column!r} is allowed to be nullable.",
            )

        if info.engine == "duckdb":
            from geoassert.engines.duckdb import count_nulls

            n_nulls = count_nulls(str(info.path), self.column)
        else:
            table = read_table_for_check(info, columns=[self.column])
            n_nulls = table.column(self.column).null_count

        if n_nulls > 0:
            return CheckResult(
                check=check_name,
                status="fail",
                severity="error",
                message=f"Column {self.column!r} has {n_nulls:,} null value(s) but nullable=false.",
                expected="no nulls",
                observed=f"{n_nulls:,} nulls",
                affected_rows=n_nulls,
                suggestion=f"Filter or fill null values in {self.column!r} before export.",
            )
        return CheckResult(
            check=check_name,
            status="pass",
            severity="info",
            message=f"Column {self.column!r} has no null values.",
        )


class AttributeUniqueCheck(BaseCheck):
    name = "attributes.unique"

    def __init__(self, column: str) -> None:
        self.column = column

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        check_name = f"attributes.{self.column}.unique"
        if self.column not in info.schema.names:
            return CheckResult(
                check=check_name,
                status="skip",
                severity="info",
                message=f"Skipped: column {self.column!r} not in schema.",
            )

        if info.engine == "duckdb":
            from geoassert.engines.duckdb import count_distinct, count_total

            n_total = count_total(str(info.path))
            n_distinct = count_distinct(str(info.path), self.column)
            n_dupes = n_total - n_distinct
        else:
            table = read_table_for_check(info, columns=[self.column])
            arr = table.column(self.column)
            n_total = len(arr)
            n_distinct = pc.count_distinct(arr).as_py()
            n_dupes = n_total - n_distinct

        if n_dupes > 0:
            return CheckResult(
                check=check_name,
                status="fail",
                severity="error",
                message=f"Column {self.column!r} has {n_dupes:,} duplicate value(s).",
                expected="all values unique",
                observed=f"{n_dupes:,} duplicates ({n_distinct:,} distinct / {n_total:,} total)",
                affected_rows=n_dupes,
                suggestion=f"Deduplicate {self.column!r} before export.",
            )
        return CheckResult(
            check=check_name,
            status="pass",
            severity="info",
            message=f"Column {self.column!r} has all unique values.",
        )


class AttributeRangeCheck(BaseCheck):
    name = "attributes.range"

    def __init__(self, column: str, min_val: float | None, max_val: float | None) -> None:
        self.column = column
        self.min_val = min_val
        self.max_val = max_val

    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        check_name = f"attributes.{self.column}.range"
        if self.column not in info.schema.names:
            return CheckResult(
                check=check_name,
                status="skip",
                severity="info",
                message=f"Skipped: column {self.column!r} not in schema.",
            )

        if info.engine == "duckdb":
            from geoassert.engines.duckdb import count_non_null, get_min_max

            if count_non_null(str(info.path), self.column) == 0:
                return CheckResult(
                    check=check_name,
                    status="skip",
                    severity="info",
                    message=f"Skipped: column {self.column!r} has no non-null values.",
                )
            observed_min, observed_max = get_min_max(str(info.path), self.column)
        else:
            table = read_table_for_check(info, columns=[self.column])
            arr = table.column(self.column).drop_null()
            if len(arr) == 0:
                return CheckResult(
                    check=check_name,
                    status="skip",
                    severity="info",
                    message=f"Skipped: column {self.column!r} has no non-null values.",
                )
            observed_min = pc.min(arr).as_py()
            observed_max = pc.max(arr).as_py()

        violations = []
        if self.min_val is not None and observed_min < self.min_val:
            violations.append(f"min {observed_min} < expected {self.min_val}")
        if self.max_val is not None and observed_max > self.max_val:
            violations.append(f"max {observed_max} > expected {self.max_val}")

        if violations:
            return CheckResult(
                check=check_name,
                status="fail",
                severity="error",
                message=f"Column {self.column!r} range violation: {'; '.join(violations)}",
                expected={"min": self.min_val, "max": self.max_val},
                observed={"min": observed_min, "max": observed_max},
                suggestion=f"Filter or clamp {self.column!r} values before export.",
            )
        return CheckResult(
            check=check_name,
            status="pass",
            severity="info",
            message=(
                f"Column {self.column!r} range [{observed_min}, {observed_max}] is within bounds."
            ),
        )


def run_attribute_checks(
    info: DatasetInfo,
    contract: Contract | None = None,
) -> list[CheckResult]:
    if not (contract and contract.attributes):
        return []

    results: list[CheckResult] = []
    for col_name, attr in contract.attributes.items():
        results.append(AttributeExistsCheck(col_name).run(info, contract))
        results.append(AttributeNullCheck(col_name, attr.nullable).run(info, contract))
        if attr.unique:
            results.append(AttributeUniqueCheck(col_name).run(info, contract))
        if attr.min is not None or attr.max is not None:
            results.append(AttributeRangeCheck(col_name, attr.min, attr.max).run(info, contract))
    return results
