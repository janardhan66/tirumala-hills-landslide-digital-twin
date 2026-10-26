import rasterio
import glob
import os
import re
import numpy as np
import pandas as pd

# --------------------------------------------------
# Project settings
# --------------------------------------------------

RAINFALL_DIR = "data/raw/rainfall/extracted"
OUTPUT_DIR = "data/processed/rainfall"

LON = 80.6414837
LAT = 16.5060235

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------------------------------------------------
# Read daily rainfall
# --------------------------------------------------

files = sorted(
    glob.glob(
        os.path.join(
            RAINFALL_DIR,
            "3B-DAY-L.GIS.IMERG.*.V07C.tif"
        )
    )
)

records = []

for file in files:

    filename = os.path.basename(file)

    match = re.search(
        r"IMERG\.(\d{8})\.",
        filename
    )

    if not match:
        continue

    date_string = match.group(1)
    date = pd.to_datetime(date_string, format="%Y%m%d")

    with rasterio.open(file) as src:

        data = src.read(1).astype(float)

        # Missing-data value
        data[data == 29999] = np.nan

        # Convert stored value to mm
        data = data / 10.0

        row, col = src.index(LON, LAT)

        rainfall = data[row, col]

    records.append(
        {
            "date": date,
            "daily_rainfall_mm": rainfall
        }
    )

# --------------------------------------------------
# Create dataframe
# --------------------------------------------------

df = pd.DataFrame(records)

df = df.sort_values("date")

# --------------------------------------------------
# Reindex to actual calendar days
# Missing dates remain NaN
# --------------------------------------------------

df = df.set_index("date")

full_dates = pd.date_range(
    start=df.index.min(),
    end=df.index.max(),
    freq="D"
)

df = df.reindex(full_dates)

# --------------------------------------------------
# Calculate calendar-correct antecedent rainfall
# --------------------------------------------------

df["rainfall_3day_mm"] = (
    df["daily_rainfall_mm"]
    .rolling(window=3, min_periods=3)
    .sum()
)

df["rainfall_7day_mm"] = (
    df["daily_rainfall_mm"]
    .rolling(window=7, min_periods=7)
    .sum()
)

# --------------------------------------------------
# Add location
# --------------------------------------------------

df["latitude"] = LAT
df["longitude"] = LON

df = df.reset_index()

df = df.rename(
    columns={"index": "date"}
)

# --------------------------------------------------
# Save corrected dataset
# --------------------------------------------------

output_file = os.path.join(
    OUTPUT_DIR,
    "moghalrajpuram_rainfall_features.csv"
)

df.to_csv(output_file, index=False)

# --------------------------------------------------
# Display results
# --------------------------------------------------

print()
print("=" * 85)
print("CORRECTED RAINFALL FEATURE DATASET")
print("=" * 85)

print(
    df.to_string(index=False)
)

print()
print("=" * 85)
print("SENTINEL-1 ACQUISITION DATES")
print("=" * 85)

important_dates = df[
    df["date"].isin(
        [
            pd.Timestamp("2026-08-17"),
            pd.Timestamp("2026-08-29")
        ]
    )
]

print(
    important_dates.to_string(index=False)
)

print()
print("=" * 85)
print("OUTPUT")
print("=" * 85)

print(output_file)

print()
print("Original rainfall files:", len(files))
print("Calendar days represented:", len(df))
print()
print("Processing completed successfully.")