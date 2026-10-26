import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import rasterio
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

# --------------------------------------------------
# Input files
# --------------------------------------------------

inventory_file = PROJECT / "data" / "features" / \
    "tirumala_gsi_validation_table.csv"

aoi_file = PROJECT / "data" / "raw" / "aoi" / \
    "tirumala_hills_gsi_map_aoi.geojson"

slope_file = PROJECT / "data" / "processed" / "dinsar" / \
    "tirumala" / "gsi_aoi" / \
    "tirumala_slope_80m_gsi_aoi.tif"

los_file = PROJECT / "data" / "processed" / "dinsar" / \
    "tirumala" / "gsi_aoi" / \
    "tirumala_masked_los_disp_80m_gsi_aoi.tif"

output_dir = PROJECT / "results" / "maps"
output_dir.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# Read GSI point data
# --------------------------------------------------

gsi = pd.read_csv(inventory_file)

gsi_gdf = gpd.GeoDataFrame(
    gsi,
    geometry=gpd.points_from_xy(
        gsi["longitude"],
        gsi["latitude"]
    ),
    crs="EPSG:4326"
)

aoi = gpd.read_file(aoi_file)

print("GSI points:", len(gsi_gdf))
print("AOI CRS:", aoi.crs)

# --------------------------------------------------
# Function to plot raster + GSI locations
# --------------------------------------------------

def plot_raster(raster_file, output_file, title, colorbar_label):

    with rasterio.open(raster_file) as src:

        data = src.read(1).astype(float)

        if src.nodata is not None:
            data[data == src.nodata] = float("nan")

        bounds = src.bounds
        raster_crs = src.crs

    aoi_projected = aoi.to_crs(raster_crs)
    gsi_projected = gsi_gdf.to_crs(raster_crs)

    extent = [
        bounds.left,
        bounds.right,
        bounds.bottom,
        bounds.top
    ]

    fig, ax = plt.subplots(figsize=(11, 7))

    image = ax.imshow(
        data,
        extent=extent,
        origin="upper"
    )

    # AOI boundary
    aoi_projected.boundary.plot(
        ax=ax,
        linewidth=2
    )

    # GSI points
    gsi_projected.plot(
        ax=ax,
        marker="o",
        markersize=40,
        facecolors="none",
        edgecolors="black",
        linewidth=1.2
    )

    # Point numbers
    for _, row in gsi_projected.iterrows():

        number = row["inventory_id"].replace(
            "GSI_FIG32_",
            ""
        )

        ax.annotate(
            number,
            (
                row.geometry.x,
                row.geometry.y
            ),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8
        )

    ax.set_title(title)

    ax.set_xlabel(
        "Easting (m), EPSG:32644"
    )

    ax.set_ylabel(
        "Northing (m), EPSG:32644"
    )

    fig.colorbar(
        image,
        ax=ax,
        label=colorbar_label
    )

    fig.tight_layout()

    fig.savefig(
        output_file,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)

    print("Created:", output_file)


# --------------------------------------------------
# Slope evidence map
# --------------------------------------------------

plot_raster(
    slope_file,
    output_dir / "tirumala_gsi_evidence_slope_map.png",
    "Tirumala Hills: Slope and GSI Figure 3.2 Map-Derived Locations",
    "Slope (degrees)"
)

# --------------------------------------------------
# InSAR LOS evidence map
# --------------------------------------------------

plot_raster(
    los_file,
    output_dir / "tirumala_gsi_evidence_los_map.png",
    "Tirumala Hills: InSAR LOS Displacement and GSI Figure 3.2 Locations",
    "LOS displacement (mm)"
)

print("\nEvidence maps completed.")
print("Output directory:")
print(output_dir)