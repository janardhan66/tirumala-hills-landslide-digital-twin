import rasterio
import numpy as np

input_file = "data/processed/dem/moghalrajpuram_copernicus_dem_utm.tif"
output_file = "data/processed/dem/moghalrajpuram_copernicus_slope.tif"

with rasterio.open(input_file) as src:
    dem = src.read(1).astype(np.float32)
    profile = src.profile.copy()
    nodata = src.nodata
    pixel_size = src.res[0]

    valid = dem != nodata

    # Temporarily replace NoData with nearest valid values
    filled_dem = dem.copy()

    if np.any(~valid):
        valid_values = dem[valid]
        fill_value = np.nanmedian(valid_values)
        filled_dem[~valid] = fill_value

    # Calculate elevation gradients
    dz_dy, dz_dx = np.gradient(
        filled_dem,
        pixel_size,
        pixel_size
    )

    # Calculate slope in degrees
    slope = np.degrees(
        np.arctan(
            np.sqrt(dz_dx**2 + dz_dy**2)
        )
    )

    # Set original NoData cells to NoData
    slope[~valid] = -9999

    profile.update(
        dtype="float32",
        count=1,
        nodata=-9999
    )

    with rasterio.open(output_file, "w", **profile) as dst:
        dst.write(slope.astype(np.float32), 1)

print("SLOPE CREATED SUCCESSFULLY")
print("=" * 70)
print("Input :", input_file)
print("Output:", output_file)
print("Pixel size:", pixel_size, "meters")