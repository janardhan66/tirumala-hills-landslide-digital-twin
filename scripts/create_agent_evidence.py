import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = PROJECT / "data" / "features" / \
    "tirumala_integrated_assessment_dataset.csv"

output_file = PROJECT / "data" / "features" / \
    "tirumala_agent_evidence.csv"


df = pd.read_csv(input_file)

print("Input observations:", len(df))


# --------------------------------------------------
# Terrain evidence
# --------------------------------------------------

df["terrain_high_evidence"] = (
    df["terrain_class"] == "High"
).astype(int)


# --------------------------------------------------
# InSAR monitoring evidence
# --------------------------------------------------

df["insar_high_evidence"] = (
    df["insar_monitoring_class"] == "High"
).astype(int)


# --------------------------------------------------
# Measurement quality
# --------------------------------------------------

df["insar_quality_acceptable"] = (
    df["correlation"] >= 0.5
).astype(int)


# --------------------------------------------------
# Rainfall event information
# --------------------------------------------------
#
# These are descriptive trigger flags only.
# No universal rainfall threshold is assumed.
# --------------------------------------------------

df["rainfall_before_start_14d"] = (
    df["rain_14d_before_start_mm"]
)

df["rainfall_before_end_14d"] = (
    df["rain_14d_before_end_mm"]
)


# --------------------------------------------------
# Evidence count
#
# Only spatial evidence is counted here.
# Rainfall remains an event-level trigger.
# --------------------------------------------------

df["spatial_evidence_count"] = (
    df["terrain_high_evidence"]
    + df["insar_high_evidence"]
)


# --------------------------------------------------
# Explainable evidence category
# --------------------------------------------------

def classify_evidence(row):

    terrain = row["terrain_high_evidence"]
    insar = row["insar_high_evidence"]

    if terrain == 1 and insar == 1:
        return "Terrain + InSAR evidence"

    elif terrain == 1:
        return "Terrain evidence"

    elif insar == 1:
        return "InSAR monitoring evidence"

    else:
        return "No high spatial evidence"


df["agent_evidence_category"] = df.apply(
    classify_evidence,
    axis=1
)


# --------------------------------------------------
# Agent explanation
# --------------------------------------------------

def generate_explanation(row):

    reasons = []

    if row["terrain_high_evidence"] == 1:
        reasons.append(
            "relatively high terrain indicator"
        )

    if row["insar_high_evidence"] == 1:
        reasons.append(
            "relatively high LOS displacement magnitude"
        )

    if row["insar_quality_acceptable"] == 0:
        reasons.append(
            "InSAR correlation below quality threshold"
        )

    if not reasons:
        return "No high spatial evidence identified"

    return "; ".join(reasons)


df["agent_explanation"] = df.apply(
    generate_explanation,
    axis=1
)


# --------------------------------------------------
# Save
# --------------------------------------------------

columns = [
    "row",
    "col",
    "elevation_m",
    "slope_deg",
    "terrain_class",
    "terrain_high_evidence",
    "los_disp_m",
    "los_abs_m",
    "correlation",
    "insar_monitoring_class",
    "insar_high_evidence",
    "insar_quality_acceptable",
    "rain_3d_before_start_mm",
    "rain_7d_before_start_mm",
    "rain_14d_before_start_mm",
    "rain_3d_before_end_mm",
    "rain_7d_before_end_mm",
    "rain_14d_before_end_mm",
    "spatial_evidence_count",
    "agent_evidence_category",
    "agent_explanation"
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

print("\nAGENT EVIDENCE SUMMARY")
print("======================")

print("\nTerrain high evidence:")
print(
    result["terrain_high_evidence"].sum()
)

print("\nInSAR high evidence:")
print(
    result["insar_high_evidence"].sum()
)

print("\nBoth terrain + InSAR:")
print(
    (
        (result["terrain_high_evidence"] == 1)
        &
        (result["insar_high_evidence"] == 1)
    ).sum()
)

print("\nEvidence categories:")
print(
    result["agent_evidence_category"]
    .value_counts()
)

print("\nOutput:")
print(output_file)