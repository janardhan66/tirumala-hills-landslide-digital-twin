import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

terrain_file = PROJECT / "data" / "features" / \
    "tirumala_terrain_susceptibility.csv"

insar_file = PROJECT / "data" / "features" / \
    "tirumala_insar_monitoring_component.csv"

rainfall_file = PROJECT / "data" / "features" / \
    "tirumala_rainfall_trigger_component.csv"

output_file = PROJECT / "data" / "features" / \
    "tirumala_integrated_assessment_dataset.csv"


# --------------------------------------------------
# Read spatial components
# --------------------------------------------------

terrain = pd.read_csv(terrain_file)
insar = pd.read_csv(insar_file)

print("Terrain observations:", len(terrain))
print("InSAR observations:", len(insar))


# --------------------------------------------------
# Verify spatial alignment
# --------------------------------------------------

key_columns = ["row", "col"]

if not terrain[key_columns].equals(insar[key_columns]):
    raise ValueError(
        "Terrain and InSAR spatial grids are not aligned."
    )

print("Spatial grids: ALIGNED")


# --------------------------------------------------
# Combine terrain + InSAR
# --------------------------------------------------

df = terrain.merge(
    insar,
    on=["row", "col"],
    how="inner",
    suffixes=("", "_insar")
)

print("Integrated spatial observations:", len(df))


# --------------------------------------------------
# Add InSAR acquisition information
# --------------------------------------------------

df["insar_start_date"] = "2026-08-17"
df["insar_end_date"] = "2026-08-29"


# --------------------------------------------------
# Add event-level rainfall information
#
# These values are NOT spatially varying.
# They describe antecedent rainfall associated
# with the InSAR observation period.
# --------------------------------------------------

rainfall = pd.read_csv(rainfall_file)

start_rain = rainfall[
    rainfall["insar_date"] == "2026-08-17"
].iloc[0]

end_rain = rainfall[
    rainfall["insar_date"] == "2026-08-29"
].iloc[0]


df["rain_3d_before_start_mm"] = start_rain[
    "rain_3d_before_mm"
]

df["rain_7d_before_start_mm"] = start_rain[
    "rain_7d_before_mm"
]

df["rain_14d_before_start_mm"] = start_rain[
    "rain_14d_before_mm"
]

df["rain_3d_before_end_mm"] = end_rain[
    "rain_3d_before_mm"
]

df["rain_7d_before_end_mm"] = end_rain[
    "rain_7d_before_mm"
]

df["rain_14d_before_end_mm"] = end_rain[
    "rain_14d_before_mm"
]


# --------------------------------------------------
# Add rainfall change between acquisitions
# --------------------------------------------------

df["rain_3d_change_mm"] = (
    df["rain_3d_before_end_mm"]
    - df["rain_3d_before_start_mm"]
)

df["rain_7d_change_mm"] = (
    df["rain_7d_before_end_mm"]
    - df["rain_7d_before_start_mm"]
)

df["rain_14d_change_mm"] = (
    df["rain_14d_before_end_mm"]
    - df["rain_14d_before_start_mm"]
)


# --------------------------------------------------
# Save
# --------------------------------------------------

output_file.parent.mkdir(
    parents=True,
    exist_ok=True
)

df.to_csv(
    output_file,
    index=False
)


# --------------------------------------------------
# Summary
# --------------------------------------------------

print("\nINTEGRATED ASSESSMENT DATASET")
print("=============================")

print("Rows:", len(df))
print("Columns:", len(df.columns))

print("\nTerrain classes:")
print(
    df["terrain_class"]
    .value_counts()
    .sort_index()
)

print("\nInSAR monitoring classes:")
print(
    df["insar_monitoring_class"]
    .value_counts()
    .sort_index()
)

print("\nRainfall before 17 Aug:")
print(
    f"3-day  = {start_rain['rain_3d_before_mm']:.1f} mm"
)
print(
    f"7-day  = {start_rain['rain_7d_before_mm']:.1f} mm"
)
print(
    f"14-day = {start_rain['rain_14d_before_mm']:.1f} mm"
)

print("\nRainfall before 29 Aug:")
print(
    f"3-day  = {end_rain['rain_3d_before_mm']:.1f} mm"
)
print(
    f"7-day  = {end_rain['rain_7d_before_mm']:.1f} mm"
)
print(
    f"14-day = {end_rain['rain_14d_before_mm']:.1f} mm"
)

print("\nOutput:")
print(output_file)