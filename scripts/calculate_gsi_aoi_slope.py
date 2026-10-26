import numpy as np
import rasterio
import os

input_file = "data/processed/dinsar/tirumala/gsi_aoi/tirumala_dem_80m_gsi_aoi.tif"
output_file = "data/processed/dinsar/tirumala/gsi_aoi/tirumala_slope_80m_gsi_aoi.tif"

with rasterio.open(input_file) as src:
    dem = src.read(1).astype(np.float32)
    profile = src.profile.copy()

    valid = np.isfinite(dem) & (dem != 0)

    # Calculate gradients only after temporarily filling nodata
    # with nearest valid values. The final slope mask removes
    # cells where a complete 3x3 neighborhood is unavailable.
    filled = dem.copy()

    # Nearest-neighbor filling using iterative propagation
    for _ in range(10):
        missing = ~valid
        if not missing.any():
            break

        candidates = [
            np.roll(filled, 1, axis=0),
            np.roll(filled, -1, axis=0),
            np.roll(filled, 1, axis=1),
            np.roll(filled, -1, axis=1)
        ]

        for candidate in candidates:
            use = missing & (candidate != 0) & np.isfinite(candidate)
            filled[use] = candidate[use]
            valid[use] = True

    # Calculate terrain gradient
    dz_dy, dz_dx = np.gradient(filled, 80.0, 80.0)

    slope_rad = np.arctan(
        np.sqrt(dz_dx**2 + dz_dy**2)
    )

    slope_deg = np.degrees(slope_rad)

    # Identify cells whose 3x3 neighborhood is completely valid
    original_valid = (dem != 0) & np.isfinite(dem)

    neighbor_valid = original_valid.copy()

    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            shifted = np.roll(np.roll(original_valid, dr, axis=0), dc, axis=1)
            neighbor_valid &= shifted

    # Remove artificial edge wrapping
    neighbor_valid[0, :] = False
    neighbor_valid[-1, :] = False
    neighbor_valid[:, 0] = False
    neighbor_valid[:, -1] = False

    slope_deg[~neighbor_valid] = 0

    profile.update(
        dtype="float32",
        count=1,
        nodata=0
    )

    with rasterio.open(output_file, "w", **profile) as dst:
        dst.write(slope_deg.astype(np.float32), 1)

valid_slope = slope_deg[slope_deg != 0]

print("Nodata-aware slope created successfully.")
print("Output:", output_file)
print("Valid slope pixels:", len(valid_slope))
print("Minimum slope:", valid_slope.min())
print("Maximum slope:", valid_slope.max())
print("Mean slope:", valid_slope.mean())