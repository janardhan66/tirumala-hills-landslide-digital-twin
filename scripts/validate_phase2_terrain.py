"""Validate the existing Tirumala DEM and versioned Cesium terrain assets."""

import json
import struct
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PROJECT_ROOT


def validate_glb_header(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 12:
        return {"valid": False, "error": "GLB is shorter than the 12-byte header."}
    magic = data[:4]
    length = struct.unpack("<I", data[8:12])[0]
    version = struct.unpack("<I", data[4:8])[0]
    valid = magic == b"glTF" and version == 2 and length == len(data)
    return {
        "valid": valid,
        "magic": magic.decode("ascii", errors="replace"),
        "version": version,
        "declared_length": length,
        "actual_length": len(data),
    }


def validate_phase2_terrain() -> dict:
    dem_path = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "dinsar"
        / "tirumala"
        / "gsi_aoi"
        / "tirumala_dem_80m_gsi_aoi.tif"
    )
    glb_path = (
        PROJECT_ROOT
        / "viewer"
        / "cesium"
        / "models"
        / "tirumala_terrain_elevation.glb"
    )
    manifest_path = PROJECT_ROOT / "viewer" / "cesium" / "layers_manifest.json"

    errors = []
    dem = {}
    with rasterio.open(dem_path) as source:
        values = source.read(1, masked=True)
        valid = values.compressed()
        dem = {
            "path": str(dem_path),
            "crs": str(source.crs),
            "shape": list(source.shape),
            "resolution": list(source.res),
            "bounds": [float(value) for value in source.bounds],
            "nodata": source.nodata,
            "valid_pixels": int(valid.size),
            "invalid_pixels": int(values.size - valid.size),
            "min_elevation_m": float(valid.min()) if valid.size else None,
            "max_elevation_m": float(valid.max()) if valid.size else None,
            "mean_elevation_m": float(valid.mean()) if valid.size else None,
        }
        if source.crs is None or source.crs.to_epsg() != 32644:
            errors.append("DEM CRS is not EPSG:32644.")
        if source.shape != (69, 110):
            errors.append("DEM shape is not 69 x 110.")
        if tuple(source.res) != (80.0, 80.0):
            errors.append("DEM resolution is not 80 x 80 metres.")
        if not valid.size:
            errors.append("DEM contains no valid elevation pixels.")

    glb = validate_glb_header(glb_path)
    if not glb["valid"]:
        errors.append(glb["error"] if "error" in glb else "GLB header is invalid.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    elevation_layer = next(
        (layer for layer in manifest["layers"] if layer["id"] == "elevation"),
        None,
    )
    if elevation_layer is None:
        errors.append("Elevation layer is absent from the Cesium manifest.")
    elif not glb_path.exists():
        errors.append("Elevation GLB is missing.")

    return {
        "valid": not errors,
        "errors": errors,
        "dem": dem,
        "glb": {
            "path": str(glb_path),
            "size_bytes": glb_path.stat().st_size if glb_path.exists() else 0,
            **glb,
        },
        "manifest": {
            "bounds": manifest.get("bounds"),
            "terrain": manifest.get("terrain"),
            "elevation_layer": elevation_layer,
        },
    }


def main():
    print(json.dumps(validate_phase2_terrain(), indent=2))


if __name__ == "__main__":
    main()
