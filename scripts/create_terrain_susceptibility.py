import pandas as pd
import numpy as np
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = PROJECT / "data" / "features" / \
    "tirumala_modeling_dataset.csv"

output_file = PROJECT / "data" / "features" / \
    "tirumala_terrain_susceptibility.csv"


# --------------------------------------------------
# Read data
# --------------------------------------------------

df = pd.read_csv(input_file)

print("Input observations:", len(df))


# --------------------------------------------------
# Min-Max normalization
#
# This converts each terrain variable to 0-1.
# --------------------------------------------------

def minmax(series):

    minimum = series.min()
    maximum = series.max()

    if maximum == minimum:
        return pd.Series(
            np.zeros(len(series)),
            index=series.index
        )

    return (series - minimum) / (maximum - minimum)


df["slope_norm"] = minmax(df["slope_deg"])

df["elevation_norm"] = minmax(
    df["elevation_m"]
)


# --------------------------------------------------
# Terrain indicator
#
# Equal contribution is used only to construct a
# transparent descriptive indicator.
# It is NOT a calibrated probability.
# --------------------------------------------------

df["terrain_indicator"] = (
    0.5 * df["slope_norm"] +
    0.5 * df["elevation_norm"]
)


# --------------------------------------------------
# Classify indicator into relative classes
#
# Quantiles are used so that the classes describe
# relative conditions within this study area.
# --------------------------------------------------

df["terrain_class"] = pd.qcut(
    df["terrain_indicator"],
    q=3,
    labels=[
        "Low",
        "Moderate",
        "High"
    ],
    duplicates="drop"
)


# --------------------------------------------------
# Save
# --------------------------------------------------

columns = [
    "row",
    "col",
    "elevation_m",
    "slope_deg",
    "slope_norm",
    "elevation_norm",
    "terrain_indicator",
    "terrain_class"
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

print("\nTERRAIN SUSCEPTIBILITY COMPONENT")
print("================================")

print("\nSlope range:")
print(
    f"{df['slope_deg'].min():.2f} - "
    f"{df['slope_deg'].max():.2f} degrees"
)

print("\nElevation range:")
print(
    f"{df['elevation_m'].min():.2f} - "
    f"{df['elevation_m'].max():.2f} m"
)

print("\nTerrain indicator:")
print(
    f"{df['terrain_indicator'].min():.3f} - "
    f"{df['terrain_indicator'].max():.3f}"
)

print("\nTerrain classes:")
print(
    result["terrain_class"]
    .value_counts()
    .sort_index()
)

print("\nOutput:")
print(output_file)