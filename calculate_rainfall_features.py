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

# Load AOI
aoi = gpd.read_file(AOI_PATH)

results = []

files = sorted(glob.glob(os.path.join(RAIN_DIR, "*.tif")))

for path in files:

    filename = os.path.basename(path)

    match = re.search(r"IMERG\.(\d{8})\.V07C", filename)

    if not match:
        continue

    date_str = match.group(1)

    with rasterio.open(path) as src:

        aoi_src = aoi.to_crs(src.crs)

        data, transform = mask(
            src,
            aoi_src.geometry,
            crop=True
        )

        raw = data[0].astype(np.float32)

        # IMERG daily GIS values are scaled by 10
        rainfall_mm = raw / 10.0

        valid = rainfall_mm[np.isfinite(rainfall_mm)]

        if len(valid) == 0:
            continue

        results.append({
            "date": pd.to_datetime(
                date_str,
                format="%Y%m%d"
            ),
            "rainfall_mean_mm": float(
                np.mean(valid)
            ),
            "rainfall_min_mm": float(
                np.min(valid)
            ),
            "rainfall_max_mm": float(
                np.max(valid)
            ),
            "grid_cells": int(len(valid))
        })


# Create dataframe
df = pd.DataFrame(results)

df = df.sort_values("date").reset_index(drop=True)


# --------------------------------------------------
# Rainfall temporal features
# --------------------------------------------------

# Cumulative rainfall ending on each date
df["rainfall_3day_mm"] = (
    df["rainfall_mean_mm"]
    .rolling(window=3, min_periods=1)
    .sum()
)

df["rainfall_7day_mm"] = (
    df["rainfall_mean_mm"]
    .rolling(window=7, min_periods=1)
    .sum()
)

df["rainfall_14day_mm"] = (
    df["rainfall_mean_mm"]
    .rolling(window=14, min_periods=1)
    .sum()
)


# Maximum daily rainfall during preceding windows
df["max_daily_rainfall_3day_mm"] = (
    df["rainfall_mean_mm"]
    .rolling(window=3, min_periods=1)
    .max()
)

df["max_daily_rainfall_7day_mm"] = (
    df["rainfall_mean_mm"]
    .rolling(window=7, min_periods=1)
    .max()
)


# Save complete rainfall feature table
out_csv = os.path.join(
    OUT_DIR,
    "tirumala_rainfall_features_20260811_20260829.csv"
)

df.to_csv(out_csv, index=False)


# --------------------------------------------------
# Display results
# --------------------------------------------------

print()
print("=" * 80)
print("TIRUMALA RAINFALL FEATURES")
print("=" * 80)

print(df.to_string(index=False))

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

print("Number of days:", len(df))
print(
    "Total rainfall:",
    round(df["rainfall_mean_mm"].sum(), 3),
    "mm"
)

print(
    "Maximum daily rainfall:",
    round(df["rainfall_mean_mm"].max(), 3),
    "mm"
)

max_date = df.loc[
    df["rainfall_mean_mm"].idxmax(),
    "date"
]

print(
    "Maximum rainfall date:",
    max_date.strftime("%Y-%m-%d")
)

print()
print("Saved:", out_csv)