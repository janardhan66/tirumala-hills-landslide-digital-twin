import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = PROJECT / "data" / "features" / \
    "tirumala_agent_evidence.csv"

output_file = PROJECT / "results" / "agent" / \
    "tirumala_agent_monitoring_report.csv"


df = pd.read_csv(input_file)


# --------------------------------------------------
# Agent monitoring status
# --------------------------------------------------

def determine_status(row):

    terrain = row["terrain_high_evidence"]
    insar = row["insar_high_evidence"]
    quality = row["insar_quality_acceptable"]

    if terrain == 1 and insar == 1 and quality == 1:
        return "Multiple spatial evidence"

    elif terrain == 1 and quality == 1:
        return "Terrain-dominant evidence"

    elif insar == 1 and quality == 1:
        return "InSAR-dominant evidence"

    elif terrain == 1:
        return "Terrain evidence; InSAR quality limited"

    elif insar == 1:
        return "InSAR evidence; quality requires review"

    else:
        return "No high spatial evidence"


df["agent_monitoring_status"] = df.apply(
    determine_status,
    axis=1
)


# --------------------------------------------------
# Agent recommendation
# --------------------------------------------------

def generate_recommendation(row):

    status = row["agent_monitoring_status"]

    if status == "Multiple spatial evidence":
        return (
            "Prioritize this location for further "
            "monitoring and validation."
        )

    elif status == "Terrain-dominant evidence":
        return (
            "Terrain conditions warrant monitoring; "
            "additional InSAR observations are needed."
        )

    elif status == "InSAR-dominant evidence":
        return (
            "Review InSAR displacement evidence and "
            "obtain additional temporal observations."
        )

    elif "quality limited" in status:
        return (
            "Terrain evidence is present, but the "
            "InSAR measurement quality is insufficient "
            "for this observation."
        )

    elif "quality requires review" in status:
        return (
            "Review InSAR correlation before interpreting "
            "the displacement measurement."
        )

    return (
        "No high spatial evidence identified in the "
        "current assessment."
    )


df["agent_recommendation"] = df.apply(
    generate_recommendation,
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
    "los_disp_m",
    "los_abs_m",
    "correlation",
    "insar_monitoring_class",
    "insar_quality_acceptable",
    "agent_monitoring_status",
    "agent_explanation",
    "agent_recommendation"
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

print("\nINTELLIGENT AGENT MONITORING REPORT")
print("====================================")

print("\nStatus distribution:")

print(
    result["agent_monitoring_status"]
    .value_counts()
)

print("\nRecommendations:")

print(
    result["agent_recommendation"]
    .value_counts()
)

print("\nOutput:")
print(output_file)