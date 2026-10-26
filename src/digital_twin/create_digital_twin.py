import pandas as pd
from pathlib import Path


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

INPUT_FILE = Path(
    "data/features/moghalrajpuram_risk_assessment.csv"
)

OUTPUT_DIR = Path(
    "data/digital_twin"
)

OUTPUT_FILE = OUTPUT_DIR / (
    "moghalrajpuram_digital_twin_state.csv"
)


# ---------------------------------------------------------
# Load risk assessment data
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

print(f"Input rows: {len(df)}")


# ---------------------------------------------------------
# Create output directory
# ---------------------------------------------------------

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ---------------------------------------------------------
# Select Digital Twin attributes
# ---------------------------------------------------------

digital_twin = df[
    [
        "pixel_id",
        "latitude",
        "longitude",
        "elevation_m",
        "slope_deg",
        "los_displacement_m",
        "coherence",
        "reference_date",
        "secondary_date",
        "reference_daily_rainfall_mm",
        "reference_3day_rainfall_mm",
        "reference_7day_rainfall_mm",
        "risk_score",
        "risk_category",
        "insar_confidence",
        "evidence_type"
    ]
].copy()


# ---------------------------------------------------------
# Add Digital Twin metadata
# ---------------------------------------------------------

digital_twin.insert(
    0,
    "twin_id",
    [
        f"MGH-{i:04d}"
        for i in range(1, len(digital_twin) + 1)
    ]
)

digital_twin["location"] = "Moghalrajpuram, Vijayawada"

digital_twin["data_source"] = (
    "Sentinel-1 InSAR + Copernicus DEM + GPM IMERG"
)

digital_twin["update_status"] = "Current"


# ---------------------------------------------------------
# Save Digital Twin state
# ---------------------------------------------------------

digital_twin.to_csv(
    OUTPUT_FILE,
    index=False
)


# ---------------------------------------------------------
# Display results
# ---------------------------------------------------------

print()
print("Digital Twin dataset created successfully.")

print(f"Output: {OUTPUT_FILE}")

print()
print("Digital Twin columns:")

for column in digital_twin.columns:
    print(f"- {column}")

print()
print("Number of Digital Twin records:")
print(len(digital_twin))