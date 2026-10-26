import os
import numpy as np
import rasterio

input_file = r"data\processed\dinsar\tirumala\clipped\tirumala_corr_80m.tif"
output_file = r"data\processed\dinsar\tirumala\clipped\tirumala_insar_quality_mask_80m.tif"

threshold = 0.5

with rasterio.open(input_file) as src:
    correlation = src.read(1)
    profile = src.profile.copy()

    valid = (
        np.isfinite(correlation) &
        (correlation != src.nodata)
    )

    mask = np.zeros(correlation.shape, dtype=np.uint8)
    mask[valid & (correlation >= threshold)] = 1

    profile.update(
        dtype="uint8",
        count=1,
        nodata=0,
        compress="deflate"
    )

    with rasterio.open(output_file, "w", **profile) as dst:
        dst.write(mask, 1)

valid_pixels = np.sum(valid)
good_pixels = np.sum(mask == 1)

print("Created:", output_file)
print("Correlation threshold:", threshold)
print("Valid pixels:", valid_pixels)
print("Good-quality pixels:", good_pixels)
print(
    "Good-quality percentage:",
    round(good_pixels / valid_pixels * 100, 2),
    "%"
)