import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

INVENTORY_FILE = (
    "data/raw/landslide_inventory/"
    "coolr_landslide_events.csv"
)

AOI_FILE = (
    "data/raw/aoi/"
    "moghalrajpuram_aoi.geojson"
)

# Read events
df = pd.read_csv(INVENTORY_FILE)

print("=" * 70)
print("NASA COOLR LANDSLIDE EVENTS")
print("=" * 70)

print("Total records:", len(df))

# Keep valid coordinates
df = df.dropna(
    subset=["Latitude", "Longitude"]
).copy()

print("Records with valid coordinates:", len(df))

# Convert to points
geometry = [
    Point(lon, lat)
    for lon, lat in zip(
        df["Longitude"],
        df["Latitude"]
    )
]

gdf = gpd.GeoDataFrame(
    df,
    geometry=geometry,
    crs="EPSG:4326"
)

# Read AOI
aoi = gpd.read_file(AOI_FILE)
aoi = aoi.to_crs("EPSG:4326")

# --------------------------------------------------
# Exact AOI
# --------------------------------------------------

inside = gpd.sjoin(
    gdf,
    aoi,
    predicate="within",
    how="inner"
)

print()
print("=" * 70)
print("EVENTS INSIDE EXACT AOI")
print("=" * 70)

print("Number of events inside AOI:", len(inside))

if len(inside) > 0:

    columns = [
        "Event ID",
        "Event Date",
        "Latitude",
        "Longitude",
        "Landslide Category",
        "Landslide Trigger",
        "Method",
        "Imagery Type for Digitizing",
        "Country Name"
    ]

    print()
    print(inside[columns].to_string(index=False))

    output = (
        "data/raw/landslide_inventory/"
        "moghalrajpuram_landslide_events_inside_aoi.csv"
    )

    inside.drop(
        columns="geometry"
    ).to_csv(output, index=False)

    print()
    print("Saved:", output)

else:
    print("No events found inside the exact AOI.")

# --------------------------------------------------
# 5 km buffer
# --------------------------------------------------

gdf_utm = gdf.to_crs("EPSG:32644")
aoi_utm = aoi.to_crs("EPSG:32644")

buffer = aoi_utm.buffer(5000)

buffer_gdf = gpd.GeoDataFrame(
    geometry=buffer,
    crs="EPSG:32644"
)

nearby = gpd.sjoin(
    gdf_utm,
    buffer_gdf,
    predicate="within",
    how="inner"
)

print()
print("=" * 70)
print("EVENTS WITHIN 5 KM OF AOI")
print("=" * 70)

print("Number of nearby events:", len(nearby))

if len(nearby) > 0:

    columns = [
        "Event ID",
        "Event Date",
        "Latitude",
        "Longitude",
        "Landslide Category",
        "Landslide Trigger",
        "Method",
        "Imagery Type for Digitizing",
        "Country Name"
    ]

    print()
    print(
        nearby[columns]
        .head(30)
        .to_string(index=False)
    )

print()
print("=" * 70)