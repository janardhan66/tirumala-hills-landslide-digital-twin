import rasterio
from rasterio.warp import reproject, Resampling
import numpy as np
import os

# Sentinel-1 InSAR raster = reference grid
reference_file = (
    "data/processed/dinsar/"
    "S1DD_20260817T003008_20260829T003009_VVR012_INT40_G_ueF_DE75_los_disp.tif"
)

dem_file = "data/processed/dem/moghalrajpuram_copernicus_dem_utm.tif"

slope_file = "data/processed/dem/moghalrajpuram_copernicus_slope.tif"

output_dem = "data/processed/dem/moghalrajpuram_copernicus_dem_40m.tif"

output_slope = "data/processed/dem/moghalrajpuram_copernicus_slope_40m.tif"


def align_raster(input_file, output_file, reference_file):
    with rasterio.open(reference_file) as ref:
        ref_crs = ref.crs
        ref_transform = ref.transform
        ref_width = ref.width
        ref_height = ref.height

        profile = ref.profile.copy()

    with rasterio.open(input_file) as src:
        source = src.read(1).astype(np.float32)

        if src.nodata is not None:
            source[source == src.nodata] = np.nan

        destination = np.full(
            (ref_height, ref_width),
            np.nan,
            dtype=np.float32
        )

        reproject(
            source=source,
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=np.nan,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear
        )

    profile.update(
        dtype="float32",
        count=1,
        nodata=-9999
    )

    destination[np.isnan(destination)] = -9999

    with rasterio.open(output_file, "w", **profile) as dst:
        dst.write(destination, 1)

    print("CREATED:", output_file)


print("=" * 70)
print("ALIGNING TERRAIN DATA TO SENTINEL-1 40m GRID")
print("=" * 70)

align_raster(
    dem_file,
    output_dem,
    reference_file
)

align_raster(
    slope_file,
    output_slope,
    reference_file
)

print("=" * 70)
print("TERRAIN ALIGNMENT COMPLETED")
print("=" * 70)