import rasterio
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

aoi_dir = PROJECT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi"

pair_05_17 = aoi_dir / "pair_05_17" / "tirumala_los_disp_80m_gsi_aoi_pair_05_17.tif"
pair_17_29 = aoi_dir / "tirumala_los_disp_80m_gsi_aoi.tif"

corr_05_17 = aoi_dir / "pair_05_17" / "tirumala_corr_80m_gsi_aoi_pair_05_17.tif"
corr_17_29 = aoi_dir / "tirumala_corr_80m_gsi_aoi.tif"

output_dir = PROJECT / "data" / "features"
output_dir.mkdir(parents=True, exist_ok=True)

def read_raster(path):
    with rasterio.open(path) as src:
        return src.read(1), src.profile

los1, profile = read_raster(pair_05_17)
los2, _ = read_raster(pair_17_29)

corr1, _ = read_raster(corr_05_17)
corr2, _ = read_raster(corr_17_29)

print("\nTEMPORAL INSAR COMPARISON")
print("=========================")

print("Pair 1: 05 Aug -> 17 Aug 2026")
print("Pair 2: 17 Aug -> 29 Aug 2026")

print("\nShape:")
print("05-17:", los1.shape)
print("17-29:", los2.shape)

if los1.shape != los2.shape:
    raise ValueError("Raster dimensions do not match.")

# Valid data mask
valid = (
    np.isfinite(los1) &
    np.isfinite(los2) &
    np.isfinite(corr1) &
    np.isfinite(corr2) &
    (los1 != 0) &
    (los2 != 0) &
    (corr1 >= 0.5) &
    (corr2 >= 0.5)
)

change = np.full(los1.shape, np.nan, dtype=np.float32)

# Change between consecutive interferograms
change[valid] = los2[valid] - los1[valid]

valid_change = change[np.isfinite(change)]

print("\nQuality-valid pixels:", len(valid_change))

if len(valid_change) > 0:

    print("Temporal LOS change statistics")
    print("--------------------------------")
    print("Min change :", float(valid_change.min()), "m")
    print("Max change :", float(valid_change.max()), "m")
    print("Mean change:", float(valid_change.mean()), "m")
    print("Std change :", float(valid_change.std()), "m")

    print("\nAbsolute temporal change")
    print("------------------------")
    print("Mean absolute change:",
          float(np.mean(np.abs(valid_change))), "m")

    print("Maximum absolute change:",
          float(np.max(np.abs(valid_change))), "m")

# Save raster
profile.update(
    dtype="float32",
    count=1,
    nodata=np.nan
)

output_raster = aoi_dir / "tirumala_temporal_los_change_05_17_to_17_29.tif"

with rasterio.open(output_raster, "w", **profile) as dst:
    dst.write(change, 1)

# Create pixel-level feature table
rows, cols = np.where(np.isfinite(change))

records = []

for r, c in zip(rows, cols):
    records.append({
        "row": int(r),
        "col": int(c),
        "los_05_17_m": float(los1[r, c]),
        "los_17_29_m": float(los2[r, c]),
        "los_change_m": float(change[r, c]),
        "abs_los_change_m": float(abs(change[r, c])),
        "corr_05_17": float(corr1[r, c]),
        "corr_17_29": float(corr2[r, c])
    })

df = pd.DataFrame(records)

output_csv = output_dir / "tirumala_temporal_insar_features.csv"

df.to_csv(output_csv, index=False)

print("\nOutputs created:")
print("Raster:", output_raster)
print("CSV   :", output_csv)

print("\nTemporal comparison complete.")