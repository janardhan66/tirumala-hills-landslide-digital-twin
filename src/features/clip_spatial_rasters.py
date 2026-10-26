import rasterio
import geopandas as gpd
from rasterio.mask import mask
import os

# AOI
aoi_file = "data/raw/aoi/moghalrajpuram_aoi.geojson"

# Input rasters
rasters = {
    "los_displacement": (
        "data/processed/dinsar/"
        "S1DD_20260817T003008_20260829T003009_VVR012_INT40_G_ueF_DE75_los_disp.tif"
    ),
    "coherence": (
        "data/processed/dinsar/"
        "S1DD_20260817T003008_20260829T003009_VVR012_INT40_G_ueF_DE75_corr.tif"
    ),
    "elevation": (
        "data/processed/dem/"
        "moghalrajpuram_copernicus_dem_40m.tif"
    ),
    "slope": (
        "data/processed/dem/"
        "moghalrajpuram_copernicus_slope_40m.tif"
    )
}

# Output directory
output_dir = "data/processed/aoi"
os.makedirs(output_dir, exist_ok=True)

# Read AOI
aoi = gpd.read_file(aoi_file)

print("=" * 70)
print("CLIPPING RASTERS TO MOHALRAJPURAM AOI")
print("=" * 70)

for name, input_file in rasters.items():

    with rasterio.open(input_file) as src:

        # Reproject AOI to raster CRS if necessary
        aoi_projected = aoi.to_crs(src.crs)

        geometries = aoi_projected.geometry.values

        # Clip raster
        clipped, transform = mask(
            src,
            geometries,
            crop=True,
            nodata=-9999
        )

        profile = src.profile.copy()

        profile.update(
            height=clipped.shape[1],
            width=clipped.shape[2],
            transform=transform,
            nodata=-9999
        )

        output_file = os.path.join(
            output_dir,
            f"moghalrajpuram_{name}_40m.tif"
        )

        with rasterio.open(output_file, "w", **profile) as dst:
            dst.write(clipped)

        print()
        print("Created:", output_file)
        print("Size:", clipped.shape[2], "x", clipped.shape[1])
        print("CRS:", src.crs)

print()
print("=" * 70)
print("AOI CLIPPING COMPLETED")
print("=" * 70)