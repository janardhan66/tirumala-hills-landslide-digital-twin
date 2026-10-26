import geopandas as gpd
import rasterio
from rasterio.mask import mask
import os

# --------------------------------------------------
# Paths
# --------------------------------------------------

AOI_FILE = "data/raw/aoi/moghalrajpuram_aoi.geojson"

INPUT_FILES = {
    "los_disp": "data/processed/dinsar/S1DD_20260817T003008_20260829T003009_VVR012_INT40_G_ueF_DE75_los_disp.tif",
    "coherence": "data/processed/dinsar/S1DD_20260817T003008_20260829T003009_VVR012_INT40_G_ueF_DE75_corr.tif",
    "dem": "data/processed/dinsar/S1DD_20260817T003008_20260829T003009_VVR012_INT40_G_ueF_DE75_dem.tif",
    "slope": "data/processed/dem/moghalrajpuram_slope.tif",
}

OUTPUT_DIR = "data/processed/aoi"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------------------------------------------------
# Read AOI
# --------------------------------------------------

aoi = gpd.read_file(AOI_FILE)

print("AOI CRS:", aoi.crs)
print("AOI bounds:", aoi.total_bounds)

# --------------------------------------------------
# Clip each raster
# --------------------------------------------------

for name, input_file in INPUT_FILES.items():

    print("\nProcessing:", name)

    with rasterio.open(input_file) as src:

        # Reproject AOI to raster CRS
        aoi_projected = aoi.to_crs(src.crs)

        # Clip raster
        clipped, transform = mask(
            src,
            aoi_projected.geometry,
            crop=True
        )

        # Update metadata
        profile = src.profile.copy()

        profile.update(
            height=clipped.shape[1],
            width=clipped.shape[2],
            transform=transform
        )

        # Output filename
        output_file = os.path.join(
            OUTPUT_DIR,
            f"moghalrajpuram_{name}.tif"
        )

        # Save clipped raster
        with rasterio.open(output_file, "w", **profile) as dst:
            dst.write(clipped)

        print("Saved:", output_file)
        print("Size:", clipped.shape[2], "x", clipped.shape[1])
        print("CRS:", src.crs)
        print("Resolution:", src.res)

print("\nAOI CLIPPING COMPLETED")