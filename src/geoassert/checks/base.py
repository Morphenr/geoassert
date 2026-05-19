"""Abstract base check."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geoassert.contracts.schema import Contract
    from geoassert.engines.pyarrow import DatasetInfo
    from geoassert.result import CheckResult


class BaseCheck(ABC):
    name: str

    @abstractmethod
    def run(self, info: DatasetInfo, contract: Contract | None = None) -> CheckResult:
        ...
