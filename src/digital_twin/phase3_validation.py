"""Phase 3 GIS evidence audit and manifest metadata."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import rasterio


def validate_raster_grid(
    dem_path: Path,
    raster_paths: Dict[str, Path],
) -> Dict:
    result = {"valid": True, "rasters": {}, "errors": []}
    with rasterio.open(dem_path) as reference:
        reference_profile = {
            "crs": str(reference.crs),
            "shape": list(reference.shape),
            "resolution": list(reference.res),
            "bounds": [float(value) for value in reference.bounds],
            "transform": tuple(reference.transform),
        }

    for name, path in raster_paths.items():
        try:
            with rasterio.open(path) as source:
                data = source.read(1, masked=True)
                values = data.compressed()
                profile = {
                    "path": str(path),
                    "crs": str(source.crs),
                    "shape": list(source.shape),
                    "resolution": list(source.res),
                    "bounds": [float(value) for value in source.bounds],
                    "nodata": (
                        None
                        if source.nodata is None
                        or not np.isfinite(float(source.nodata))
                        else float(source.nodata)
                    ),
                    "valid_pixels": int(values.size),
                    "invalid_pixels": int(data.size - values.size),
                    "missing_percent": round(
                        100.0 * (data.size - values.size) / data.size,
                        3,
                    ),
                    "min": (
                        float(values.min())
                        if values.size
                        else None
                    ),
                    "max": (
                        float(values.max())
                        if values.size
                        else None
                    ),
                    "aligned": (
                        str(source.crs) == reference_profile["crs"]
                        and list(source.shape) == reference_profile["shape"]
                        and list(source.res) == reference_profile["resolution"]
                        and [float(value) for value in source.bounds]
                        == reference_profile["bounds"]
                        and tuple(source.transform) == reference_profile["transform"]
                    ),
                }
                result["rasters"][name] = profile
                if not profile["aligned"]:
                    result["valid"] = False
                    result["errors"].append(f"{name} is not aligned to the DEM grid.")
        except Exception as exc:
            result["valid"] = False
            result["rasters"][name] = {"path": str(path), "error": str(exc)}
            result["errors"].append(f"{name}: {exc}")

    return result


def audit_gsi_inventory(
    inventory_csv: Path,
    output_geojson: Path,
) -> Dict:
    import pandas as pd

    frame = pd.read_csv(inventory_csv)
    required = {"inventory_id", "latitude", "longitude", "source", "coordinate_quality"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            "GSI inventory missing columns: " + ", ".join(sorted(missing))
        )

    features = []
    for _, row in frame.iterrows():
        latitude = row["latitude"]
        longitude = row["longitude"]
        if pd.isna(latitude) or pd.isna(longitude):
            continue
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(longitude), float(latitude)],
            },
            "properties": {
                "id": str(row["inventory_id"]),
                "source": str(row["source"]),
                "quality": str(row["coordinate_quality"]),
                "coordinate_type": "map-derived approximate",
                "terrain_available": bool(row.get("terrain_available", False)),
                "insar_quality_pass": bool(row.get("insar_quality_pass", False)),
            },
        })

    payload = {
        "type": "FeatureCollection",
        "name": "tirumala_gsi_phase3_evidence",
        "features": features,
    }
    output_geojson.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_geojson.with_suffix(output_geojson.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(output_geojson)
    return {
        "valid": len(features) == len(frame),
        "record_count": len(frame),
        "exported_count": len(features),
        "output": str(output_geojson),
        "coordinate_quality": "map-derived approximate",
    }
