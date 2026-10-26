import os
import numpy as np
import rasterio
from rasterio.transform import xy

input_file = r"data\processed\dinsar\tirumala\clipped\tirumala_dem_80m.tif"
output_dir = r"data\processed\dinsar\tirumala\clipped"
output_file = os.path.join(output_dir, "tirumala_slope_80m.tif")

with rasterio.open(input_file) as src:
    dem = src.read(1, masked=True).astype("float32")
    profile = src.profile.copy()
    transform = src.transform

    # DEM resolution in meters
    xres = abs(transform.a)
    yres = abs(transform.e)

    # Fill masked cells temporarily for gradient calculation
    dem_filled = dem.filled(np.nan)

    # Calculate elevation gradients
    dz_dy, dz_dx = np.gradient(
        dem_filled,
        yres,
        xres
    )

    # Calculate slope in degrees
    slope = np.degrees(
        np.arctan(
            np.sqrt(
                dz_dx ** 2 +
                dz_dy ** 2
            )
        )
    )

    # Preserve NoData areas
    slope[dem.mask] = np.nan

    profile.update(
        dtype="float32",
        count=1,
        nodata=np.nan,
        compress="deflate"
    )

    with rasterio.open(output_file, "w", **profile) as dst:
        dst.write(slope.astype("float32"), 1)

print("Created:", output_file)

valid = slope[np.isfinite(slope)]

print("VALID PIXELS:", len(valid))
print("MIN SLOPE:", float(np.min(valid)))
print("MAX SLOPE:", float(np.max(valid)))
print("MEAN SLOPE:", float(np.mean(valid)))