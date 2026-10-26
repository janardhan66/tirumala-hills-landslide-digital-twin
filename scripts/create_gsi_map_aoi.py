import geopandas as gpd
from shapely.geometry import Polygon

# Approximate boundary digitized from GSI Figure 3.2
# Coordinates are map-derived, not official GSI point coordinates.
coords = [
    (79.337258, 13.691948),
    (79.336453, 13.679588),
    (79.341385, 13.676779),
    (79.343096, 13.673970),
    (79.333937, 13.653745),
    (79.340479, 13.651779),
    (79.343800, 13.646442),
    (79.355374, 13.648315),
    (79.359400, 13.644757),
    (79.368257, 13.643165),
    (79.378120, 13.646629),
    (79.380032, 13.645412),
    (79.382045, 13.646723),
    (79.388889, 13.645506),
    (79.395431, 13.650281),
    (79.410930, 13.657678),
    (79.414050, 13.661610),
    (79.413748, 13.665075),
    (79.410427, 13.667697),
    (79.404992, 13.666854),
    (79.388084, 13.668727),
    (79.383756, 13.679588),
    (79.374094, 13.676030),
    (79.359903, 13.673876),
    (79.356985, 13.692697),
]

polygon = Polygon(coords)

gdf = gpd.GeoDataFrame(
    [{
        "name": "Tirumala Hills GSI Figure 3.2 AOI",
        "source": "GSI Figure 3.2",
        "coordinate_type": "map-derived approximate boundary"
    }],
    geometry=[polygon],
    crs="EPSG:4326"
)

# Save
output = "data/raw/aoi/tirumala_hills_gsi_map_aoi.geojson"
gdf.to_file(output, driver="GeoJSON")

# Calculate area in UTM Zone 44N
utm = gdf.to_crs("EPSG:32644")
area_km2 = utm.geometry.area.iloc[0] / 1e6

print("AOI created successfully.")
print(f"Area: {area_km2:.3f} km²")
print(f"Output: {output}")