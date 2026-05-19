"""GeoPandas engine (requires geoassert[geopandas])."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

try:
    import geopandas as gpd

    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False


def check_geopandas() -> None:
    if not HAS_GEOPANDAS:
        raise ImportError(
            "geopandas is required for this operation. "
            "Install it with: pip install 'geoassert[geopandas]'"
        )


def read_geodataframe(path: Path | str) -> gpd.GeoDataFrame:
    check_geopandas()
    return gpd.read_file(str(path))


def read_geoparquet(path: Path | str) -> gpd.GeoDataFrame:
    check_geopandas()
    return gpd.read_parquet(str(path))
