import numpy as np
import rasterio

corr_file = "data/processed/dinsar/tirumala/gsi_aoi/tirumala_corr_80m_gsi_aoi.tif"
los_file = "data/processed/dinsar/tirumala/gsi_aoi/tirumala_los_disp_80m_gsi_aoi.tif"
output_file = "data/processed/dinsar/tirumala/gsi_aoi/tirumala_masked_los_disp_80m_gsi_aoi.tif"

threshold = 0.5

with rasterio.open(corr_file) as corr_src:
    corr = corr_src.read(1)
    corr_profile = corr_src.profile.copy()

with rasterio.open(los_file) as los_src:
    los = los_src.read(1)
    los_profile = los_src.profile.copy()

# Valid quality mask
quality_mask = (corr >= threshold) & (corr != 0) & (los != 0)

# Mask low-correlation pixels
masked_los = np.where(quality_mask, los, 0).astype(np.float32)

los_profile.update(
    dtype="float32",
    count=1,
    nodata=0
)

with rasterio.open(output_file, "w", **los_profile) as dst:
    dst.write(masked_los, 1)

valid = masked_los[quality_mask]

print("InSAR quality mask applied successfully.")
print("Correlation threshold:", threshold)
print("Total pixels:", corr.size)
print("Quality-valid pixels:", len(valid))
print("Percentage valid:", len(valid) / corr.size * 100)
print("LOS minimum (m):", valid.min())
print("LOS maximum (m):", valid.max())
print("LOS mean (m):", valid.mean())
print("LOS minimum (mm):", valid.min() * 1000)
print("LOS maximum (mm):", valid.max() * 1000)
print("LOS mean (mm):", valid.mean() * 1000)
print("Output:", output_file)