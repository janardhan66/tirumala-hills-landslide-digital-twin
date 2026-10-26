import os
import geopandas as gpd
import rasterio
from rasterio.mask import mask

aoi_file = r"data\raw\aoi\tirumala_hills_aoi.geojson"
input_dir = r"data\processed\dinsar\tirumala"
output_dir = r"data\processed\dinsar\tirumala\clipped"

os.makedirs(output_dir, exist_ok=True)

aoi = gpd.read_file(aoi_file)

files = [
    "tirumala_corr_80m.tif",
    "tirumala_dem_80m.tif",
    "tirumala_los_disp_80m.tif",
]

for filename in files:
    input_file = os.path.join(input_dir, filename)
    output_file = os.path.join(output_dir, filename)

    with rasterio.open(input_file) as src:
        aoi_proj = aoi.to_crs(src.crs)

        geometries = [
            aoi_proj.geometry.iloc[0].__geo_interface__
        ]

        data, transform = mask(
            src,
            geometries,
            crop=True
        )

        metadata = src.meta.copy()
        metadata.update(
            height=data.shape[1],
            width=data.shape[2],
            transform=transform
        )

        with rasterio.open(output_file, "w", **metadata) as dst:
            dst.write(data)

        print(
            f"Created: {output_file} | "
            f"Size: {data.shape[2]} x {data.shape[1]}"
        )

print("\nClipping completed successfully.")