import os
import geopandas as gpd
from shapely.geometry import Point

OUT_DIR = r"data\processed\landslide_inventory"
os.makedirs(OUT_DIR, exist_ok=True)

# Coordinates reported by GSI in Chapter 2.2
points = [
    {
        "name": "GSI Study Area NW Reference",
        "latitude": 13.691728,
        "longitude": 79.337403
    },
    {
        "name": "GSI Study Area SE Reference",
        "latitude": 13.639739,
        "longitude": 79.423392
    }
]

geometry = [
    Point(p["longitude"], p["latitude"])
    for p in points
]

gdf = gpd.GeoDataFrame(
    points,
    geometry=geometry,
    crs="EPSG:4326"
)

out_file = os.path.join(
    OUT_DIR,
    "gsi_tirumala_reference_points.geojson"
)

gdf.to_file(out_file, driver="GeoJSON")

print("=" * 70)
print("GSI TIRUMALA REFERENCE POINTS")
print("=" * 70)

print(gdf[[
    "name",
    "latitude",
    "longitude"
]].to_string(index=False))

print()
print("Saved:", out_file)