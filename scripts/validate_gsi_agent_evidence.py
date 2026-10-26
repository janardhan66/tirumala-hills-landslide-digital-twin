import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.transform import xy
from pyproj import Transformer
from pathlib import Path
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]

agent_file = (
    PROJECT
    / "data"
    / "features"
    / "tirumala_final_agent_evidence.csv"
)

gsi_file = (
    PROJECT
    / "data"
    / "features"
    / "tirumala_gsi_validation_table.csv"
)

reference_raster = (
    PROJECT
    / "data"
    / "processed"
    / "dinsar"
    / "tirumala"
    / "gsi_aoi"
    / "tirumala_temporal_los_change_05_17_to_17_29.tif"
)

output_dir = PROJECT / "results" / "validation"
output_dir.mkdir(parents=True, exist_ok=True)

output_file = (
    output_dir
    / "gsi_agent_spatial_validation.csv"
)

print("\nGSI vs INTELLIGENT AGENT VALIDATION")
print("====================================")

# ------------------------------------------------
# Load datasets
# ------------------------------------------------

agent = pd.read_csv(agent_file)
gsi = pd.read_csv(gsi_file)

print("Agent observations:", len(agent))
print("GSI historical locations:", len(gsi))

# ------------------------------------------------
# Convert agent raster row/column to coordinates
# ------------------------------------------------

with rasterio.open(reference_raster) as src:

    transform = src.transform
    raster_crs = src.crs

    print("Reference raster CRS:", raster_crs)
    print("Reference raster shape:", src.height, "x", src.width)

    transformer = Transformer.from_crs(
        raster_crs,
        "EPSG:4326",
        always_xy=True
    )

    agent_lats = []
    agent_lons = []

    for _, row in agent.iterrows():

        raster_row = int(row["row"])
        raster_col = int(row["col"])

        x, y = xy(
            transform,
            raster_row,
            raster_col,
            offset="center"
        )

        lon, lat = transformer.transform(x, y)

        agent_lats.append(lat)
        agent_lons.append(lon)

agent["latitude"] = agent_lats
agent["longitude"] = agent_lons

# ------------------------------------------------
# Convert both datasets to projected CRS
# ------------------------------------------------

agent_gdf = gpd.GeoDataFrame(
    agent,
    geometry=gpd.points_from_xy(
        agent["longitude"],
        agent["latitude"]
    ),
    crs="EPSG:4326"
)

gsi_gdf = gpd.GeoDataFrame(
    gsi,
    geometry=gpd.points_from_xy(
        gsi["longitude"],
        gsi["latitude"]
    ),
    crs="EPSG:4326"
)

agent_gdf = agent_gdf.to_crs("EPSG:32644")
gsi_gdf = gsi_gdf.to_crs("EPSG:32644")

# ------------------------------------------------
# Validation radii
# ------------------------------------------------
#
# GSI coordinates are approximate.
# We therefore evaluate several spatial
# proximity windows instead of using one
# exact-match threshold.
#
# 160 m = 2 x 80 m pixels
# 320 m = 4 x 80 m pixels
# 500 m = broader sensitivity check
# ------------------------------------------------

radii = [160, 320, 500]

results = []

for _, gsi_row in gsi_gdf.iterrows():

    gsi_id = gsi_row["inventory_id"]
    gsi_point = gsi_row.geometry

    distances = agent_gdf.geometry.distance(gsi_point)

    result = {
        "inventory_id": gsi_id,
        "latitude": gsi_row["latitude"],
        "longitude": gsi_row["longitude"],
        "coordinate_quality": gsi_row["coordinate_quality"],
        "terrain_available_at_gsi": gsi_row["terrain_available"],
        "insar_quality_pass_at_gsi": gsi_row["insar_quality_pass"],
        "los_available_at_gsi": gsi_row["los_available"],
    }

    # --------------------------------------------
    # Nearest agent observation
    # --------------------------------------------

    nearest_idx = distances.idxmin()
    nearest_distance = distances.loc[nearest_idx]

    nearest_agent = agent_gdf.loc[nearest_idx]

    result["nearest_agent_distance_m"] = nearest_distance
    result["nearest_agent_category"] = (
        nearest_agent["final_agent_evidence"]
    )

    result["nearest_agent_slope_deg"] = (
        nearest_agent["slope_deg"]
    )

    result["nearest_agent_los_abs_m"] = (
        nearest_agent["los_abs_m"]
    )

    result["nearest_agent_temporal_change_mm"] = (
        nearest_agent["abs_temporal_change_mm"]
    )

    # --------------------------------------------
    # Proximity analysis
    # --------------------------------------------

    for radius in radii:

        nearby = agent_gdf.loc[
            distances <= radius
        ].copy()

        count = len(nearby)

        result[f"agent_cells_within_{radius}m"] = count

        if count == 0:

            result[
                f"supporting_evidence_within_{radius}m"
            ] = False

            result[
                f"dominant_category_within_{radius}m"
            ] = "No nearby agent observation"

        else:

            # Evidence categories excluding
            # the generic no-high-evidence class
            supporting = nearby[
                nearby["final_agent_evidence"]
                != "No high spatial evidence"
            ]

            result[
                f"supporting_evidence_within_{radius}m"
            ] = len(supporting) > 0

            if len(supporting) == 0:

                result[
                    f"dominant_category_within_{radius}m"
                ] = "No high spatial evidence"

            else:

                category_counts = (
                    supporting["final_agent_evidence"]
                    .value_counts()
                )

                result[
                    f"dominant_category_within_{radius}m"
                ] = category_counts.index[0]

                result[
                    f"supporting_cells_within_{radius}m"
                ] = len(supporting)

    results.append(result)

# ------------------------------------------------
# Fill missing supporting-cell counts
# ------------------------------------------------

validation = pd.DataFrame(results)

for radius in radii:

    column = f"supporting_cells_within_{radius}m"

    if column not in validation.columns:
        validation[column] = 0

    validation[column] = (
        validation[column]
        .fillna(0)
        .astype(int)
    )

# ------------------------------------------------
# Overall summary columns
# ------------------------------------------------

validation["support_160m"] = (
    validation["supporting_evidence_within_160m"]
)

validation["support_320m"] = (
    validation["supporting_evidence_within_320m"]
)

validation["support_500m"] = (
    validation["supporting_evidence_within_500m"]
)

# ------------------------------------------------
# Save
# ------------------------------------------------

validation.to_csv(
    output_file,
    index=False
)

# ------------------------------------------------
# Summary
# ------------------------------------------------

print("\nVALIDATION SUMMARY")
print("------------------")

print(
    "Historical locations:",
    len(validation)
)

print(
    "Supporting evidence within 160 m:",
    int(validation["support_160m"].sum()),
    "/",
    len(validation)
)

print(
    "Supporting evidence within 320 m:",
    int(validation["support_320m"].sum()),
    "/",
    len(validation)
)

print(
    "Supporting evidence within 500 m:",
    int(validation["support_500m"].sum()),
    "/",
    len(validation)
)

print("\nNearest-agent distance:")
print(
    validation["nearest_agent_distance_m"]
    .describe()
    .to_string()
)

print("\nValidation table:")
print(
    validation[
        [
            "inventory_id",
            "nearest_agent_distance_m",
            "nearest_agent_category",
            "support_160m",
            "support_320m",
            "support_500m"
        ]
    ].to_string(index=False)
)

print("\nOutput:")
print(output_file)