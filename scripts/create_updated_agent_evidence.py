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
    / "tirumala_updated_agent_evidence.csv"
)

spatial = pd.read_csv(spatial_file)
temporal = pd.read_csv(temporal_file)

print("\nUPDATED INTELLIGENT AGENT EVIDENCE")
print("===================================")

print("Spatial observations :", len(spatial))
print("Temporal observations:", len(temporal))

# ------------------------------------------------
# Merge using raster row/column location
# ------------------------------------------------
if not {"row", "col"}.issubset(temporal.columns):
    raise ValueError("Temporal dataset does not contain row/col.")

if not {"row", "col"}.issubset(spatial.columns):
    raise ValueError(
        "Spatial agent dataset does not contain row/col. "
        "Do not continue without a common spatial key."
    )

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

df = spatial.merge(
    temporal_subset,
    on=["row", "col"],
    how="left"
)

# ------------------------------------------------
# Temporal evidence availability
# ------------------------------------------------
df["temporal_available"] = (
    df["temporal_evidence_flag"].notna()
)

df["temporal_evidence_flag"] = (
    df["temporal_evidence_flag"]
    .fillna(0)
    .astype(int)
)

# IMPORTANT:
# Missing temporal data is NOT the same as
# "lower temporal evidence".
df["temporal_status"] = np.where(
    df["temporal_available"],
    "Available",
    "Unavailable"
)

# ------------------------------------------------
# Existing spatial evidence
# ------------------------------------------------
if "agent_evidence_category" not in df.columns:
    raise ValueError(
        "Expected 'agent_evidence_category' in spatial agent dataset."
    )

# ------------------------------------------------
# Updated evidence fusion
# ------------------------------------------------
def classify(row):

    spatial_category = row["agent_evidence_category"]
    temporal_available = row["temporal_available"]
    temporal_flag = row["temporal_evidence_flag"]

    if spatial_category == "Terrain + InSAR evidence":
        if temporal_available and temporal_flag == 1:
            return "Multiple spatial + temporal evidence"
        return "Multiple spatial evidence"

    if spatial_category == "InSAR monitoring evidence":
        if temporal_available and temporal_flag == 1:
            return "InSAR + temporal evidence"
        return "InSAR monitoring evidence"

    if spatial_category == "Terrain evidence":
        if temporal_available and temporal_flag == 1:
            return "Terrain + temporal evidence"
        return "Terrain evidence"

    # No high spatial evidence
    if temporal_available and temporal_flag == 1:
        return "Temporal-change evidence"

    return "No high spatial evidence"


df["updated_agent_evidence"] = df.apply(
    classify,
    axis=1
)

# ------------------------------------------------
# Save
# ------------------------------------------------
df.to_csv(output_file, index=False)

print("\nUpdated evidence distribution:")
print(
    df["updated_agent_evidence"]
    .value_counts()
    .to_string()
)

print("\nTemporal availability:")
print(
    df["temporal_status"]
    .value_counts()
    .to_string()
)

print("\nTemporal evidence available:",
      int(df["temporal_available"].sum()))

print("Temporal evidence unavailable:",
      int((~df["temporal_available"]).sum()))

print("\nOutput:")
print(output_file)

print("\nUpdated Intelligent Agent evidence created.")