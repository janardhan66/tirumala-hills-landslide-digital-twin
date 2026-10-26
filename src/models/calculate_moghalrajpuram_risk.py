import pandas as pd
import numpy as np
from pathlib import Path


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

INPUT_FILE = Path(
    "data/features/moghalrajpuram_integrated_features.csv"
)

OUTPUT_FILE = Path(
    "data/features/moghalrajpuram_risk_assessment.csv"
)


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

print(f"Input rows: {len(df)}")


# ---------------------------------------------------------
# Main variables
# ---------------------------------------------------------

slope = df["slope_deg"]
abs_los = df["los_displacement_m"].abs()
coherence = df["coherence"]


# ---------------------------------------------------------
# Data-driven thresholds
# ---------------------------------------------------------

slope_p50 = slope.quantile(0.50)
slope_p75 = slope.quantile(0.75)

los_p50 = abs_los.quantile(0.50)
los_p75 = abs_los.quantile(0.75)


print()
print("Data-driven thresholds:")
print(f"Slope P50: {slope_p50:.4f} degrees")
print(f"Slope P75: {slope_p75:.4f} degrees")
print(f"|LOS displacement| P50: {los_p50:.6f} m")
print(f"|LOS displacement| P75: {los_p75:.6f} m")


# ---------------------------------------------------------
# Terrain evidence score
#
# Low      = 0
# Moderate = 50
# High     = 100
# ---------------------------------------------------------

terrain_score = np.select(
    [
        slope < slope_p50,
        slope < slope_p75
    ],
    [
        0,
        50
    ],
    default=100
)


# ---------------------------------------------------------
# Deformation evidence score
#
# Low      = 0
# Moderate = 50
# High     = 100
# ---------------------------------------------------------

deformation_score = np.select(
    [
        abs_los < los_p50,
        abs_los < los_p75
    ],
    [
        0,
        50
    ],
    default=100
)


# ---------------------------------------------------------
# Combined risk score
#
# Terrain       = 50%
# Deformation   = 50%
#
# Coherence is NOT included as hazard.
# ---------------------------------------------------------

risk_score = pd.Series(
    0.50 * terrain_score
    + 0.50 * deformation_score,
    index=df.index
)
# ---------------------------------------------------------
# Risk category
# ---------------------------------------------------------

def classify_risk(score):

    if score == 0:
        return "Low"

    elif score == 25:
        return "Moderate"

    elif score == 50:
        return "High"

    else:
        return "Very High"


risk_category = risk_score.apply(classify_risk)


# ---------------------------------------------------------
# Coherence quality
# ---------------------------------------------------------

def classify_coherence(value):

    if value < 0.5:
        return "Moderate Confidence"

    elif value < 0.7:
        return "Good Confidence"

    else:
        return "High Confidence"


confidence = coherence.apply(classify_coherence)


# ---------------------------------------------------------
# Evidence type
# ---------------------------------------------------------

# ---------------------------------------------------------
# Add scores to dataframe BEFORE evidence classification
# ---------------------------------------------------------

df["terrain_score"] = terrain_score
df["deformation_score"] = deformation_score
df["risk_score"] = risk_score


# ---------------------------------------------------------
# Evidence type
# ---------------------------------------------------------

def evidence_type(row):

    terrain_high = row["terrain_score"] == 100
    deformation_high = row["deformation_score"] == 100

    if terrain_high and deformation_high:
        return "High Terrain + High Deformation"

    elif terrain_high:
        return "High Terrain"

    elif deformation_high:
        return "High Deformation"

    elif row["terrain_score"] == 50 and row["deformation_score"] == 50:
        return "Moderate Terrain + Moderate Deformation"

    else:
        return "Lower Combined Evidence"


evidence = df.apply(evidence_type, axis=1)

# ---------------------------------------------------------
# Add results
# ---------------------------------------------------------

df["terrain_score"] = terrain_score
df["deformation_score"] = deformation_score
df["risk_score"] = risk_score
df["risk_category"] = risk_category
df["insar_confidence"] = confidence
df["evidence_type"] = evidence


# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

df.to_csv(OUTPUT_FILE, index=False)


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

print()
print("Risk assessment completed.")
print(f"Output: {OUTPUT_FILE}")

print()
print("Risk category distribution:")
print(
    df["risk_category"]
    .value_counts()
    .reindex(
        ["Low", "Moderate", "High", "Very High"],
        fill_value=0
    )
    .to_string()
)

print()
print("Risk score distribution:")
print(
    df["risk_score"]
    .value_counts()
    .sort_index()
    .to_string()
)

print()
print("InSAR confidence distribution:")
print(
    df["insar_confidence"]
    .value_counts()
    .to_string()
)

print()
print("Evidence distribution:")
print(
    df["evidence_type"]
    .value_counts()
    .to_string()
)

print()
print("Top 10 highest-risk pixels:")

print(
    df.nlargest(10, "risk_score")[
        [
            "pixel_id",
            "latitude",
            "longitude",
            "elevation_m",
            "slope_deg",
            "los_displacement_m",
            "coherence",
            "terrain_score",
            "deformation_score",
            "risk_score",
            "risk_category",
            "insar_confidence",
            "evidence_type",
        ]
    ].to_string(index=False)
)