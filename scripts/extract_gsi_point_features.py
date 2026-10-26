import pandas as pd
import geopandas as gpd
import rasterio
from pathlib import Path
from pyproj import Transformer

# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT = Path(__file__).resolve().parents[1]

inventory_file = PROJECT / "data" / "raw" / "inventory" / \
    "tirumala_gsi_fig32_map_derived_inventory.csv"

aoi_file = PROJECT / "data" / "raw" / "aoi" / \
    "tirumala_hills_gsi_map_aoi.geojson"

dem_file = PROJECT / "data" / "processed" / "dinsar" / "tirumala" / \
    "gsi_aoi" / "tirumala_dem_80m_gsi_aoi.tif"

slope_file = PROJECT / "data" / "processed" / "dinsar" / "tirumala" / \
    "gsi_aoi" / "tirumala_slope_80m_gsi_aoi.tif"

corr_file = PROJECT / "data" / "processed" / "dinsar" / "tirumala" / \
    "gsi_aoi" / "tirumala_corr_80m_gsi_aoi.tif"

los_file = PROJECT / "data" / "processed" / "dinsar" / "tirumala" / \
    "gsi_aoi" / "tirumala_masked_los_disp_80m_gsi_aoi.tif"

output_file = PROJECT / "data" / "features" / \
    "tirumala_gsi_inventory_features.csv"

# --------------------------------------------------
# Read inventory
# --------------------------------------------------

df = pd.read_csv(inventory_file)

print("Inventory points:", len(df))

# Convert geographic coordinates to GeoDataFrame
gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(
        df["longitude"],
        df["latitude"]
    ),
    crs="EPSG:4326"
)

# --------------------------------------------------
# Transform WGS84 coordinates to raster CRS
# --------------------------------------------------

with rasterio.open(dem_file) as src:
    raster_crs = src.crs

print("Raster CRS:", raster_crs)

gdf_utm = gdf.to_crs(raster_crs)

# --------------------------------------------------
# Function to extract raster value
# --------------------------------------------------

def extract_values(raster_path, points):
    values = []

    with rasterio.open(raster_path) as src:

        for point in points.geometry:

            try:
                row, col = src.index(point.x, point.y)

                if (
                    row < 0 or row >= src.height or
                    col < 0 or col >= src.width
                ):
                    values.append(float("nan"))
                    continue

                value = src.read(1)[row, col]

                if src.nodata is not None and value == src.nodata:
                    values.append(float("nan"))
                else:
                    values.append(float(value))

            except Exception:
                values.append(float("nan"))

    return values


# --------------------------------------------------
# Extract terrain and InSAR values
# --------------------------------------------------

gdf_utm["elevation_m"] = extract_values(
    dem_file,
    gdf_utm
)

gdf_utm["slope_deg"] = extract_values(
    slope_file,
    gdf_utm
)

gdf_utm["correlation"] = extract_values(
    corr_file,
    gdf_utm
)

gdf_utm["los_disp_m"] = extract_values(
    los_file,
    gdf_utm
)

gdf_utm["los_abs_m"] = gdf_utm["los_disp_m"].abs()

# --------------------------------------------------
# Return geographic coordinates
# --------------------------------------------------

gdf_utm = gdf_utm.to_crs("EPSG:4326")

# Remove geometry before saving CSV
result = pd.DataFrame(gdf_utm.drop(columns="geometry"))

# --------------------------------------------------
# Save
# --------------------------------------------------

output_file.parent.mkdir(parents=True, exist_ok=True)

result.to_csv(output_file, index=False)

# --------------------------------------------------
# Summary
# --------------------------------------------------

print("\nExtraction completed.")
print("Output:", output_file)
print("Rows:", len(result))
print("Columns:", len(result.columns))

print("\nMissing values:")
print(result[
    [
        "elevation_m",
        "slope_deg",
        "correlation",
        "los_disp_m"
    ]
].isna().sum())

print("\nExtracted feature table:")
print(
    result[
        [
            "inventory_id",
            "latitude",
            "longitude",
            "elevation_m",
            "slope_deg",
            "correlation",
            "los_disp_m",
            "los_abs_m"
        ]
    ].round(4).to_string(index=False)
)