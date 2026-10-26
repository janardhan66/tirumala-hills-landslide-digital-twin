import os
import numpy as np
import rasterio

los_file = r"data\processed\dinsar\tirumala\clipped\tirumala_los_disp_80m.tif"
corr_file = r"data\processed\dinsar\tirumala\clipped\tirumala_corr_80m.tif"

output_file = r"data\processed\dinsar\tirumala\clipped\tirumala_masked_los_disp_80m.tif"

threshold = 0.5

with rasterio.open(los_file) as los_src:
    los = los_src.read(1)
    profile = los_src.profile.copy()
    los_nodata = los_src.nodata

with rasterio.open(corr_file) as corr_src:
    corr = corr_src.read(1)
    corr_nodata = corr_src.nodata

valid_los = np.isfinite(los) & (los != los_nodata)
valid_corr = np.isfinite(corr) & (corr != corr_nodata)

good_quality = valid_los & valid_corr & (corr >= threshold)

masked_los = np.full(
    los.shape,
    np.nan,
    dtype=np.float32
)

masked_los[good_quality] = los[good_quality]

profile.update(
    dtype="float32",
    count=1,
    nodata=np.nan,
    compress="deflate"
)

with rasterio.open(output_file, "w", **profile) as dst:
    dst.write(masked_los, 1)

valid_pixels = np.sum(np.isfinite(masked_los))

print("Created:", output_file)
print("Correlation threshold:", threshold)
print("Retained LOS pixels:", valid_pixels)

if valid_pixels > 0:
    values = masked_los[np.isfinite(masked_los)]

    print("MIN LOS:", float(np.min(values)))
    print("MAX LOS:", float(np.max(values)))
    print("MEAN LOS:", float(np.mean(values)))