import rasterio
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

raster_file = (
    PROJECT
    / "data"
    / "processed"
    / "dinsar"
    / "tirumala"
    / "gsi_aoi"
    / "tirumala_temporal_los_change_05_17_to_17_29.tif"
)

aoi_file = (
    PROJECT
    / "data"
    / "raw"
    / "aoi"
    / "tirumala_hills_gsi_map_aoi.geojson"
)

inventory_file = (
    PROJECT
    / "data"
    / "raw"
    / "inventory"
    / "tirumala_gsi_fig32_map_derived_inventory.csv"
)

output_dir = PROJECT / "results" / "insar"
output_dir.mkdir(parents=True, exist_ok=True)

output_png = output_dir / "tirumala_temporal_insar_change_map.png"

print("\nCREATING TEMPORAL INSAR CHANGE MAP")
print("===================================")

# -----------------------------
# Read temporal InSAR raster
# -----------------------------
with rasterio.open(raster_file) as src:
    change = src.read(1)
    bounds = src.bounds
    extent = [
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top
    ]
    raster_crs = src.crs

# Convert metres to millimetres
change_mm = change * 1000.0

valid = np.isfinite(change_mm)

print("Raster CRS:", raster_crs)
print("Raster shape:", change_mm.shape)

if valid.sum() == 0:
    raise ValueError("No valid temporal InSAR pixels found.")

print("Valid pixels:", int(valid.sum()))
print("Min change:", float(change_mm[valid].min()), "mm")
print("Max change:", float(change_mm[valid].max()), "mm")
print("Mean change:", float(change_mm[valid].mean()), "mm")

# -----------------------------
# Read AOI
# -----------------------------
aoi = gpd.read_file(aoi_file)
aoi = aoi.to_crs(raster_crs)

# -----------------------------
# Read GSI map-derived points
# -----------------------------
inventory = gpd.read_file(inventory_file)

# The CSV contains longitude/latitude
inventory = gpd.GeoDataFrame(
    inventory,
    geometry=gpd.points_from_xy(
        inventory["longitude"],
        inventory["latitude"]
    ),
    crs="EPSG:4326"
)

inventory = inventory.to_crs(raster_crs)

# -----------------------------
# Plot
# -----------------------------
fig, ax = plt.subplots(figsize=(11, 8))

masked_change = np.ma.masked_invalid(change_mm)

image = ax.imshow(
    masked_change,
    extent=extent,
    origin="upper"
)

# AOI boundary
aoi.boundary.plot(
    ax=ax,
    linewidth=2,
    label="GSI Figure 3.2 map-derived approximate AOI"
)

# Historical GSI points
inventory.plot(
    ax=ax,
    marker="o",
    markersize=28,
    label="GSI Figure 3.2 map-derived points"
)

cbar = plt.colorbar(image, ax=ax)
cbar.set_label("Temporal LOS change (mm)")

ax.set_title(
    "Tirumala Hills Multi-temporal InSAR Change\n"
    "05–17 Aug 2026 vs 17–29 Aug 2026"
)

ax.set_xlabel("Easting (m)")
ax.set_ylabel("Northing (m)")

ax.legend(loc="best")

plt.tight_layout()

plt.savefig(
    output_png,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print("\nMap created successfully.")
print("Output:", output_png)