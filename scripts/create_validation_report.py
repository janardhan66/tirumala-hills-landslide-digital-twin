import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = (
    PROJECT
    / "results"
    / "validation"
    / "gsi_agent_spatial_validation.csv"
)

output_dir = PROJECT / "results" / "validation"
output_dir.mkdir(parents=True, exist_ok=True)

report_file = (
    output_dir
    / "gsi_agent_validation_summary.csv"
)

figure_file = (
    output_dir
    / "gsi_agent_validation_proximity.png"
)

df = pd.read_csv(input_file)

# ------------------------------------------------
# Calculate percentages
# ------------------------------------------------

total = len(df)

summary = pd.DataFrame({
    "proximity_window_m": [160, 320, 500],
    "historical_locations": [total] * 3,
    "supporting_locations": [
        int(df["support_160m"].sum()),
        int(df["support_320m"].sum()),
        int(df["support_500m"].sum())
    ]
})

summary["support_percentage"] = (
    summary["supporting_locations"]
    / summary["historical_locations"]
    * 100
)

# ------------------------------------------------
# Save summary
# ------------------------------------------------

summary.to_csv(
    report_file,
    index=False
)

# ------------------------------------------------
# Create figure
# ------------------------------------------------

plt.figure(figsize=(8, 5))

plt.plot(
    summary["proximity_window_m"],
    summary["support_percentage"],
    marker="o"
)

plt.xlabel("Proximity window (m)")
plt.ylabel("GSI locations with supporting agent evidence (%)")
plt.title(
    "Spatial Validation of Intelligent-Agent Evidence\n"
    "Against GSI Figure 3.2 Historical Locations"
)

plt.xticks([160, 320, 500])

plt.ylim(0, 100)

plt.grid(True, alpha=0.3)

plt.tight_layout()

plt.savefig(
    figure_file,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

# ------------------------------------------------
# Print report
# ------------------------------------------------

print("\nGSI vs AGENT VALIDATION REPORT")
print("==============================")

print(
    summary.to_string(index=False)
)

print("\nNearest-agent distance statistics:")
print(
    df["nearest_agent_distance_m"]
    .describe()
    .to_string()
)

print("\nOutput files:")
print(report_file)
print(figure_file)