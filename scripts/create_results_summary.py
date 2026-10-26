import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

# ------------------------------------------------
# Input files
# ------------------------------------------------

terrain_file = (
    PROJECT / "data" / "features"
    / "tirumala_terrain_susceptibility.csv"
)

insar_file = (
    PROJECT / "data" / "features"
    / "tirumala_insar_monitoring_component.csv"
)

temporal_file = (
    PROJECT / "data" / "features"
    / "tirumala_temporal_agent_evidence.csv"
)

agent_file = (
    PROJECT / "data" / "features"
    / "tirumala_final_agent_evidence.csv"
)

validation_file = (
    PROJECT / "results" / "validation"
    / "gsi_agent_spatial_validation.csv"
)

output_dir = PROJECT / "results" / "summary"
output_dir.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------
# Load data
# ------------------------------------------------

terrain = pd.read_csv(terrain_file)
insar = pd.read_csv(insar_file)
temporal = pd.read_csv(temporal_file)
agent = pd.read_csv(agent_file)
validation = pd.read_csv(validation_file)

# ------------------------------------------------
# Print dataset sizes
# ------------------------------------------------

print("\nRESEARCH RESULTS SUMMARY")
print("========================")

print("Terrain observations:", len(terrain))
print("InSAR observations:", len(insar))
print("Temporal observations:", len(temporal))
print("Agent observations:", len(agent))
print("GSI validation locations:", len(validation))

# ------------------------------------------------
# 1. Terrain classes
# ------------------------------------------------

terrain_counts = (
    terrain["terrain_class"]
    .value_counts()
    .reindex(["Low", "Moderate", "High"])
    .fillna(0)
)

terrain_percent = (
    terrain_counts / terrain_counts.sum() * 100
)

plt.figure(figsize=(8, 5.5))

bars = plt.bar(
    terrain_counts.index,
    terrain_counts.values
)

# Add count and percentage labels
for bar, count, pct in zip(
    bars,
    terrain_counts.values,
    terrain_percent.values
):
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 15,
        f"{int(count)} ({pct:.1f}%)",
        ha="center"
    )

plt.xlabel("Relative terrain evidence class")
plt.ylabel("Number of observations")

plt.title(
    "Relative Terrain Evidence Distribution"
)

plt.ylim(
    0,
    terrain_counts.max() * 1.12
)

plt.tight_layout()

terrain_plot = (
    output_dir / "01_terrain_evidence_distribution.png"
)

plt.savefig(
    terrain_plot,
    dpi=300,
    bbox_inches="tight"
)

plt.close()
# ------------------------------------------------
# 2. InSAR monitoring classes
# ------------------------------------------------

insar_counts = (
    insar["insar_monitoring_class"]
    .value_counts()
    .reindex(["Low", "Moderate", "High"])
    .fillna(0)
)

insar_percent = (
    insar_counts / insar_counts.sum() * 100
)

plt.figure(figsize=(8, 5.5))

bars = plt.bar(
    insar_counts.index,
    insar_counts.values
)

# Add count and percentage labels
for bar, count, pct in zip(
    bars,
    insar_counts.values,
    insar_percent.values
):
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 15,
        f"{int(count)} ({pct:.1f}%)",
        ha="center"
    )

plt.xlabel("Relative InSAR monitoring class")
plt.ylabel("Number of observations")

plt.title(
    "Relative InSAR Monitoring Evidence Distribution"
)

plt.ylim(
    0,
    insar_counts.max() * 1.12
)

plt.tight_layout()

insar_plot = (
    output_dir / "02_insar_monitoring_distribution.png"
)

plt.savefig(
    insar_plot,
    dpi=300,
    bbox_inches="tight"
)

plt.close()
# ------------------------------------------------
# 3. Temporal InSAR change
# ------------------------------------------------

if "abs_temporal_change_mm" in temporal.columns:

    temporal_values = (
        temporal["abs_temporal_change_mm"]
        .dropna()
    )

else:

    temporal_values = pd.Series(dtype=float)

mean_change = temporal_values.mean()
max_change = temporal_values.max()
median_change = temporal_values.median()

plt.figure(figsize=(8, 5.5))

plt.hist(
    temporal_values,
    bins=30
)

plt.axvline(
    mean_change,
    linestyle="--",
    linewidth=1.5,
    label=f"Mean = {mean_change:.2f} mm"
)

plt.xlabel(
    "Absolute temporal LOS change (mm)"
)

plt.ylabel("Number of observations")

plt.title(
    "Multi-temporal InSAR Change Distribution"
)

plt.legend()

plt.text(
    0.98,
    0.95,
    f"Valid observations: {len(temporal_values):,}\n"
    f"Median: {median_change:.2f} mm\n"
    f"Mean: {mean_change:.2f} mm\n"
    f"Maximum: {max_change:.2f} mm",
    transform=plt.gca().transAxes,
    ha="right",
    va="top"
)

plt.tight_layout()

temporal_plot = (
    output_dir / "03_temporal_insar_change_distribution.png"
)

plt.savefig(
    temporal_plot,
    dpi=300,
    bbox_inches="tight"
)

plt.close()
# ------------------------------------------------
# 4. Intelligent-agent evidence
# ------------------------------------------------

agent_counts = (
    agent["final_agent_evidence"]
    .value_counts()
)

agent_percent = (
    agent_counts / agent_counts.sum() * 100
)

plt.figure(figsize=(10, 6))

bars = plt.barh(
    agent_counts.index[::-1],
    agent_counts.values[::-1]
)

# Add count and percentage labels
for bar, count, pct in zip(
    bars,
    agent_counts.values[::-1],
    agent_percent.values[::-1]
):
    plt.text(
        bar.get_width() + 20,
        bar.get_y() + bar.get_height() / 2,
        f"{int(count)} ({pct:.1f}%)",
        va="center"
    )

plt.xlabel("Number of spatial observations")
plt.ylabel("Intelligent-agent evidence category")

plt.title(
    "Intelligent-Agent Evidence Distribution"
)

plt.xlim(
    0,
    agent_counts.max() * 1.18
)

plt.tight_layout()

agent_plot = (
    output_dir / "04_agent_evidence_distribution.png"
)

plt.savefig(
    agent_plot,
    dpi=300,
    bbox_inches="tight"
)

plt.close()
# ------------------------------------------------
# 5. GSI spatial validation
# ------------------------------------------------

validation_summary = pd.DataFrame({
    "window_m": [160, 320, 500],
    "supporting": [
        validation["support_160m"].sum(),
        validation["support_320m"].sum(),
        validation["support_500m"].sum()
    ]
})

validation_summary["percentage"] = (
    validation_summary["supporting"]
    / len(validation)
    * 100
)

plt.figure(figsize=(8, 5.5))

plt.plot(
    validation_summary["window_m"],
    validation_summary["percentage"],
    marker="o",
    linewidth=2
)

# Add percentage labels
for _, row in validation_summary.iterrows():
    plt.annotate(
        f"{row['supporting']}/{len(validation)} "
        f"({row['percentage']:.1f}%)",
        (row["window_m"], row["percentage"]),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center"
    )

plt.xlabel("Spatial proximity window (m)")
plt.ylabel(
    "GSI locations with supporting agent evidence (%)"
)

plt.title(
    "Spatial Correspondence with GSI Historical Evidence"
)

plt.xticks([160, 320, 500])
plt.ylim(0, 100)
plt.grid(True, alpha=0.3)

plt.tight_layout()

validation_plot = (
    output_dir / "05_gsi_agent_validation.png"
)

plt.savefig(
    validation_plot,
    dpi=300,
    bbox_inches="tight"
)

plt.close()
# ------------------------------------------------
# Save numerical summary
# ------------------------------------------------

summary = pd.DataFrame({
    "metric": [
        "Terrain observations",
        "InSAR observations",
        "Temporal InSAR observations",
        "Agent observations",
        "GSI historical locations",
        "GSI support within 160 m (%)",
        "GSI support within 320 m (%)",
        "GSI support within 500 m (%)"
    ],
    "value": [
        len(terrain),
        len(insar),
        len(temporal),
        len(agent),
        len(validation),
        validation_summary.loc[
            validation_summary["window_m"] == 160,
            "percentage"
        ].iloc[0],
        validation_summary.loc[
            validation_summary["window_m"] == 320,
            "percentage"
        ].iloc[0],
        validation_summary.loc[
            validation_summary["window_m"] == 500,
            "percentage"
        ].iloc[0]
    ]
})

summary_file = (
    output_dir / "research_results_summary.csv"
)

summary.to_csv(
    summary_file,
    index=False
)

# ------------------------------------------------
# Final output
# ------------------------------------------------

print("\nValidation percentages:")

for _, row in validation_summary.iterrows():

    print(
        f"{int(row['window_m'])} m: "
        f"{int(row['supporting'])}/{len(validation)} "
        f"({row['percentage']:.1f}%)"
    )

print("\nGenerated figures:")

print(terrain_plot)
print(insar_plot)
print(temporal_plot)
print(agent_plot)
print(validation_plot)

print("\nSummary:")
print(summary_file)