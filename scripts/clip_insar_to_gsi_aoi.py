import os
import geopandas as gpd
import rasterio
from rasterio.mask import mask

# --------------------------------------------------
# Paths
# --------------------------------------------------
aoi_file = "data/raw/aoi/tirumala_hills_gsi_map_aoi.geojson"
input_dir = "data/processed/dinsar/tirumala"
output_dir = "data/processed/dinsar/tirumala/gsi_aoi"

os.makedirs(output_dir, exist_ok=True)

# --------------------------------------------------
# Read AOI
# --------------------------------------------------
aoi = gpd.read_file(aoi_file)

print("AOI CRS:", aoi.crs)
print("AOI geometry:", aoi.geometry.geom_type.tolist())

# --------------------------------------------------
# Input rasters
# --------------------------------------------------
rasters = {
    "corr": "tirumala_corr_80m.tif",
    "dem": "tirumala_dem_80m.tif",
    "los_disp": "tirumala_los_disp_80m.tif",
}

# --------------------------------------------------
# Clip each raster
# --------------------------------------------------
for name, filename in rasters.items():

    input_path = os.path.join(input_dir, filename)
    output_path = os.path.join(
        output_dir,
        f"tirumala_{name}_80m_gsi_aoi.tif"
    )

    print(f"\nProcessing: {filename}")

    with rasterio.open(input_path) as src:

        # Reproject AOI to raster CRS
        aoi_raster_crs = aoi.to_crs(src.crs)

        # Clip
        clipped, transform = mask(
            src,
            aoi_raster_crs.geometry,
            crop=True,
            nodata=0
        )

        # Update metadata
        metadata = src.meta.copy()
        metadata.update({
            "height": clipped.shape[1],
            "width": clipped.shape[2],
            "transform": transform,
            "nodata": 0
        })

        # Save
        with rasterio.open(output_path, "w", **metadata) as dst:
            dst.write(clipped)

    print(f"Saved: {output_path}")

print("\nAll rasters clipped successfully.")