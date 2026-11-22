"""Tirumala Hills 3D Digital Twin: GLB Terrain and Texture Generator.

Transforms local GeoTIFF DEMs and satellite/evidence rasters into georeferenced
glTF/GLB 3D surface meshes for CesiumJS and WebGL visualization.
"""
from __future__ import annotations

import io
import json
import os
import struct
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pyproj
import rasterio
from PIL import Image


class TerrainBuilderError(Exception):
    """Raised when DEM or raster cannot be converted to 3D terrain geometry."""


def generate_terrain_texture(
    raster_path: str | Path,
    output_png_path: str | Path,
    colormap_name: str = "gist_earth",
    dem_for_hillshade: Optional[str | Path] = None,
    value_range: Optional[Tuple[float, float]] = None,
    symmetric_range: bool = False,
    resolution: Tuple[int, int] = (1024, 1024),
) -> str:
    """Generate a high-resolution colormapped and hillshaded texture for 3D terrain draping."""
    raster_path = Path(raster_path)
    output_png_path = Path(output_png_path)
    output_png_path.parent.mkdir(parents=True, exist_ok=True)

    if not raster_path.exists():
        raise TerrainBuilderError(f"Raster file not found: {raster_path}")

    with rasterio.open(raster_path) as ds:
        data = ds.read(1).astype(np.float32)
        nodata = ds.nodata

    valid = np.isfinite(data)
    if nodata is not None:
        valid &= data != nodata

    if not np.any(valid):
        raise TerrainBuilderError(f"No valid pixels found in {raster_path.name}")

    min_val = float(np.min(data[valid]))
    max_val = float(np.max(data[valid]))

    if value_range is not None:
        cmin, cmax = value_range
    elif symmetric_range:
        max_abs = max(abs(min_val), abs(max_val), 1e-4)
        cmin, cmax = -max_abs, max_abs
    else:
        cmin, cmax = min_val, max_val

    # Normalize data to [0.0, 1.0]
    span = max(cmax - cmin, 1e-6)
    normalized = np.clip((data - cmin) / span, 0.0, 1.0)
    normalized[~valid] = 0.0

    # Get colormap
    try:
        cmap = plt.colormaps[colormap_name]
    except KeyError:
        cmap = plt.colormaps["viridis"]

    rgba = cmap(normalized)

    # Compute analytical hillshade if DEM provided
    shade_factor = np.ones_like(normalized, dtype=np.float32)
    dem_path = Path(dem_for_hillshade) if dem_for_hillshade else raster_path
    if dem_path.exists():
        try:
            with rasterio.open(dem_path) as dem_ds:
                dem = dem_ds.read(1).astype(np.float32)
                res_x = float(dem_ds.transform.a)
                res_y = float(-dem_ds.transform.e)

            dem_valid = np.isfinite(dem)
            if dem_ds.nodata is not None:
                dem_valid &= dem != dem_ds.nodata
            dem_fill = np.where(dem_valid, dem, np.nanmean(dem[dem_valid]))

            azimuth_rad = np.radians(360.0 - 315.0 + 90.0)
            altitude_rad = np.radians(45.0)

            dy, dx = np.gradient(dem_fill, res_y, res_x)
            slope = np.arctan(np.sqrt(dx * dx + dy * dy))
            aspect = np.arctan2(-dy, -dx)

            shaded = (
                np.sin(altitude_rad) * np.cos(slope)
                + np.cos(altitude_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)
            )
            shaded = np.clip(shaded, 0.0, 1.0)
            shade_factor = 0.50 + 0.50 * shaded
        except Exception:
            shade_factor = np.ones_like(normalized, dtype=np.float32)

    # Apply shading to RGB channels
    for i in range(3):
        rgba[:, :, i] = np.clip(rgba[:, :, i] * shade_factor, 0.0, 1.0)

    # Set invalid pixels to transparent
    rgba[:, :, 3] = np.where(valid, 1.0, 0.0)

    img = Image.fromarray((rgba * 255).astype(np.uint8))
    img_hd = img.resize(resolution, Image.Resampling.BICUBIC)
    img_hd.save(output_png_path, format="PNG")
    return str(output_png_path)


def build_terrain_glb(
    dem_path: str | Path,
    output_glb_path: str | Path,
    texture_path: Optional[str | Path] = None,
    vertical_exaggeration: float = 1.0,
) -> Dict[str, Any]:
    """Convert a georeferenced DEM GeoTIFF into a 3D binary glTF (GLB) mesh.

    Uses an East-North-Up (ENU) metric frame:
      X = Easting offset from center (meters)
      Y = Northing offset from center (meters)
      Z = Elevation above base datum (meters)
    """
    dem_path = Path(dem_path)
    output_glb_path = Path(output_glb_path)
    output_glb_path.parent.mkdir(parents=True, exist_ok=True)

    if not dem_path.exists():
        raise TerrainBuilderError(f"DEM raster file not found: {dem_path}")

    try:
        vertical_exaggeration = float(vertical_exaggeration)
    except (TypeError, ValueError) as exc:
        raise TerrainBuilderError("Vertical exaggeration must be a finite positive number.") from exc
    if not np.isfinite(vertical_exaggeration) or vertical_exaggeration <= 0:
        raise TerrainBuilderError("Vertical exaggeration must be a finite positive number.")

    with rasterio.open(dem_path) as ds:
        dem = ds.read(1).astype(np.float32)
        transform = ds.transform
        crs = ds.crs
        nodata = ds.nodata

    if crs is None:
        raise TerrainBuilderError(f"{dem_path.name} is missing a Coordinate Reference System.")
    projected_crs = pyproj.CRS.from_user_input(crs)
    if not projected_crs.is_projected:
        raise TerrainBuilderError(f"{dem_path.name} must use a projected Coordinate Reference System.")
    if not all(
        np.isclose(axis.unit_conversion_factor, 1.0)
        for axis in projected_crs.axis_info[:2]
    ):
        raise TerrainBuilderError(f"{dem_path.name} must use projected coordinates in meters.")

    res_x = float(transform.a)
    res_y = float(-transform.e)
    if (
        not np.isfinite([res_x, res_y, transform.b, transform.d]).all()
        or res_x <= 0
        or res_y <= 0
        or not np.isclose(transform.b, 0.0, atol=1e-9)
        or not np.isclose(transform.d, 0.0, atol=1e-9)
    ):
        raise TerrainBuilderError(f"{dem_path.name} must be a north-up raster with positive pixel sizes.")

    height, width = dem.shape
    if height < 2 or width < 2:
        raise TerrainBuilderError(f"{dem_path.name} must be at least 2 × 2 pixels.")

    valid_mask = np.isfinite(dem)
    if nodata is not None:
        valid_mask &= dem != nodata

    if not np.any(valid_mask):
        raise TerrainBuilderError(f"{dem_path.name} contains no valid elevation cells.")

    min_elev = float(np.min(dem[valid_mask]))
    max_elev = float(np.max(dem[valid_mask]))
    dem_filled = np.where(valid_mask, dem, min_elev)

    center_col = width / 2.0
    center_row = height / 2.0
    center_easting = float(transform.c + center_col * res_x)
    center_northing = float(transform.f - center_row * res_y)
    base_elevation = float(min_elev)

    # Convert center coordinates to WGS 84 (EPSG:4326)
    transformer = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    center_lon, center_lat = transformer.transform(center_easting, center_northing)

    cols = np.arange(width, dtype=np.float32)
    rows = np.arange(height, dtype=np.float32)
    col_grid, row_grid = np.meshgrid(cols, rows)

    # Local ENU coordinates in meters
    x_coords = (col_grid - center_col) * res_x
    y_coords = (center_row - row_grid) * res_y
    z_coords = (dem_filled - base_elevation) * vertical_exaggeration

    num_vertices = height * width
    positions = np.stack([x_coords, y_coords, z_coords], axis=-1).reshape(-1, 3).astype(np.float32)

    # Texture UV mapping (U: 0->1 West->East; V: 0->1 North->South)
    u = col_grid / (width - 1.0)
    v = row_grid / (height - 1.0)
    uvs = np.stack([u, v], axis=-1).reshape(-1, 2).astype(np.float32)

    # Triangulate quad grid into counter-clockwise triangle indices
    r = np.arange(height - 1)
    c = np.arange(width - 1)
    r_grid, c_grid = np.meshgrid(r, c, indexing="ij")

    v0 = (r_grid * width + c_grid).ravel()
    v1 = ((r_grid + 1) * width + c_grid).ravel()
    v2 = (r_grid * width + (c_grid + 1)).ravel()
    v3 = ((r_grid + 1) * width + (c_grid + 1)).ravel()

    tri1 = np.stack([v0, v1, v2], axis=1)
    tri2 = np.stack([v2, v1, v3], axis=1)
    triangles = np.concatenate([tri1, tri2], axis=0)
    valid_vertices = valid_mask.ravel()
    triangles = triangles[np.all(valid_vertices[triangles], axis=1)]
    if not len(triangles):
        raise TerrainBuilderError(f"{dem_path.name} has no valid adjacent elevation cells to form terrain.")
    indices = triangles.ravel().astype(np.uint32)

    # Accumulate valid triangle face normals so NoData boundaries do not distort shading.
    face_normals = np.cross(
        positions[triangles[:, 1]] - positions[triangles[:, 0]],
        positions[triangles[:, 2]] - positions[triangles[:, 0]],
    )
    normal_sums = np.zeros_like(positions)
    for corner in range(3):
        np.add.at(normal_sums, triangles[:, corner], face_normals)
    normal_lengths = np.linalg.norm(normal_sums, axis=1)
    normals = np.zeros_like(normal_sums)
    normals[:, 2] = 1.0
    has_normal = normal_lengths > 0
    normals[has_normal] = normal_sums[has_normal] / normal_lengths[has_normal, np.newaxis]

    # Read or synthesize texture image
    if texture_path and Path(texture_path).exists():
        with open(texture_path, "rb") as f:
            image_bytes = f.read()
    else:
        # Default warm sandstone terrain color
        fallback_img = Image.new("RGBA", (256, 256), color=(200, 180, 150, 255))
        buf = io.BytesIO()
        fallback_img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

    def pad4(data: bytes) -> bytes:
        rem = len(data) % 4
        return data + b"\x00" * (4 - rem) if rem else data

    pos_bytes = positions.tobytes()
    norm_bytes = normals.tobytes()
    uv_bytes = uvs.tobytes()
    idx_bytes = indices.tobytes()
    img_padded = pad4(image_bytes)

    buffer_parts = [pos_bytes, norm_bytes, uv_bytes, idx_bytes, img_padded]
    buffer_views = []
    current_offset = 0
    for part in buffer_parts:
        buffer_views.append({
            "buffer": 0,
            "byteOffset": current_offset,
            "byteLength": len(part),
        })
        current_offset += len(pad4(part))

    combined_buffer = b"".join(pad4(p) for p in buffer_parts)

    pos_min = [float(positions[:, 0].min()), float(positions[:, 1].min()), float(positions[:, 2].min())]
    pos_max = [float(positions[:, 0].max()), float(positions[:, 1].max()), float(positions[:, 2].max())]

    gltf_json = {
        "asset": {"version": "2.0", "generator": "Tirumala 3D Digital Twin Engine (CesiumJS compatible)"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{
            "mesh": 0,
            "name": "Tirumala_Terrain_Mesh",
            "translation": [0.0, 0.0, 0.0],
        }],
        "meshes": [{
            "name": "Tirumala_Terrain",
            "primitives": [{
                "attributes": {
                    "POSITION": 0,
                    "NORMAL": 1,
                    "TEXCOORD_0": 2,
                },
                "indices": 3,
                "material": 0,
            }],
        }],
        "materials": [{
            "name": "Terrain_Drape_Material",
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0},
                "metallicFactor": 0.02,
                "roughnessFactor": 0.88,
            },
            "doubleSided": True,
        }],
        "textures": [{"source": 0}],
        "images": [{"bufferView": 4, "mimeType": "image/png"}],
        "accessors": [
            {
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": num_vertices,
                "type": "VEC3",
                "min": pos_min,
                "max": pos_max,
            },
            {
                "bufferView": 1,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": num_vertices,
                "type": "VEC3",
            },
            {
                "bufferView": 2,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": num_vertices,
                "type": "VEC2",
            },
            {
                "bufferView": 3,
                "byteOffset": 0,
                "componentType": 5125,  # UNSIGNED_INT
                "count": len(indices),
                "type": "SCALAR",
                "min": [int(indices.min())],
                "max": [int(indices.max())],
            },
        ],
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(combined_buffer)}],
    }

    json_bytes = json.dumps(gltf_json).encode("utf-8")
    json_rem = len(json_bytes) % 4
    if json_rem:
        json_bytes += b" " * (4 - json_rem)

    total_len = 12 + 8 + len(json_bytes) + 8 + len(combined_buffer)
    header = struct.pack("<4sII", b"glTF", 2, total_len)
    json_chunk = struct.pack("<I4s", len(json_bytes), b"JSON") + json_bytes
    bin_chunk = struct.pack("<I4s", len(combined_buffer), b"BIN\x00") + combined_buffer

    glb_data = header + json_chunk + bin_chunk

    with open(output_glb_path, "wb") as f:
        f.write(glb_data)

    metadata = {
        "dem_file": dem_path.name,
        "crs": str(crs),
        "center_easting": center_easting,
        "center_northing": center_northing,
        "center_longitude": float(center_lon),
        "center_latitude": float(center_lat),
        "base_elevation_m": base_elevation,
        "min_elevation_m": min_elev,
        "max_elevation_m": max_elev,
        "elevation_span_m": max_elev - min_elev,
        "vertical_exaggeration": float(vertical_exaggeration),
        "width_pixels": width,
        "height_pixels": height,
        "cell_size_m": [res_x, res_y],
        "total_vertices": num_vertices,
        "total_triangles": len(indices) // 3,
        "file_size_bytes": len(glb_data),
        "output_glb": str(output_glb_path),
    }

    meta_json_path = output_glb_path.with_suffix(".json")
    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def export_cesium_package(base_dir: str | Path, output_dir: str | Path) -> Dict[str, Any]:
    """Build the complete set of 3D GLB models and colormap overlays for CesiumJS."""
    base_dir = Path(base_dir)
    output_dir = Path(output_dir)
    raster_dir = base_dir / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi"
    textures_dir = output_dir / "textures"
    models_dir = output_dir / "models"
    textures_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    dem_path = raster_dir / "tirumala_dem_80m_gsi_aoi.tif"
    slope_path = raster_dir / "tirumala_slope_80m_gsi_aoi.tif"
    corr_path = raster_dir / "tirumala_corr_80m_gsi_aoi.tif"
    los_path = raster_dir / "tirumala_los_disp_80m_gsi_aoi.tif"

    results = {}

    # 1. Shaded Relief Topography
    relief_texture = textures_dir / "tirumala_shaded_relief.png"
    generate_terrain_texture(dem_path, relief_texture, colormap_name="gist_earth")
    results["shaded_relief"] = build_terrain_glb(
        dem_path, models_dir / "tirumala_terrain_relief.glb", relief_texture, vertical_exaggeration=1.0
    )

    # 2. Slope Overlay
    if slope_path.exists():
        slope_texture = textures_dir / "tirumala_slope.png"
        generate_terrain_texture(
            slope_path, slope_texture, colormap_name="turbo",
            dem_for_hillshade=dem_path, value_range=(0.0, 50.0)
        )
        results["slope"] = build_terrain_glb(
            dem_path, models_dir / "tirumala_terrain_slope.glb", slope_texture, vertical_exaggeration=1.0
        )

    # 3. Sentinel-1 LOS Displacement
    if los_path.exists():
        los_texture = textures_dir / "tirumala_los.png"
        generate_terrain_texture(
            los_path, los_texture, colormap_name="RdBu",
            dem_for_hillshade=dem_path, symmetric_range=True
        )
        results["los_displacement"] = build_terrain_glb(
            dem_path, models_dir / "tirumala_terrain_los.glb", los_texture, vertical_exaggeration=1.0
        )

    # 4. InSAR Coherence
    if corr_path.exists():
        corr_texture = textures_dir / "tirumala_corr.png"
        generate_terrain_texture(
            corr_path, corr_texture, colormap_name="viridis",
            dem_for_hillshade=dem_path, value_range=(0.0, 1.0)
        )
        results["coherence"] = build_terrain_glb(
            dem_path, models_dir / "tirumala_terrain_corr.glb", corr_texture, vertical_exaggeration=1.0
        )

    # Also make the primary default model link
    default_glb = models_dir / "tirumala_terrain.glb"
    import shutil
    shutil.copyfile(models_dir / "tirumala_terrain_relief.glb", default_glb)
    results["default"] = results["shaded_relief"]

    return results
