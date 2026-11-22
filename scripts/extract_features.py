"""
Feature Extraction from Rasters

Extracts terrain, InSAR, and proximity features from processed GeoTIFFs
and updates the spatial evidence grid and observation snapshots in the database.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS, RISK, STUDY_AREA, setup_logging
from src.data.db import get_db

logger = setup_logging("extract_features")


def extract_raster_values(tif_path: str) -> Optional[np.ndarray]:
    """Read a single-band GeoTIFF into a numpy array."""
    try:
        import rasterio
        with rasterio.open(tif_path) as src:
            data = src.read(1)
            nodata = src.nodata
            if nodata is not None:
                data = np.where(data == nodata, np.nan, data)
            return data.astype(np.float64)
    except Exception as e:
        logger.error("Failed to read %s: %s", tif_path, e)
        return None


def extract_raster_metadata(tif_path: str) -> Optional[Dict]:
    """Get CRS, transform, and bounds from a GeoTIFF."""
    try:
        import rasterio
        with rasterio.open(tif_path) as src:
            return {
                "crs": str(src.crs),
                "transform": list(src.transform),
                "bounds": dict(zip(["left", "bottom", "right", "top"], src.bounds)),
                "shape": src.shape,
                "resolution": src.res,
            }
    except Exception as e:
        logger.error("Failed to read metadata from %s: %s", tif_path, e)
        return None


def compute_grid_coordinates(
    rows: int, cols: int, transform: list
) -> List[Dict]:
    """Compute UTM and WGS84 coordinates for each grid cell."""
    try:
        from pyproj import Transformer
        import rasterio.transform

        affine = rasterio.transform.Affine(*transform[:6])
        transformer = Transformer.from_crs(STUDY_AREA.epsg_projected, 4326, always_xy=True)

        cells = []
        for r in range(rows):
            for c in range(cols):
                # Cell center coordinates in UTM
                x_utm, y_utm = affine * (c + 0.5, r + 0.5)
                lon, lat = transformer.transform(x_utm, y_utm)
                cells.append({
                    "cell_id": f"R{r}_C{c}",
                    "row_idx": r,
                    "col_idx": c,
                    "utm_easting": round(x_utm, 1),
                    "utm_northing": round(y_utm, 1),
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                })
        return cells
    except Exception as e:
        logger.error("Coordinate computation failed: %s", e)
        return []


def compute_distance_to_gsi(lat: float, lon: float, gsi_points: List[Dict]) -> float:
    """Compute Euclidean distance (km) to nearest GSI landslide point."""
    if not gsi_points:
        return 999.0
    min_dist = float("inf")
    for pt in gsi_points:
        dlat = lat - pt["lat"]
        dlon = lon - pt["lon"]
        # Approximate degree-to-km at ~13.6°N latitude
        dist_km = np.sqrt((dlat * 110.9) ** 2 + (dlon * 101.3) ** 2)
        min_dist = min(min_dist, dist_km)
    return round(min_dist, 3)


def load_gsi_points() -> List[Dict]:
    """Load GSI historical landslide points from inventory CSV."""
    csv_path = PATHS.root / "data" / "raw" / "inventory" / "tirumala_gsi_fig32_map_derived_inventory.csv"
    if not csv_path.exists():
        logger.warning("GSI inventory not found: %s", csv_path)
        return []
    try:
        df = pd.read_csv(csv_path)
        lat_col = [c for c in df.columns if "lat" in c.lower()]
        lon_col = [c for c in df.columns if "lon" in c.lower()]
        if lat_col and lon_col:
            return [
                {"lat": row[lat_col[0]], "lon": row[lon_col[0]]}
                for _, row in df.iterrows()
                if pd.notna(row[lat_col[0]]) and pd.notna(row[lon_col[0]])
            ]
    except Exception as e:
        logger.error("Failed to load GSI points: %s", e)
    return []


def extract_all_features(observation_date: str) -> Dict:
    """
    Extract features from all available rasters and populate the database.
    
    Returns summary statistics.
    """
    try:
        parsed_date = datetime.strptime(observation_date, "%Y-%m-%d")
        if parsed_date.strftime("%Y-%m-%d") != observation_date:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("Observation date must use YYYY-MM-DD format.") from exc

    db = get_db()
    summary = {"cells_processed": 0, "features_extracted": [], "errors": []}

    # Load raster data
    rasters = {}
    raster_files = {
        "elevation_m": str(PATHS.dem_tif),
        "slope_deg": str(PATHS.slope_tif),
        "los_disp_m": str(PATHS.los_tif),
        "coherence": str(PATHS.corr_tif),
    }

    # Try aspect
    aspect_path = PATHS.processed_dinsar / "tirumala_aspect_80m_gsi_aoi.tif"
    if aspect_path.exists():
        raster_files["aspect_deg"] = str(aspect_path)

    metadata = None
    for name, path in raster_files.items():
        if Path(path).exists():
            data = extract_raster_values(path)
            if data is not None:
                rasters[name] = data
                summary["features_extracted"].append(name)
                if metadata is None:
                    metadata = extract_raster_metadata(path)
        else:
            logger.warning("Raster not found: %s (%s)", name, path)

    if not rasters or metadata is None:
        summary["errors"].append("No valid rasters found.")
        return summary

    rows, cols = metadata["shape"]
    logger.info("Grid: %d rows × %d cols (%d total cells)", rows, cols, rows * cols)

    # Compute coordinates
    grid_coords = compute_grid_coordinates(rows, cols, metadata["transform"])
    gsi_points = load_gsi_points()

    # Build feature records
    grid_records = []
    obs_records = []

    for cell in grid_coords:
        r, c = cell["row_idx"], cell["col_idx"]

        # Extract values at this cell
        elev = float(rasters["elevation_m"][r, c]) if "elevation_m" in rasters else np.nan
        slope = float(rasters["slope_deg"][r, c]) if "slope_deg" in rasters else np.nan
        los = float(rasters["los_disp_m"][r, c]) if "los_disp_m" in rasters else np.nan
        corr = float(rasters["coherence"][r, c]) if "coherence" in rasters else np.nan
        aspect = float(rasters["aspect_deg"][r, c]) if "aspect_deg" in rasters else None

        # Skip cells with no valid data
        if np.isnan(elev) and np.isnan(slope):
            continue

        # Distance to GSI
        dist_gsi = compute_distance_to_gsi(cell["latitude"], cell["longitude"], gsi_points)

        # Terrain evidence flag
        terrain_flag = 1 if (not np.isnan(slope) and slope >= RISK.high_slope_deg and
                             not np.isnan(elev) and elev >= RISK.high_elevation_m) else 0

        # InSAR evidence flag
        insar_flag = 1 if (not np.isnan(los) and abs(los * 1000) >= RISK.significant_los_mm and
                           not np.isnan(corr) and corr >= RISK.high_coherence) else 0

        grid_record = {
            "cell_id": cell["cell_id"],
            "row_idx": r, "col_idx": c,
            "utm_easting": cell["utm_easting"],
            "utm_northing": cell["utm_northing"],
            "latitude": cell["latitude"],
            "longitude": cell["longitude"],
            "elevation_m": round(elev, 1) if not np.isnan(elev) else 0,
            "slope_deg": round(slope, 2) if not np.isnan(slope) else 0,
            "aspect_deg": round(aspect, 1) if aspect and not np.isnan(aspect) else None,
            "dist_to_gsi_km": dist_gsi,
            "terrain_high_evidence": terrain_flag,
        }
        grid_records.append(grid_record)

        # Observation snapshot
        obs_record = {
            "cell_id": cell["cell_id"],
            "observation_date": observation_date,
            "los_disp_m": round(los, 6) if not np.isnan(los) else None,
            "coherence": round(corr, 4) if not np.isnan(corr) else None,
            "insar_high_evidence": insar_flag,
            "risk_score": 0,  # Will be calculated by risk engine
            "risk_category": "Low",
        }
        obs_records.append(obs_record)
        summary["cells_processed"] += 1

    # Populate database
    if grid_records:
        db.populate_spatial_grid(grid_records)
    if obs_records:
        db.bulk_add_observation_snapshots(obs_records)

    logger.info(
        "Feature extraction complete: %d cells, features: %s",
        summary["cells_processed"], ", ".join(summary["features_extracted"]),
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description="Extract spatial features for Tirumala grid.")
    parser.add_argument(
        "--observation-date",
        help="Observation date for this feature snapshot (YYYY-MM-DD). Defaults to the latest processed InSAR pair date.",
    )
    args = parser.parse_args()

    observation_date = args.observation_date
    if observation_date is None:
        observation_date = get_db().get_latest_processed_insar_date()
        if observation_date is None:
            parser.error("No processed InSAR pair date is available; pass --observation-date explicitly.")

    summary = extract_all_features(observation_date)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
