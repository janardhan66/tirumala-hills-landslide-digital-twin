"""Calculate Topographic Aspect (slope direction) in degrees for Tirumala Hills DEM."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import rasterio


def calculate_dem_aspect(
    dem_path: str | Path,
    output_aspect_path: str | Path,
) -> Path:
    """Calculate topographic aspect (0 to 360 degrees clockwise from North, -1 for flat) from DEM."""
    dem_path = Path(dem_path)
    output_aspect_path = Path(output_aspect_path)
    output_aspect_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        transform = src.transform
        crs = src.crs
        nodata = src.nodata

    valid = np.isfinite(dem)
    if nodata is not None:
        valid &= dem != nodata

    dem_filled = np.where(valid, dem, np.nanmean(dem[valid]))

    res_x = float(transform.a)
    res_y = float(-transform.e)

    # Horn's gradient: dy (North-South), dx (East-West)
    dy, dx = np.gradient(dem_filled, res_y, res_x)

    # In cartography, aspect is azimuth measured clockwise from North:
    # 0 = North, 90 = East, 180 = South, 270 = West, -1 = Flat
    slope_mag = np.sqrt(dx * dx + dy * dy)
    
    # angle from positive X axis (East) CCW is arctan2(dy, -dx)
    # Azimuth clockwise from North: (450 - degrees) % 360
    math_angle_deg = np.degrees(np.arctan2(dy, -dx))
    compass_aspect = (450.0 - math_angle_deg) % 360.0

    # Mark nearly flat areas (< 0.5 degree slope) as -1
    slope_deg = np.degrees(np.arctan(slope_mag))
    compass_aspect[slope_deg < 0.5] = -1.0
    compass_aspect[~valid] = -9999.0

    meta = src.meta.copy()
    meta.update({
        "dtype": "float32",
        "nodata": -9999.0,
    })

    with rasterio.open(output_aspect_path, "w", **meta) as dst:
        dst.write(compass_aspect.astype(np.float32), 1)

    print(f"Calculated topographic aspect saved to {output_aspect_path}")
    return output_aspect_path


if __name__ == "__main__":
    dem_file = Path("data/processed/dinsar/tirumala/gsi_aoi/tirumala_dem_80m_gsi_aoi.tif")
    out_file = Path("data/processed/dinsar/tirumala/gsi_aoi/tirumala_aspect_80m_gsi_aoi.tif")
    calculate_dem_aspect(dem_file, out_file)
