"""Tirumala Hills 3D Digital Twin: Multi-Layer GIS Evidence Exporter.

Automates the export of aligned geospatial raster and vector layers as
georeferenced RGBA overlays and GeoJSON entities with exact geographic bounds
for dynamic multi-layer draping in CesiumJS and WebGL.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pyproj
import rasterio
from PIL import Image


class LayerExportError(Exception):
    """Raised when an evidence layer cannot be exported or aligned."""


def raster_to_rgba_overlay(
    raster_path: str | Path,
    output_png_path: str | Path,
    colormap_name: str = "viridis",
    value_range: Optional[Tuple[float, float]] = None,
    symmetric_range: bool = False,
    dem_for_hillshade: Optional[str | Path] = None,
    alpha_mask: Optional[np.ndarray] = None,
    resolution: Tuple[int, int] = (1024, 1024),
    reference_raster_path: Optional[str | Path] = None,
    scale_factor: float = 1.0,
) -> Tuple[str, Dict[str, float]]:
    """Export a single-band raster to a georeferenced RGBA PNG overlay with exact WGS84 bounds."""
    raster_path = Path(raster_path)
    output_png_path = Path(output_png_path)
    output_png_path.parent.mkdir(parents=True, exist_ok=True)

    if not raster_path.exists():
        raise LayerExportError(f"Raster not found: {raster_path}")

    with rasterio.open(raster_path) as src:
        data = src.read(1).astype(np.float32)
        transform = src.transform
        crs = src.crs
        nodata = src.nodata
        height, width = src.shape

    if reference_raster_path is not None:
        reference_raster_path = Path(reference_raster_path)
        if not reference_raster_path.exists():
            raise LayerExportError(f"Reference raster not found: {reference_raster_path}")
        with rasterio.open(reference_raster_path) as reference:
            if (
                (height, width) != reference.shape
                or crs != reference.crs
                or transform != reference.transform
            ):
                raise LayerExportError(
                    f"{raster_path.name} is not aligned with {reference_raster_path.name}."
                )

    valid = np.isfinite(data)
    if nodata is not None:
        valid &= data != nodata
    if alpha_mask is not None:
        if alpha_mask.shape != data.shape:
            raise LayerExportError(
                f"Alpha mask shape {alpha_mask.shape} does not match {raster_path.name} shape {data.shape}."
            )
        valid &= alpha_mask

    if not np.any(valid):
        raise LayerExportError(f"No valid pixels in {raster_path.name}")

    if not np.isfinite(scale_factor) or scale_factor <= 0:
        raise LayerExportError("Raster scale factor must be a finite positive number.")
    data *= scale_factor
    min_val = float(np.min(data[valid]))
    max_val = float(np.max(data[valid]))

    if value_range is not None:
        cmin, cmax = value_range
    elif symmetric_range:
        max_abs = max(abs(min_val), abs(max_val), 1e-4)
        cmin, cmax = -max_abs, max_abs
    else:
        cmin, cmax = min_val, max_val

    span = max(cmax - cmin, 1e-6)
    normalized = np.clip((data - cmin) / span, 0.0, 1.0)

    try:
        cmap = plt.colormaps[colormap_name]
    except KeyError:
        cmap = plt.colormaps["viridis"]

    rgba = cmap(normalized)

    # Optional hillshade enhancement
    if dem_for_hillshade and Path(dem_for_hillshade).exists():
        try:
            with rasterio.open(dem_for_hillshade) as dem_src:
                dem = dem_src.read(1).astype(np.float32)
                res_x = float(dem_src.transform.a)
                res_y = float(-dem_src.transform.e)

            dem_valid = np.isfinite(dem)
            if dem_src.nodata is not None:
                dem_valid &= dem != dem_src.nodata
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
            for i in range(3):
                rgba[:, :, i] = np.clip(rgba[:, :, i] * shade_factor, 0.0, 1.0)
        except Exception:
            pass

    # Transparency on invalid or nodata pixels
    rgba[:, :, 3] = np.where(valid, 1.0, 0.0)

    img = Image.fromarray((rgba * 255).astype(np.uint8))
    img_hd = img.resize(resolution, Image.Resampling.BICUBIC)
    img_hd.save(output_png_path, format="PNG")

    # Compute exact WGS84 bounding coordinates
    res_x = float(transform.a)
    res_y = float(-transform.e)
    left = transform.c
    right = transform.c + width * res_x
    top = transform.f
    bottom = transform.f - height * res_y

    transformer = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    west, south = transformer.transform(left, bottom)
    east, north = transformer.transform(right, top)

    bounds = {
        "west": float(west),
        "south": float(south),
        "east": float(east),
        "north": float(north),
        "min_value": min_val,
        "max_value": max_val,
    }

    return str(output_png_path), bounds


def export_risk_zones_raster(
    base_dir: str | Path,
    output_png_path: str | Path,
    resolution: Tuple[int, int] = (1024, 1024),
    risk_data=None,
) -> Tuple[str, Dict[str, float]]:
    """Export the multi-criteria risk assessment classification into an RGBA overlay."""
    base_dir = Path(base_dir)
    dem_path = base_dir / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_dem_80m_gsi_aoi.tif"
    evidence_csv = base_dir / "data" / "features" / "tirumala_final_agent_evidence.csv"

    if not dem_path.exists() or not evidence_csv.exists():
        raise LayerExportError("Missing DEM or evidence table for risk zone export.")

    import pandas as pd

    with rasterio.open(dem_path) as src:
        height, width = src.shape
        transform = src.transform
        crs = src.crs

    if risk_data is None:
        df = pd.read_csv(evidence_csv)
    else:
        df = risk_data
        if not {"row", "col", "risk_category"}.issubset(df.columns):
            raise LayerExportError(
                "Latest database risk records need row, col, and risk_category."
            )

    # Initialize RGBA image: Transparent background
    rgba = np.zeros((height, width, 4), dtype=np.float32)

    # Colors: Green for Low, Orange for Medium, Red for High
    color_map = {
        "low": (0.06, 0.72, 0.51, 0.75),       # #10b981
        "medium": (0.96, 0.62, 0.04, 0.80),    # #f59e0b
        "high": (0.94, 0.27, 0.27, 0.85),      # #ef4444
    }

    for _, row in df.iterrows():
        if pd.isna(row["row"]) or pd.isna(row["col"]):
            continue
        r = int(row["row"])
        c = int(row["col"])
        if 0 <= r < height and 0 <= c < width:
            category = str(row.get("agent_evidence_category", "Low")).lower()
            if "high" in category or "multiple" in category:
                col = color_map["high"]
            elif "medium" in category or "moderate" in category:
                col = color_map["medium"]
            else:
                col = color_map["low"]

            rgba[r, c] = col

    img = Image.fromarray((rgba * 255).astype(np.uint8))
    img_hd = img.resize(resolution, Image.Resampling.NEAREST) # Nearest to keep zone borders sharp
    img_hd.save(output_png_path, format="PNG")

    res_x = float(transform.a)
    res_y = float(-transform.e)
    left = transform.c
    right = transform.c + width * res_x
    top = transform.f
    bottom = transform.f - height * res_y

    transformer = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    west, south = transformer.transform(left, bottom)
    east, north = transformer.transform(right, top)

    bounds = {
        "west": float(west),
        "south": float(south),
        "east": float(east),
        "north": float(north),
        "min_value": 0.0,
        "max_value": 100.0,
    }
    return str(output_png_path), bounds


def export_all_gis_layers(
    base_dir: str | Path, output_dir: str | Path, db=None
) -> Dict[str, Any]:
    """Export complete multi-layer stack and generate layers_manifest.json for CesiumJS."""
    base_dir = Path(base_dir)
    output_dir = Path(output_dir)
    textures_dir = output_dir / "textures"
    textures_dir.mkdir(parents=True, exist_ok=True)

    gsi_aoi_dir = base_dir / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi"
    dem_path = gsi_aoi_dir / "tirumala_dem_80m_gsi_aoi.tif"
    slope_path = gsi_aoi_dir / "tirumala_slope_80m_gsi_aoi.tif"
    aspect_path = gsi_aoi_dir / "tirumala_aspect_80m_gsi_aoi.tif"
    los_path = gsi_aoi_dir / "tirumala_los_disp_80m_gsi_aoi.tif"
    corr_path = gsi_aoi_dir / "tirumala_corr_80m_gsi_aoi.tif"
    pair1_dir = gsi_aoi_dir / "pair_05_17"
    pair1_los_path = pair1_dir / "tirumala_los_disp_80m_gsi_aoi_pair_05_17.tif"
    pair1_corr_path = pair1_dir / "tirumala_corr_80m_gsi_aoi_pair_05_17.tif"

    if not dem_path.exists():
        raise LayerExportError(f"Reference DEM not found: {dem_path}")

    layers: List[Dict[str, Any]] = []

    # 1. Shaded Relief Elevation
    if dem_path.exists():
        p, b = raster_to_rgba_overlay(dem_path, textures_dir / "layer_elevation.png", "gist_earth")
        layers.append({
            "id": "elevation",
            "name": "Topographic Elevation",
            "url": "./textures/layer_elevation.png",
            "bounds": b,
            "unit": "meters",
            "default_opacity": 0.90,
            "default_visible": True,
            "legend": {"title": "Elevation (m)", "min": f"{b['min_value']:.0f} m", "max": f"{b['max_value']:.0f} m", "gradient": "linear-gradient(to right, #2b83ba, #abdda4, #ffffbf, #fdae61, #d7191c)"}
        })

    # 2. Slope Distribution
    if slope_path.exists():
        p, b = raster_to_rgba_overlay(
            slope_path, textures_dir / "layer_slope.png", "turbo",
            value_range=(0.0, 50.0), dem_for_hillshade=dem_path,
            reference_raster_path=dem_path
        )
        layers.append({
            "id": "slope",
            "name": "Topographic Slope",
            "url": "./textures/layer_slope.png",
            "bounds": b,
            "unit": "degrees",
            "default_opacity": 0.75,
            "default_visible": False,
            "legend": {"title": "Slope Angle (deg)", "min": "0° (Flat)", "max": "50° (Steep)", "gradient": "linear-gradient(to right, #30123b, #4686fb, #1ae4b6, #a2fc3c, #fbb31e, #d82b04)"}
        })

    # 3. Topographic Aspect (Slope Direction)
    if aspect_path.exists():
        with rasterio.open(aspect_path) as aspect_src:
            aspect_mask = aspect_src.read(1) >= 0.0
        p, b = raster_to_rgba_overlay(
            aspect_path, textures_dir / "layer_aspect.png", "twilight",
            value_range=(0.0, 360.0), dem_for_hillshade=dem_path,
            alpha_mask=aspect_mask,
            reference_raster_path=dem_path
        )
        layers.append({
            "id": "aspect",
            "name": "Topographic Aspect (Slope Facing)",
            "url": "./textures/layer_aspect.png",
            "bounds": b,
            "unit": "degrees",
            "default_opacity": 0.70,
            "default_visible": False,
            "legend": {"title": "Aspect (Azimuth)", "min": "0° (North)", "max": "360° (North)", "gradient": "linear-gradient(to right, #e08282, #e0d082, #82e096, #82d0e0, #9682e0, #e08282)"}
        })

    # 4. Sentinel-1 LOS Displacement
    if los_path.exists():
        if not corr_path.exists():
            raise LayerExportError(f"Coherence raster required to quality-mask LOS: {corr_path}")
        with rasterio.open(corr_path) as coherence_src:
            los_quality_mask = coherence_src.read(1) >= 0.5
        p, b = raster_to_rgba_overlay(
            los_path, textures_dir / "layer_los.png", "RdBu",
            value_range=(-48.0, 12.0), dem_for_hillshade=dem_path,
            alpha_mask=los_quality_mask,
            scale_factor=1000.0,
            reference_raster_path=dem_path
        )
        layers.append({
            "id": "los",
            "name": "Sentinel-1 LOS Displacement (Pair 2)",
            "url": "./textures/layer_los.png",
            "bounds": b,
            "unit": "mm",
            "default_opacity": 0.80,
            "default_visible": False,
            "legend": {"title": "InSAR LOS Disp (mm)", "min": "-48 mm (Subsidence)", "max": "+12 mm (Uplift)", "gradient": "linear-gradient(to right, #b2182b, #ef8a62, #f7f7f7, #67a9cf, #2166ac)"}
        })

    # 5. InSAR Coherence
    if corr_path.exists():
        with rasterio.open(corr_path) as coherence_src:
            coherence_mask = coherence_src.read(1) >= 0.5
        p, b = raster_to_rgba_overlay(
            corr_path, textures_dir / "layer_coherence.png", "viridis",
            value_range=(0.5, 1.0), dem_for_hillshade=dem_path,
            alpha_mask=coherence_mask,
            reference_raster_path=dem_path
        )
        layers.append({
            "id": "coherence",
            "name": "InSAR Quality Coherence (γ ≥ 0.50)",
            "url": "./textures/layer_coherence.png",
            "bounds": b,
            "unit": "ratio",
            "default_opacity": 0.75,
            "default_visible": False,
            "legend": {"title": "InSAR Coherence (γ)", "min": "0.50", "max": "1.00", "gradient": "linear-gradient(to right, #440154, #3b528b, #21918c, #5ec962, #fde725)"}
        })

    # 6. Spatial Risk Assessment Zones
    try:
        risk_data = None
        if db is not None:
            import pandas as pd

            observation_date = db.get_latest_processed_insar_date()
            observations = (
                db.get_observations_for_date(observation_date)
                if observation_date else []
            )
            grid = {
                cell["cell_id"]: cell for cell in db.get_all_grid_cells()
            }
            risk_data = pd.DataFrame([
                {
                    "row": grid[item["cell_id"]]["row_idx"],
                    "col": grid[item["cell_id"]]["col_idx"],
                    "risk_category": item.get("risk_category"),
                }
                for item in observations
                if item.get("cell_id") in grid
                and item.get("risk_category") in {"Low", "Medium", "High"}
            ])
            if risk_data.empty:
                raise LayerExportError(
                    "No valid risk records exist for the latest processed observation."
                )
        p, b = export_risk_zones_raster(
            base_dir,
            textures_dir / "layer_risk_zones.png",
            risk_data=risk_data,
        )
        layers.append({
            "id": "risk_zones",
            "name": "Landslide Risk Assessment Zones",
            "url": "./textures/layer_risk_zones.png",
            "bounds": b,
            "unit": "category",
            "default_opacity": 0.70,
            "default_visible": False,
            "legend": {"title": "Risk Category", "min": "Low (Green)", "max": "High (Red)", "gradient": "linear-gradient(to right, #10b981, #f59e0b, #ef4444)"}
        })
    except Exception as e:
        print(f"Warning: Could not export risk zones overlay: {e}")

    from .terrain_glb_builder import build_terrain_glb

    models_dir = output_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    terrain_metadata = None
    for layer in layers:
        model_name = f"tirumala_terrain_{layer['id']}.glb"
        model_path = models_dir / model_name
        texture_path = output_dir / layer["url"].replace("./", "", 1)
        model_metadata = build_terrain_glb(
            dem_path,
            model_path,
            texture_path=texture_path,
            vertical_exaggeration=1.0,
        )
        layer["model_url"] = f"./models/{model_name}"
        if terrain_metadata is None:
            terrain_metadata = model_metadata

    temporal_pairs: List[Dict[str, Any]] = []
    pair_specs = [
        {
            "pair_id": "PAIR_20260805_20260817",
            "reference_date": "2026-08-05",
            "secondary_date": "2026-08-17",
            "label": "05–17 Aug 2026",
            "los_path": pair1_los_path,
            "coherence_path": pair1_corr_path,
            "model_url": "./models/tirumala_terrain_los_pair_05_17.glb",
            "texture_url": "./textures/layer_los_pair_05_17.png",
        },
        {
            "pair_id": "PAIR_20260817_20260829",
            "reference_date": "2026-08-17",
            "secondary_date": "2026-08-29",
            "label": "17–29 Aug 2026",
            "los_path": los_path,
            "coherence_path": corr_path,
            "model_url": "./models/tirumala_terrain_los.glb",
            "texture_url": "./textures/layer_los.png",
        },
    ]
    for pair in pair_specs:
        los_source = pair["los_path"]
        coherence_source = pair["coherence_path"]
        if not los_source.exists() and not coherence_source.exists():
            continue
        if not los_source.exists() or not coherence_source.exists():
            raise LayerExportError(
                f"Both LOS and coherence rasters are required for {pair['pair_id']}."
            )
        if pair["pair_id"] == "PAIR_20260805_20260817":
            with rasterio.open(coherence_source) as coherence_src:
                quality_mask = coherence_src.read(1) >= 0.5
            texture_path, _ = raster_to_rgba_overlay(
                los_source,
                output_dir / pair["texture_url"].removeprefix("./"),
                "RdBu",
                value_range=(-48.0, 12.0),
                dem_for_hillshade=dem_path,
                alpha_mask=quality_mask,
                scale_factor=1000.0,
                reference_raster_path=dem_path,
            )
            build_terrain_glb(
                dem_path,
                output_dir / pair["model_url"].removeprefix("./"),
                texture_path=texture_path,
                vertical_exaggeration=1.0,
            )
        temporal_pairs.append({
            "pair_id": pair["pair_id"],
            "reference_date": pair["reference_date"],
            "secondary_date": pair["secondary_date"],
            "label": pair["label"],
            "model_url": pair["model_url"],
            "unit": "mm",
            "lookup_los_field": (
                "los_pair_05_17_m"
                if pair["pair_id"] == "PAIR_20260805_20260817"
                else "los_pair_17_29_m"
            ),
            "lookup_coherence_field": (
                "corr_pair_05_17"
                if pair["pair_id"] == "PAIR_20260805_20260817"
                else "corr_pair_17_29"
            ),
            "reference_note": (
                "LOS displacement is relative to this pair’s own phase reference. "
                "Cross-pair subtraction is not shown."
            ),
        })

    manifest = {
        "study_area": "Tirumala Hills, Andhra Pradesh, India",
        "bounds": layers[0]["bounds"] if layers else {},
        "terrain": {
            "base_elevation_m": terrain_metadata["base_elevation_m"],
            "center_longitude": terrain_metadata["center_longitude"],
            "center_latitude": terrain_metadata["center_latitude"],
            "cell_size_m": terrain_metadata["cell_size_m"],
            "vertical_exaggeration": terrain_metadata["vertical_exaggeration"],
        },
        "temporal": {
            "insar_pairs": temporal_pairs,
            "scope_note": (
                "Only processed InSAR pairs have map layers; rainfall and risk snapshots are listed, not mapped."
            ),
            "comparison_note": (
                "Each pair has its own phase reference; no cross-pair LOS difference is shown."
            ),
        },
        "layers": layers,
    }

    manifest_path = output_dir / "layers_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Exported {len(layers)} multi-layer overlays to {manifest_path}")
    return manifest
