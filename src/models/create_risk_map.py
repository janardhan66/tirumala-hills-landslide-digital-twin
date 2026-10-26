import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import geopandas as gpd
from pathlib import Path


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

INPUT_FILE = Path(
    "data/features/moghalrajpuram_risk_assessment.csv"
)

AOI_FILE = Path(
    "data/raw/aoi/moghalrajpuram_aoi.geojson"
)

OUTPUT_DIR = Path("outputs/maps")

OUTPUT_FILE = OUTPUT_DIR / "moghalrajpuram_final_risk_map.png"


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

aoi = gpd.read_file(AOI_FILE)

print(f"Risk data rows: {len(df)}")
print(f"AOI features: {len(aoi)}")


# ---------------------------------------------------------
# Create output directory
# ---------------------------------------------------------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Risk colors
# ---------------------------------------------------------

risk_colors = {
    "Low": "green",
    "Moderate": "yellow",
    "High": "orange",
    "Very High": "red"
}


risk_order = [
    "Low",
    "Moderate",
    "High",
    "Very High"
]


# ---------------------------------------------------------
# Create figure
# ---------------------------------------------------------

fig, ax = plt.subplots(
    figsize=(10, 8)
)


# ---------------------------------------------------------
# Plot AOI boundary
# ---------------------------------------------------------

aoi.boundary.plot(
    ax=ax,
    linewidth=2
)


# ---------------------------------------------------------
# Plot risk pixels
# ---------------------------------------------------------

for risk in risk_order:

    subset = df[
        df["risk_category"] == risk
    ]

    ax.scatter(
        subset["longitude"],
        subset["latitude"],
        s=35,
        c=risk_colors[risk],
        label=risk,
        alpha=0.85,
        edgecolors="none"
    )


# ---------------------------------------------------------
# Labels and title
# ---------------------------------------------------------

ax.set_xlabel(
    "Longitude"
)

ax.set_ylabel(
    "Latitude"
)

ax.set_title(
    "Landslide Risk Assessment – Moghalrajpuram, Vijayawada",
    fontsize=14
)


# ---------------------------------------------------------
# Legend
# ---------------------------------------------------------

legend_handles = []

for risk in risk_order:

    legend_handles.append(
        Patch(
            facecolor=risk_colors[risk],
            label=risk
        )
    )


ax.legend(
    handles=legend_handles,
    title="Risk Category",
    loc="upper right"
)


# ---------------------------------------------------------
# Grid
# ---------------------------------------------------------

ax.grid(
    True,
    alpha=0.3
)


# ---------------------------------------------------------
# Equal geographic aspect
# ---------------------------------------------------------

ax.set_aspect(
    "equal",
    adjustable="box"
)


# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

plt.tight_layout()

plt.savefig(
    OUTPUT_FILE,
    dpi=300,
    bbox_inches="tight"
)

plt.close()


# ---------------------------------------------------------
# Final information
# ---------------------------------------------------------

print()
print("Final risk map created successfully.")
print(f"Output: {OUTPUT_FILE}")

print()
print("Risk distribution:")

print(
    df["risk_category"]
    .value_counts()
    .reindex(
        risk_order,
        fill_value=0
    )
    .to_string()
)