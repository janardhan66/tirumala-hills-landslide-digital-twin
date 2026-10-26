import os
import glob
import re

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.mask import mask


RAIN_DIR = r"data\raw\rainfall\tirumala"
AOI_PATH = r"data\raw\aoi\tirumala_hills_aoi.geojson"
OUT_DIR = r"data\processed\rainfall\tirumala"

os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------
# Load Tirumala AOI
# ---------------------------------------------------------
aoi = gpd.read_file(AOI_PATH)

print("AOI CRS:", aoi.crs)
print("AOI bounds:", aoi.total_bounds)


results = []


# ---------------------------------------------------------
# Process each daily IMERG GeoTIFF
# ---------------------------------------------------------
files = sorted(glob.glob(os.path.join(RAIN_DIR, "*.tif")))

for path in files:

    filename = os.path.basename(path)

    # Extract date from filename
    match = re.search(r"IMERG\.(\d{8})\.V07C", filename)

    if not match:
        print("Skipping:", filename)
        continue

    date_str = match.group(1)
    date = pd.to_datetime(date_str, format="%Y%m%d")


    with rasterio.open(path) as src:

        # Reproject AOI if necessary
        aoi_src = aoi.to_crs(src.crs)

        # Crop raster to AOI
        data, transform = mask(
            src,
            aoi_src.geometry,
            crop=True
        )

        raw = data[0].astype(np.float32)

        # IMERG Late Run daily accumulation:
        # stored integer / 10 = millimeters
        rainfall_mm = raw / 10.0

        # There is no nodata value in these files.
        # Remove invalid numerical values if any.
        valid = rainfall_mm[np.isfinite(rainfall_mm)]

        if len(valid) == 0:
            print("No valid rainfall:", filename)
            continue

        results.append({
            "date": date.strftime("%Y-%m-%d"),
            "rainfall_mean_mm": float(np.mean(valid)),
            "rainfall_min_mm": float(np.min(valid)),
            "rainfall_max_mm": float(np.max(valid)),
            "grid_cells": int(len(valid)),
            "source_file": filename
        })

        print(
            f"{date.strftime('%Y-%m-%d')} | "
            f"mean={np.mean(valid):.2f} mm | "
            f"min={np.min(valid):.2f} mm | "
            f"max={np.max(valid):.2f} mm | "
            f"cells={len(valid)}"
        )


# ---------------------------------------------------------
# Save rainfall table
# ---------------------------------------------------------
df = pd.DataFrame(results)

df = df.sort_values("date").reset_index(drop=True)

out_csv = os.path.join(
    OUT_DIR,
    "tirumala_daily_rainfall_20260817_20260829.csv"
)

df.to_csv(out_csv, index=False)

print()
print("=" * 70)
print("RAINfall extraction completed")
print("=" * 70)
print(df.to_string(index=False))
print()
print("Saved:", out_csv)