"""Shapely-based geometry operations (requires geoassert[shapely])."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

try:
    import shapely
    import shapely.wkb

    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


def check_shapely() -> None:
    if not HAS_SHAPELY:
        raise ImportError(
            "shapely is required for geometry checks. "
            "Install it with: pip install 'geoassert[shapely]'"
        )


def wkb_column_to_geometries(array: pa.Array) -> list:
    """Decode a WKB binary column into shapely geometries."""
    check_shapely()
    return [shapely.wkb.loads(bytes(v.as_py())) if v.is_valid else None for v in array]


def count_invalid(geometries: list) -> int:
    check_shapely()
    return sum(1 for g in geometries if g is not None and not shapely.is_valid(g))


def count_empty(geometries: list) -> int:
    check_shapely()
    return sum(1 for g in geometries if g is not None and shapely.is_empty(g))


def count_null(geometries: list) -> int:
    return sum(1 for g in geometries if g is None)


def geometry_type_counts(geometries: list) -> dict[str, int]:
    check_shapely()
    counts: dict[str, int] = {}
    for g in geometries:
        if g is not None:
            t = shapely.get_type_id(g)
            name = shapely.GeometryType(t).name if hasattr(shapely, "GeometryType") else str(t)
            counts[name] = counts.get(name, 0) + 1
    return counts
