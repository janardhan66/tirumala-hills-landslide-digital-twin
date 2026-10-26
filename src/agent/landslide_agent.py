import pandas as pd
from pathlib import Path


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

INPUT_FILE = Path(
    "data/digital_twin/moghalrajpuram_digital_twin_state.csv"
)

OUTPUT_DIR = Path(
    "outputs/reports"
)

OUTPUT_FILE = OUTPUT_DIR / (
    "moghalrajpuram_agent_assessment.csv"
)


# ---------------------------------------------------------
# Load Digital Twin
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

print(f"Digital Twin records: {len(df)}")


# ---------------------------------------------------------
# Create output directory
# ---------------------------------------------------------

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ---------------------------------------------------------
# Intelligent Agent decision function
# ---------------------------------------------------------

def agent_decision(row):

    risk = row["risk_category"]
    confidence = row["insar_confidence"]

    # Very High Risk
    if risk == "Very High":

        if confidence == "High Confidence":
            return (
                "Immediate attention",
                "High-priority monitoring and field verification"
            )

        else:
            return (
                "Priority review",
                "Recheck InSAR evidence and conduct field verification"
            )

    # High Risk
    elif risk == "High":

        return (
            "Enhanced monitoring",
            "Monitor deformation and terrain conditions closely"
        )

    # Moderate Risk
    elif risk == "Moderate":

        return (
            "Routine monitoring",
            "Continue periodic remote sensing monitoring"
        )

    # Low Risk
    else:

        return (
            "Normal monitoring",
            "No immediate action required"
        )
# ---------------------------------------------------------
# Apply agent decisions
# ---------------------------------------------------------

decisions = df.apply(
    agent_decision,
    axis=1
)


df["agent_action"] = [
    decision[0]
    for decision in decisions
]

df["agent_recommendation"] = [
    decision[1]
    for decision in decisions
]


# ---------------------------------------------------------
# Agent reasoning
# ---------------------------------------------------------

def generate_reason(row):

    return (
        f"Risk={row['risk_category']}; "
        f"Risk Score={row['risk_score']}; "
        f"Slope={row['slope_deg']:.2f} deg; "
        f"LOS displacement={row['los_displacement_m']:.4f} m; "
        f"InSAR confidence={row['insar_confidence']}"
    )


df["agent_reason"] = df.apply(
    generate_reason,
    axis=1
)


# ---------------------------------------------------------
# Save agent assessment
# ---------------------------------------------------------

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ---------------------------------------------------------
# Display summary
# ---------------------------------------------------------

print()
print("Intelligent Agent assessment completed.")

print(f"Output: {OUTPUT_FILE}")

print()
print("Agent action distribution:")

print(
    df["agent_action"]
    .value_counts()
    .to_string()
)


print()
print("Sample agent decisions:")

print(
    df[
        [
            "twin_id",
            "risk_category",
            "risk_score",
            "insar_confidence",
            "agent_action",
            "agent_recommendation"
        ]
    ]
    .head(10)
    .to_string(index=False)
)
# ---------------------------------------------------------
# U-Net Segmentation Evidence for Intelligent Agent
# ---------------------------------------------------------

import os
import numpy as np
import pandas as pd


SEGMENTATION_DIR = (
    "outputs"
    "\\segmentation"
    "\\upload_test"
)

PROBABILITY_FILE = os.path.join(
    SEGMENTATION_DIR,
    "landslide_probability.npy"
)

MASK_FILE = os.path.join(
    SEGMENTATION_DIR,
    "landslide_mask.npy"
)


def segmentation_agent_decision(
    landslide_percentage,
    average_confidence
):

    if landslide_percentage >= 10 and average_confidence >= 0.80:

        return (
            "Immediate attention",
            "High landslide segmentation evidence; "
            "prioritize review and field verification"
        )

    elif landslide_percentage >= 5 and average_confidence >= 0.70:

        return (
            "Enhanced monitoring",
            "Significant landslide segmentation evidence; "
            "perform enhanced monitoring and expert review"
        )

    elif landslide_percentage >= 1:

        return (
            "Priority review",
            "Detected landslide evidence requires "
            "additional remote sensing and expert review"
        )

    else:

        return (
            "Normal monitoring",
            "Low detected landslide extent; "
            "continue routine monitoring"
        )


if os.path.exists(PROBABILITY_FILE) and os.path.exists(MASK_FILE):

    probability = np.load(PROBABILITY_FILE)
    mask = np.load(MASK_FILE)

    total_pixels = mask.size

    landslide_pixels = int(mask.sum())

    landslide_percentage = (
        landslide_pixels / total_pixels
    ) * 100

    if landslide_pixels > 0:

        average_confidence = float(
            probability[mask == 1].mean()
        )

    else:

        average_confidence = 0.0

    action, recommendation = segmentation_agent_decision(
        landslide_percentage,
        average_confidence
    )

    segmentation_result = pd.DataFrame(
        [{
            "input_type": "Landslide4Sense uploaded image",
            "total_pixels": total_pixels,
            "predicted_landslide_pixels": landslide_pixels,
            "predicted_landslide_percentage": landslide_percentage,
            "average_confidence": average_confidence,
            "agent_action": action,
            "agent_recommendation": recommendation
        }]
    )

    output_file = (
        "outputs"
        "\\reports"
        "\\segmentation_agent_assessment.csv"
    )

    segmentation_result.to_csv(
        output_file,
        index=False
    )

    print()
    print("U-Net Segmentation Agent Assessment")
    print("-----------------------------------")
    print(
        f"Predicted landslide pixels: "
        f"{landslide_pixels}"
    )
    print(
        f"Predicted landslide area: "
        f"{landslide_percentage:.2f}%"
    )
    print(
        f"Average confidence: "
        f"{average_confidence * 100:.2f}%"
    )
    print(f"Agent action: {action}")
    print(f"Recommendation: {recommendation}")
    print(
        f"Output: {output_file}"
    )