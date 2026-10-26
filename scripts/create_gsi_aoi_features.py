import numpy as np
import pandas as pd
import rasterio
import os

base = "data/processed/dinsar/tirumala/gsi_aoi"

files = {
    "elevation": os.path.join(base, "tirumala_dem_80m_gsi_aoi.tif"),
    "slope": os.path.join(base, "tirumala_slope_80m_gsi_aoi.tif"),
    "correlation": os.path.join(base, "tirumala_corr_80m_gsi_aoi.tif"),
    "los_disp": os.path.join(base, "tirumala_masked_los_disp_80m_gsi_aoi.tif"),
}

arrays = {}

for name, path in files.items():
    with rasterio.open(path) as src:
        arrays[name] = src.read(1).astype(np.float32)

# Quality-valid pixels
valid = (
    (arrays["correlation"] >= 0.5) &
    (arrays["elevation"] != 0) &
    (arrays["slope"] != 0) &
    (arrays["los_disp"] != 0)
)

rows, cols = np.where(valid)

df = pd.DataFrame({
    "row": rows,
    "col": cols,
    "elevation_m": arrays["elevation"][valid],
    "slope_deg": arrays["slope"][valid],
    "correlation": arrays["correlation"][valid],
    "los_disp_m": arrays["los_disp"][valid],
})

df["los_abs_m"] = np.abs(df["los_disp_m"])

output = "data/features/tirumala_insar_terrain_features_gsi_aoi.csv"

os.makedirs("data/features", exist_ok=True)
df.to_csv(output, index=False)

print("Feature dataset created successfully.")
print("Rows:", len(df))
print("Columns:", len(df.columns))
print("Output:", output)

print("\nStatistics:")
print(df.describe())