import pandas as pd
import os

# --------------------------------------------------
# Input files
# --------------------------------------------------

SPATIAL_FILE = (
    "data/features/"
    "moghalrajpuram_spatial_features_clean.csv"
)

RAINFALL_FILE = (
    "data/processed/rainfall/"
    "moghalrajpuram_rainfall_features.csv"
)

OUTPUT_FILE = (
    "data/features/"
    "moghalrajpuram_integrated_features.csv"
)

# --------------------------------------------------
# Read data
# --------------------------------------------------

spatial = pd.read_csv(SPATIAL_FILE)
rainfall = pd.read_csv(RAINFALL_FILE)

# --------------------------------------------------
# Select rainfall information for the two
# Sentinel-1 acquisition dates
# --------------------------------------------------

reference_date = "2026-08-17"
secondary_date = "2026-08-29"

rain_ref = rainfall[
    rainfall["date"] == reference_date
].iloc[0]

rain_sec = rainfall[
    rainfall["date"] == secondary_date
].iloc[0]

# --------------------------------------------------
# Add rainfall features
# --------------------------------------------------

spatial["reference_date"] = reference_date
spatial["secondary_date"] = secondary_date

spatial["reference_daily_rainfall_mm"] = (
    rain_ref["daily_rainfall_mm"]
)

spatial["reference_3day_rainfall_mm"] = (
    rain_ref["rainfall_3day_mm"]
)

spatial["reference_7day_rainfall_mm"] = (
    rain_ref["rainfall_7day_mm"]
)

spatial["secondary_daily_rainfall_mm"] = (
    rain_sec["daily_rainfall_mm"]
)

spatial["secondary_3day_rainfall_mm"] = (
    rain_sec["rainfall_3day_mm"]
)

spatial["secondary_7day_rainfall_mm"] = (
    rain_sec["rainfall_7day_mm"]
)

# --------------------------------------------------
# Derived rainfall features
# --------------------------------------------------

spatial["daily_rainfall_change_mm"] = (
    spatial["secondary_daily_rainfall_mm"]
    - spatial["reference_daily_rainfall_mm"]
)

spatial["rainfall_3day_change_mm"] = (
    spatial["secondary_3day_rainfall_mm"]
    - spatial["reference_3day_rainfall_mm"]
)

spatial["rainfall_7day_change_mm"] = (
    spatial["secondary_7day_rainfall_mm"]
    - spatial["reference_7day_rainfall_mm"]
)

# --------------------------------------------------
# Save
# --------------------------------------------------

os.makedirs("data/features", exist_ok=True)

spatial.to_csv(
    OUTPUT_FILE,
    index=False
)

# --------------------------------------------------
# Display information
# --------------------------------------------------

print("=" * 70)
print("INTEGRATED SPATIAL + RAINFALL DATASET CREATED")
print("=" * 70)

print("Output:", OUTPUT_FILE)
print("Rows:", len(spatial))
print("Columns:", len(spatial.columns))

print()
print("Reference date:", reference_date)
print("Secondary date:", secondary_date)

print()
print("Reference rainfall:")
print("Daily :", rain_ref["daily_rainfall_mm"], "mm")
print("3-day :", rain_ref["rainfall_3day_mm"], "mm")
print("7-day :", rain_ref["rainfall_7day_mm"], "mm")

print()
print("Secondary rainfall:")
print("Daily :", rain_sec["daily_rainfall_mm"], "mm")
print("3-day :", rain_sec["rainfall_3day_mm"], "mm")
print("7-day :", rain_sec["rainfall_7day_mm"], "mm")

print()
print("First 5 rows:")
print(spatial.head())

print()
print("=" * 70)