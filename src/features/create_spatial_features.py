import rasterio
import pandas as pd
import numpy as np
import os

# --------------------------------------------------
# Input files
# --------------------------------------------------

LOS_FILE = "data/processed/aoi/moghalrajpuram_los_displacement_40m.tif"
COH_FILE = "data/processed/aoi/moghalrajpuram_coherence_40m.tif"
DEM_FILE = "data/processed/aoi/moghalrajpuram_elevation_40m.tif"
SLOPE_FILE = "data/processed/aoi/moghalrajpuram_slope_40m.tif"

OUTPUT_FILE = "data/features/moghalrajpuram_spatial_features.csv"

os.makedirs("data/features", exist_ok=True)

# --------------------------------------------------
# Read rasters
# --------------------------------------------------

with rasterio.open(LOS_FILE) as src:
    los = src.read(1)
    transform = src.transform
    crs = src.crs
    height = src.height
    width = src.width

with rasterio.open(COH_FILE) as src:
    coherence = src.read(1)

with rasterio.open(DEM_FILE) as src:
    dem = src.read(1)

with rasterio.open(SLOPE_FILE) as src:
    slope = src.read(1)

# --------------------------------------------------
# Check dimensions
# --------------------------------------------------

if not (
    los.shape == coherence.shape
    == dem.shape
    == slope.shape
):
    raise ValueError("Raster dimensions do not match.")

print("Raster dimensions:", los.shape)
print("CRS:", crs)
print("Total pixels:", height * width)

# --------------------------------------------------
# Create row/column indices
# --------------------------------------------------

rows, cols = np.indices((height, width))

# --------------------------------------------------
# Convert pixel locations to map coordinates
# --------------------------------------------------

xs, ys = rasterio.transform.xy(
    transform,
    rows,
    cols,
    offset="center"
)

xs = np.asarray(xs)
ys = np.asarray(ys)

# --------------------------------------------------
# Convert UTM coordinates to longitude/latitude
# --------------------------------------------------

from pyproj import Transformer

transformer = Transformer.from_crs(
    crs,
    "EPSG:4326",
    always_xy=True
)

lon, lat = transformer.transform(xs, ys)

# --------------------------------------------------
# Flatten all arrays
# --------------------------------------------------

df = pd.DataFrame({
    "pixel_id": np.arange(height * width),

    "row": rows.ravel(),
    "column": cols.ravel(),

    "x_utm": xs.ravel(),
    "y_utm": ys.ravel(),

    "longitude": np.asarray(lon).ravel(),
    "latitude": np.asarray(lat).ravel(),

    "elevation_m": dem.ravel(),

    "slope_deg": slope.ravel(),

    "los_displacement_m": los.ravel(),

    "coherence": coherence.ravel()
})

# --------------------------------------------------
# Replace invalid values
# --------------------------------------------------

df.replace(
    [np.inf, -np.inf],
    np.nan,
    inplace=True
)

# Treat known NoData values as missing
df.loc[df["elevation_m"] == -9999, "elevation_m"] = np.nan
df.loc[df["slope_deg"] == -9999, "slope_deg"] = np.nan

# Coherence and LOS products use 0 as NoData,
# but zero can also be a meaningful value.
# Therefore we do NOT automatically remove zero here.
# Quality filtering will be handled separately.

# --------------------------------------------------
# Save
# --------------------------------------------------

df.to_csv(OUTPUT_FILE, index=False)

print("\nSPATIAL FEATURE DATASET CREATED")
print("=" * 60)
print("Output:", OUTPUT_FILE)
print("Rows:", len(df))
print("Columns:", len(df.columns))
print("\nColumns:")
print(list(df.columns))

print("\nFirst 5 rows:")
print(df.head())