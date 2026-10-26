import pandas as pd
import numpy as np
import os

INPUT_FILE = "data/features/moghalrajpuram_spatial_features.csv"

OUTPUT_FILE = (
    "data/features/"
    "moghalrajpuram_spatial_features_clean.csv"
)

COHERENCE_THRESHOLD = 0.30

# --------------------------------------------------
# Read dataset
# --------------------------------------------------

df = pd.read_csv(INPUT_FILE)

print("=" * 70)
print("CREATING QUALITY-CONTROLLED SPATIAL DATASET")
print("=" * 70)

print("Original rows:", len(df))

# --------------------------------------------------
# Replace invalid values
# --------------------------------------------------

df.replace(
    [np.inf, -np.inf],
    np.nan,
    inplace=True
)

# --------------------------------------------------
# Valid spatial features
# --------------------------------------------------

valid = (
    df["elevation_m"].notna()
    & df["slope_deg"].notna()
    & df["los_displacement_m"].notna()
    & df["coherence"].notna()
    & (df["los_displacement_m"] != -9999)
    & (df["coherence"] != -9999)
)

df = df[valid].copy()

print("After spatial validity check:", len(df))

# --------------------------------------------------
# Coherence quality filtering
# --------------------------------------------------

df = df[
    df["coherence"] >= COHERENCE_THRESHOLD
].copy()

df.reset_index(drop=True, inplace=True)

# --------------------------------------------------
# Save
# --------------------------------------------------

os.makedirs("data/features", exist_ok=True)

df.to_csv(
    OUTPUT_FILE,
    index=False
)

# --------------------------------------------------
# Final information
# --------------------------------------------------

print()
print("Coherence threshold:", COHERENCE_THRESHOLD)
print("Final rows:", len(df))
print("Removed rows:", 2500 - len(df))

print()
print("Final columns:")
print(list(df.columns))

print()
print("Final feature statistics:")
print(
    df[
        [
            "elevation_m",
            "slope_deg",
            "los_displacement_m",
            "coherence"
        ]
    ].describe()
)

print()
print("=" * 70)
print("CLEAN SPATIAL DATASET CREATED")
print("=" * 70)
print("Output:", OUTPUT_FILE)