import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = PROJECT / "data" / "features" / \
    "tirumala_gsi_inventory_features.csv"

output_file = PROJECT / "data" / "features" / \
    "tirumala_gsi_validation_table.csv"

df = pd.read_csv(input_file)

# --------------------------------------------------
# Quality flags
# --------------------------------------------------

df["terrain_available"] = (
    df["elevation_m"].notna()
    & df["slope_deg"].notna()
)

df["insar_quality_pass"] = (
    df["correlation"] >= 0.5
)

df["los_available"] = (
    df["los_disp_m"].notna()
)

# Overall status
def classify(row):

    if not row["terrain_available"]:
        return "Terrain data unavailable"

    if not row["los_available"]:
        return "Terrain valid; InSAR quality insufficient"

    return "Terrain and InSAR available"


df["data_status"] = df.apply(classify, axis=1)

# --------------------------------------------------
# Save
# --------------------------------------------------

output_file.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(output_file, index=False)

# --------------------------------------------------
# Report
# --------------------------------------------------

print("\nGSI VALIDATION TABLE")
print("====================")

print("Total GSI map-derived points:", len(df))
print(
    "Terrain available:",
    int(df["terrain_available"].sum())
)
print(
    "InSAR LOS available:",
    int(df["los_available"].sum())
)
print(
    "InSAR quality >= 0.5:",
    int(df["insar_quality_pass"].sum())
)

print("\nData-status summary:")
print(df["data_status"].value_counts())

print("\nFinal table:")
print(
    df[
        [
            "inventory_id",
            "latitude",
            "longitude",
            "elevation_m",
            "slope_deg",
            "correlation",
            "los_disp_m",
            "los_abs_m",
            "terrain_available",
            "insar_quality_pass",
            "los_available",
            "data_status"
        ]
    ].round(4).to_string(index=False)
)

print("\nOutput:")
print(output_file)