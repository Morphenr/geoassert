"""Custom exceptions with CI exit codes."""

from __future__ import annotations


class GeoAssertError(Exception):
    exit_code: int = 4


class ContractError(GeoAssertError):
    """Invalid or unreadable contract (exit 2)."""

    exit_code = 2


class DataReadError(GeoAssertError):
    """Unreadable input data (exit 3)."""

    exit_code = 3


class InternalError(GeoAssertError):
    """Unexpected internal error (exit 4)."""

    exit_code = 4
