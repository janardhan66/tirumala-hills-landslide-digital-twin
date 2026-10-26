import rasterio
import numpy as np
from pathlib import Path

project = Path(
    r"C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin"
)

dem_folder = project / "data" / "processed" / "dem"

dem_files = list(dem_folder.glob("*_dem.tif"))

if not dem_files:
    raise FileNotFoundError("No DEM file found.")

dem_file = dem_files[0]

print("Input DEM:")
print(dem_file)

with rasterio.open(dem_file) as src:

    dem = src.read(1).astype("float32")

    profile = src.profile.copy()
    transform = src.transform

    print("\nDEM information")
    print("----------------")
    print("Width      :", src.width)
    print("Height     :", src.height)
    print("CRS        :", src.crs)
    print("Resolution :", src.res)
    print("NoData     :", src.nodata)

    valid = np.isfinite(dem) & (dem != 0)

    pixel_x = abs(transform.a)
    pixel_y = abs(transform.e)

    dz_dy, dz_dx = np.gradient(
        dem,
        pixel_y,
        pixel_x
    )

    slope_radians = np.arctan(
        np.sqrt(dz_dx**2 + dz_dy**2)
    )

    slope_degrees = np.degrees(slope_radians)

    slope_degrees[~valid] = -9999

    profile.update(
        dtype="float32",
        count=1,
        nodata=-9999,
        compress="lzw"
    )

    output_file = dem_folder / "moghalrajpuram_slope.tif"

    with rasterio.open(
        output_file,
        "w",
        **profile
    ) as dst:

        dst.write(
            slope_degrees.astype("float32"),
            1
        )

print("\n================================")
print("SLOPE CALCULATION COMPLETED")
print("================================")
print("Output:")
print(output_file)