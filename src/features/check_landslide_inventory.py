import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# --------------------------------------------------
# Input files
# --------------------------------------------------

INVENTORY_FILE = (
    "data/raw/landslide_inventory/"
    "coolr_landslide_reports.csv"
)

AOI_FILE = (
    "data/raw/aoi/"
    "moghalrajpuram_aoi.geojson"
)

# --------------------------------------------------
# Read landslide inventory
# --------------------------------------------------

df = pd.read_csv(INVENTORY_FILE)

print("=" * 70)
print("NASA COOLR LANDSLIDE INVENTORY")
print("=" * 70)

print("Total records:", len(df))

# --------------------------------------------------
# Keep records with valid coordinates
# --------------------------------------------------

df = df.dropna(subset=["Latitude", "Longitude"]).copy()

print("Records with valid coordinates:", len(df))

# --------------------------------------------------
# Convert to GeoDataFrame
# --------------------------------------------------

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

# --------------------------------------------------
# Read AOI
# --------------------------------------------------

aoi = gpd.read_file(AOI_FILE)

# Make sure AOI is WGS84
aoi = aoi.to_crs("EPSG:4326")

# --------------------------------------------------
# Landslides inside exact AOI
# --------------------------------------------------

inside = gpd.sjoin(
    gdf,
    aoi,
    predicate="within",
    how="inner"
)

print()
print("=" * 70)
print("RESULT: LANDSLIDES INSIDE EXACT AOI")
print("=" * 70)

print("Number of reports inside AOI:", len(inside))

if len(inside) > 0:
    print()
    print(
        inside[
            [
                "Event ID",
                "Event Date",
                "Latitude",
                "Longitude",
                "Landslide Category",
                "Landslide Trigger",
                "Location Accuracy",
                "Country Name",
                "Administrative Division"
            ]
        ].to_string(index=False)
    )

    output_file = (
        "data/raw/landslide_inventory/"
        "moghalrajpuram_landslides_inside_aoi.csv"
    )

    inside.drop(columns="geometry").to_csv(
        output_file,
        index=False
    )

    print()
    print("Saved:", output_file)

else:
    print("No documented landslide reports found inside the exact AOI.")

# --------------------------------------------------
# Check nearby reports within 5 km
# --------------------------------------------------

gdf_utm = gdf.to_crs("EPSG:32644")
aoi_utm = aoi.to_crs("EPSG:32644")

aoi_buffer = aoi_utm.buffer(5000)

nearby = gpd.sjoin(
    gdf_utm,
    gpd.GeoDataFrame(
        geometry=aoi_buffer,
        crs="EPSG:32644"
    ),
    predicate="within",
    how="inner"
)

print()
print("=" * 70)
print("RESULT: LANDSLIDES WITHIN 5 KM OF AOI")
print("=" * 70)

print("Number of nearby reports:", len(nearby))

if len(nearby) > 0:
    print()
    print(
        nearby[
            [
                "Event ID",
                "Event Date",
                "Latitude",
                "Longitude",
                "Landslide Category",
                "Landslide Trigger",
                "Location Accuracy",
                "Country Name",
                "Administrative Division"
            ]
        ].head(20).to_string(index=False)
    )

print()
print("=" * 70)