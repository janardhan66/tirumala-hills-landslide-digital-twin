import os
import numpy as np
import pandas as pd
import rasterio

folder = r"data\processed\dinsar\tirumala\clipped"

dem_file = os.path.join(folder, "tirumala_dem_80m.tif")
slope_file = os.path.join(folder, "tirumala_slope_80m.tif")
corr_file = os.path.join(folder, "tirumala_corr_80m.tif")
los_file = os.path.join(folder, "tirumala_masked_los_disp_80m.tif")

output_dir = r"data\features"
output_file = os.path.join(output_dir, "tirumala_insar_terrain_features.csv")

os.makedirs(output_dir, exist_ok=True)

with rasterio.open(dem_file) as src:
    dem = src.read(1)
    profile = src.profile

with rasterio.open(slope_file) as src:
    slope = src.read(1)

with rasterio.open(corr_file) as src:
    corr = src.read(1)

with rasterio.open(los_file) as src:
    los = src.read(1)

# Valid feature pixels
valid = (
    np.isfinite(dem) &
    np.isfinite(slope) &
    np.isfinite(corr) &
    np.isfinite(los) &
    (corr >= 0.5)
)

rows, cols = np.where(valid)

features = pd.DataFrame({
    "row": rows,
    "col": cols,
    "elevation_m": dem[valid],
    "slope_deg": slope[valid],
    "correlation": corr[valid],
    "los_disp_m": los[valid],
    "los_abs_m": np.abs(los[valid])
})

features.to_csv(output_file, index=False)

print("Created:", output_file)
print("Rows:", len(features))
print("Columns:", len(features.columns))

print("\nFeature statistics:")
print(features.describe())