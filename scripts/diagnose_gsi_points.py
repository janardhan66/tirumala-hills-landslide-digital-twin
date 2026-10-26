import pandas as pd
import geopandas as gpd
import rasterio
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

inventory_file = PROJECT / "data" / "raw" / "inventory" / \
    "tirumala_gsi_fig32_map_derived_inventory.csv"

aoi_file = PROJECT / "data" / "raw" / "aoi" / \
    "tirumala_hills_gsi_map_aoi.geojson"

dem_file = PROJECT / "data" / "processed" / "dinsar" / "tirumala" / \
    "gsi_aoi" / "tirumala_dem_80m_gsi_aoi.tif"

df = pd.read_csv(inventory_file)

gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(
        df["longitude"],
        df["latitude"]
    ),
    crs="EPSG:4326"
)

aoi = gpd.read_file(aoi_file)

gdf_utm = gdf.to_crs("EPSG:32644")
aoi_utm = aoi.to_crs("EPSG:32644")

with rasterio.open(dem_file) as src:

    print("Raster bounds:")
    print(src.bounds)

    print("\nRaster shape:")
    print(src.height, src.width)

    print("\nPoint diagnostics:")
    
    for _, point in gdf_utm.iterrows():

        inside_aoi = aoi_utm.geometry.contains(point.geometry).any()

        try:
            row, col = src.index(
                point.geometry.x,
                point.geometry.y
            )

            inside_raster = (
                0 <= row < src.height and
                0 <= col < src.width
            )

            if inside_raster:
                value = src.read(1)[row, col]
                is_nodata = (
                    src.nodata is not None
                    and value == src.nodata
                )
            else:
                value = None
                is_nodata = True

        except Exception:
            row = col = None
            value = None
            inside_raster = False
            is_nodata = True

        print(
            f"{point['inventory_id']}: "
            f"AOI={inside_aoi}, "
            f"Raster={inside_raster}, "
            f"row={row}, col={col}, "
            f"DEM={value}, "
            f"nodata={is_nodata}"
        )