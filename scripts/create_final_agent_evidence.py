import pandas as pd
import numpy as np
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

spatial_file = (
    PROJECT
    / "data"
    / "features"
    / "tirumala_agent_evidence.csv"
)

temporal_file = (
    PROJECT
    / "data"
    / "features"
    / "tirumala_temporal_agent_evidence.csv"
)

output_file = (
    PROJECT
    / "data"
    / "features"
    / "tirumala_final_agent_evidence.csv"
)

spatial = pd.read_csv(spatial_file)
temporal = pd.read_csv(temporal_file)

print("\nFINAL INTELLIGENT AGENT EVIDENCE")
print("=================================")

print("Spatial observations :", len(spatial))
print("Temporal observations:", len(temporal))

# -----------------------------------------
# Keep only required temporal information
# -----------------------------------------
temporal_subset = temporal[
    [
        "row",
        "col",
        "abs_temporal_change_mm",
        "temporal_change_threshold_mm",
        "temporal_change_evidence",
        "temporal_evidence_flag",
        "temporal_change_class"
    ]
].copy()

# -----------------------------------------
# Merge on exact raster pixel coordinates
# -----------------------------------------
df = spatial.merge(
    temporal_subset,
    on=["row", "col"],
    how="left"
)

# -----------------------------------------
# Preserve temporal availability
# -----------------------------------------
df["temporal_available"] = (
    df["temporal_evidence_flag"].notna()
)

df["temporal_status"] = np.where(
    df["temporal_available"],
    "Available",
    "Unavailable"
)

# Missing temporal evidence must NOT become
# a positive or negative evidence flag.
df["temporal_evidence_flag"] = (
    df["temporal_evidence_flag"]
    .fillna(0)
    .astype(int)
)

# -----------------------------------------
# Evidence fusion
# -----------------------------------------
def classify(row):

    spatial_category = row["agent_evidence_category"]

    if spatial_category == "Terrain + InSAR evidence":

        if row["temporal_available"] and row["temporal_evidence_flag"] == 1:
            return "Multiple spatial + temporal evidence"

        return "Multiple spatial evidence"

    elif spatial_category == "InSAR monitoring evidence":

        if row["temporal_available"] and row["temporal_evidence_flag"] == 1:
            return "InSAR + temporal evidence"

        return "InSAR monitoring evidence"

    elif spatial_category == "Terrain evidence":

        if row["temporal_available"] and row["temporal_evidence_flag"] == 1:
            return "Terrain + temporal evidence"

        return "Terrain evidence"

    else:

        if row["temporal_available"] and row["temporal_evidence_flag"] == 1:
            return "Temporal-change evidence"

        return "No high spatial evidence"


df["final_agent_evidence"] = df.apply(
    classify,
    axis=1
)

# -----------------------------------------
# Save
# -----------------------------------------
df.to_csv(output_file, index=False)

print("\nFinal evidence distribution")
print("---------------------------")
print(
    df["final_agent_evidence"]
    .value_counts()
    .to_string()
)

print("\nTemporal availability")
print("---------------------")
print(
    df["temporal_status"]
    .value_counts()
    .to_string()
)

print("\nTotal final observations:", len(df))
print(
    "Temporal evidence available:",
    int(df["temporal_available"].sum())
)
print(
    "Temporal evidence unavailable:",
    int((~df["temporal_available"]).sum())
)

print("\nOutput:")
print(output_file)

print("\nFinal Intelligent Agent evidence created.")