import pandas as pd
import numpy as np
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = (
    PROJECT
    / "data"
    / "features"
    / "tirumala_temporal_insar_features.csv"
)

output_file = (
    PROJECT
    / "data"
    / "features"
    / "tirumala_temporal_agent_evidence.csv"
)

df = pd.read_csv(input_file)

print("\nTEMPORAL INSAR AGENT EVIDENCE")
print("=============================")

print("Input observations:", len(df))

# Absolute temporal LOS change
df["abs_temporal_change_mm"] = (
    df["abs_los_change_m"] * 1000.0
)

# Exploratory relative threshold:
# top 25% of absolute temporal change
threshold = df["abs_temporal_change_mm"].quantile(0.75)

df["temporal_change_threshold_mm"] = threshold

df["temporal_change_evidence"] = np.where(
    df["abs_temporal_change_mm"] >= threshold,
    "Elevated temporal-change evidence",
    "Lower temporal-change evidence"
)

df["temporal_evidence_flag"] = (
    df["abs_temporal_change_mm"] >= threshold
).astype(int)

# Relative classes for visualization
df["temporal_change_class"] = pd.qcut(
    df["abs_temporal_change_mm"],
    q=3,
    labels=["Low", "Moderate", "High"],
    duplicates="drop"
)

df.to_csv(output_file, index=False)

print("\nTemporal change statistics")
print("--------------------------")
print(
    "Min absolute change:",
    round(df["abs_temporal_change_mm"].min(), 3),
    "mm"
)

print(
    "Max absolute change:",
    round(df["abs_temporal_change_mm"].max(), 3),
    "mm"
)

print(
    "Mean absolute change:",
    round(df["abs_temporal_change_mm"].mean(), 3),
    "mm"
)

print(
    "75th percentile threshold:",
    round(threshold, 3),
    "mm"
)

print("\nEvidence distribution:")
print(df["temporal_change_evidence"].value_counts())

print("\nRelative classes:")
print(df["temporal_change_class"].value_counts())

print("\nOutput:")
print(output_file)

print("\nTemporal agent evidence created.")