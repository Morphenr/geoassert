"""Dataset profiling and starter-contract generation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from geoassert.engines.pyarrow import read_geoparquet_info


def profile_dataset(path: Path | str) -> dict[str, Any]:
    """Return key facts about a geospatial dataset."""
    path = Path(path)
    info = read_geoparquet_info(path)

    result: dict[str, Any] = {
        "path": str(path),
        "format": "geoparquet",
        "rows": info.num_rows,
        "columns": info.schema.names,
        "column_count": len(info.schema.names),
    }

    if info.geo_metadata:
        primary = info.geo_metadata.get("primary_column")
        result["geometry_column"] = primary
        columns_meta = info.geo_metadata.get("columns", {})
        if primary and primary in columns_meta:
            col = columns_meta[primary]
            result["geometry_types"] = col.get("geometry_types", [])
            crs = col.get("crs")
            result["crs"] = _extract_crs_id(crs) if isinstance(crs, dict) else (crs or None)
            bbox = col.get("bbox")
            if bbox:
                result["bounds"] = bbox

    return result


def generate_contract_yaml(path: Path | str) -> str:
    """Generate a conservative starter YAML contract from an existing dataset."""
    import yaml  # type: ignore[import-untyped]

    path = Path(path)
    prof = profile_dataset(path)

    contract: dict[str, Any] = {
        "geoassert_version": "0.1",
        "dataset": path.stem,
        "source": {"path": str(path), "format": prof.get("format", "geoparquet")},
    }

    geom_col = prof.get("geometry_column", "geometry")
    geometry: dict[str, Any] = {
        "column": geom_col,
        "valid": True,
        "allow_empty": False,
    }
    if prof.get("geometry_types"):
        geometry["type"] = prof["geometry_types"]
    if prof.get("crs"):
        geometry["crs"] = prof["crs"]
    contract["geometry"] = geometry

    if prof.get("bounds"):
        contract["bounds"] = {"within": {"bbox": prof["bounds"]}}

    contract["attributes"] = {}
    return yaml.dump(contract, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _extract_crs_id(projjson: dict[str, Any]) -> str:
    """Best-effort PROJJSON → authority:code string."""
    try:
        crs_id = projjson.get("id", {})
        auth = crs_id.get("authority", "")
        code = crs_id.get("code", "")
        if auth and code:
            return f"{auth}:{code}"
    except (AttributeError, TypeError):
        pass
    return "unknown"
