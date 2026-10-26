import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = PROJECT / "data" / "features" / \
    "tirumala_modeling_dataset.csv"

output_dir = PROJECT / "results" / "eda"
output_dir.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(input_file)

print("======================================")
print("TIRUMALA LANDSLIDE MODELING DATASET EDA")
print("======================================")

print("\nShape:")
print(df.shape)

# --------------------------------------------------
# Basic statistics
# --------------------------------------------------

numeric_cols = [
    "elevation_m",
    "slope_deg",
    "correlation",
    "los_disp_m",
    "los_abs_m",
    "rain_3d_before_start_mm",
    "rain_7d_before_start_mm",
    "rain_14d_before_start_mm",
    "rain_3d_before_end_mm",
    "rain_7d_before_end_mm",
    "rain_14d_before_end_mm"
]

print("\nDescriptive statistics:")
print(
    df[numeric_cols]
    .describe()
    .round(4)
    .to_string()
)

# --------------------------------------------------
# Correlation matrix
# --------------------------------------------------

print("\nCorrelation matrix:")

corr = df[numeric_cols].corr()

print(corr.round(3).to_string())

# Save correlation matrix
corr.to_csv(
    output_dir / "correlation_matrix.csv"
)

# --------------------------------------------------
# Plot 1: Elevation distribution
# --------------------------------------------------

plt.figure(figsize=(8, 5))

plt.hist(
    df["elevation_m"],
    bins=30
)

plt.xlabel("Elevation (m)")
plt.ylabel("Number of observations")
plt.title("Elevation Distribution")

plt.tight_layout()

plt.savefig(
    output_dir / "elevation_distribution.png",
    dpi=300
)

plt.close()

# --------------------------------------------------
# Plot 2: Slope distribution
# --------------------------------------------------

plt.figure(figsize=(8, 5))

plt.hist(
    df["slope_deg"],
    bins=30
)

plt.xlabel("Slope (degrees)")
plt.ylabel("Number of observations")
plt.title("Slope Distribution")

plt.tight_layout()

plt.savefig(
    output_dir / "slope_distribution.png",
    dpi=300
)

plt.close()

# --------------------------------------------------
# Plot 3: Correlation distribution
# --------------------------------------------------

plt.figure(figsize=(8, 5))

plt.hist(
    df["correlation"],
    bins=30
)

plt.xlabel("InSAR Correlation")
plt.ylabel("Number of observations")
plt.title("InSAR Correlation Distribution")

plt.tight_layout()

plt.savefig(
    output_dir / "insar_correlation_distribution.png",
    dpi=300
)

plt.close()

# --------------------------------------------------
# Plot 4: LOS displacement distribution
# --------------------------------------------------

plt.figure(figsize=(8, 5))

plt.hist(
    df["los_disp_m"] * 1000,
    bins=30
)

plt.xlabel("LOS displacement (mm)")
plt.ylabel("Number of observations")
plt.title("LOS Displacement Distribution")

plt.tight_layout()

plt.savefig(
    output_dir / "los_displacement_distribution.png",
    dpi=300
)

plt.close()

# --------------------------------------------------
# Plot 5: Elevation vs slope
# --------------------------------------------------

plt.figure(figsize=(8, 5))

plt.scatter(
    df["elevation_m"],
    df["slope_deg"],
    s=10
)

plt.xlabel("Elevation (m)")
plt.ylabel("Slope (degrees)")
plt.title("Elevation vs Slope")

plt.tight_layout()

plt.savefig(
    output_dir / "elevation_vs_slope.png",
    dpi=300
)

plt.close()

# --------------------------------------------------
# Plot 6: Slope vs LOS displacement
# --------------------------------------------------

plt.figure(figsize=(8, 5))

plt.scatter(
    df["slope_deg"],
    df["los_disp_m"] * 1000,
    s=10
)

plt.xlabel("Slope (degrees)")
plt.ylabel("LOS displacement (mm)")
plt.title("Slope vs LOS Displacement")

plt.tight_layout()

plt.savefig(
    output_dir / "slope_vs_los.png",
    dpi=300
)

plt.close()

# --------------------------------------------------
# Plot 7: Elevation vs LOS displacement
# --------------------------------------------------

plt.figure(figsize=(8, 5))

plt.scatter(
    df["elevation_m"],
    df["los_disp_m"] * 1000,
    s=10
)

plt.xlabel("Elevation (m)")
plt.ylabel("LOS displacement (mm)")
plt.title("Elevation vs LOS Displacement")

plt.tight_layout()

plt.savefig(
    output_dir / "elevation_vs_los.png",
    dpi=300
)

plt.close()

# --------------------------------------------------
# Plot 8: Rainfall comparison
# --------------------------------------------------

rainfall_names = [
    "3-day",
    "7-day",
    "14-day"
]

start_values = [
    df["rain_3d_before_start_mm"].iloc[0],
    df["rain_7d_before_start_mm"].iloc[0],
    df["rain_14d_before_start_mm"].iloc[0]
]

end_values = [
    df["rain_3d_before_end_mm"].iloc[0],
    df["rain_7d_before_end_mm"].iloc[0],
    df["rain_14d_before_end_mm"].iloc[0]
]

x = range(len(rainfall_names))

plt.figure(figsize=(8, 5))

plt.bar(
    [i - 0.2 for i in x],
    start_values,
    width=0.4,
    label="17 Aug 2026"
)

plt.bar(
    [i + 0.2 for i in x],
    end_values,
    width=0.4,
    label="29 Aug 2026"
)

plt.xticks(
    list(x),
    rainfall_names
)

plt.xlabel("Antecedent rainfall window")
plt.ylabel("Rainfall (mm)")
plt.title("Antecedent Rainfall Before Sentinel-1 Acquisitions")
plt.legend()

plt.tight_layout()

plt.savefig(
    output_dir / "antecedent_rainfall_comparison.png",
    dpi=300
)

plt.close()

print("\nEDA plots saved to:")
print(output_dir)

print("\nFiles created:")

for file in sorted(output_dir.iterdir()):
    print(file.name)