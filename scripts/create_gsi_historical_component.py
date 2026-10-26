import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = PROJECT / "data" / "features" / \
    "tirumala_gsi_validation_table.csv"

output_file = PROJECT / "data" / "features" / \
    "tirumala_gsi_historical_component.csv"

df = pd.read_csv(input_file)

print("GSI Figure 3.2 points:", len(df))


# --------------------------------------------------
# Historical evidence
# --------------------------------------------------
#
# These locations represent approximate landslide
# incidence locations extracted from GSI Figure 3.2.
#
# They are evidence locations, NOT a complete
# spatial landslide inventory.
# --------------------------------------------------

df["historical_landslide_evidence"] = 1

df["evidence_source"] = "GSI Figure 3.2"

df["coordinate_quality"] = "Map-derived approximate"


# --------------------------------------------------
# Preserve data availability information
# --------------------------------------------------

df["terrain_available"] = (
    df["elevation_m"].notna()
    & df["slope_deg"].notna()
)

df["insar_available"] = (
    df["los_disp_m"].notna()
)


# --------------------------------------------------
# Select output columns
# --------------------------------------------------

columns = [
    "inventory_id",
    "latitude",
    "longitude",
    "elevation_m",
    "slope_deg",
    "correlation",
    "los_disp_m",
    "terrain_available",
    "insar_available",
    "historical_landslide_evidence",
    "evidence_source",
    "coordinate_quality"
]

result = df[columns].copy()

output_file.parent.mkdir(
    parents=True,
    exist_ok=True
)

result.to_csv(
    output_file,
    index=False
)


# --------------------------------------------------
# Summary
# --------------------------------------------------

print("\nGSI HISTORICAL EVIDENCE")
print("=======================")

print(
    "Total Figure 3.2 points:",
    len(result)
)

print(
    "Terrain available:",
    result["terrain_available"].sum()
)

print(
    "InSAR available:",
    result["insar_available"].sum()
)

print(
    "Historical evidence points:",
    result["historical_landslide_evidence"].sum()
)

print("\nOutput:")
print(output_file)