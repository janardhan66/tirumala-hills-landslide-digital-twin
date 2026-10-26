import os
import rasterio
import geopandas as gpd
import matplotlib.pyplot as plt


# =========================================================
# PATHS
# =========================================================

INPUT_DIR = r"data\processed\dinsar\tirumala\gsi_aoi"

AOI_FILE = r"data\raw\aoi\tirumala_hills_gsi_map_aoi.geojson"

OUTPUT_DIR = r"results\maps"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# =========================================================
# LOAD AOI
# =========================================================

aoi = gpd.read_file(AOI_FILE)

print("AOI CRS:", aoi.crs)
print("AOI bounds:", aoi.total_bounds)


# =========================================================
# FUNCTION TO PLOT GEOGRAPHIC RASTER
# =========================================================

def plot_geographic_raster(
    filename,
    title,
    output_name,
    cmap,
    colorbar_label
):

    raster_path = os.path.join(INPUT_DIR, filename)

    with rasterio.open(raster_path) as src:

        data = src.read(1).astype(float)

        transform = src.transform
        raster_crs = src.crs

        nodata = src.nodata

        # Convert raster row/column coordinates
        # into geographic coordinates
        left = transform.c
        top = transform.f

        right = left + transform.a * src.width
        bottom = top + transform.e * src.height

        extent = [
            left,
            right,
            bottom,
            top
        ]

    # Handle nodata
    if nodata is not None:
        data[data == nodata] = float("nan")

    # Reproject AOI to raster CRS if required
    aoi_plot = aoi.to_crs(raster_crs)

    # -----------------------------------------------------
    # PLOT
    # -----------------------------------------------------

    fig, ax = plt.subplots(figsize=(10, 7))

    image = ax.imshow(
        data,
        extent=extent,
        origin="upper",
        cmap=cmap
    )

    # AOI boundary
    aoi_plot.boundary.plot(
        ax=ax,
        linewidth=2
    )

    ax.set_title(title)

    ax.set_xlabel("Easting (m) - UTM Zone 44N")
    ax.set_ylabel("Northing (m) - UTM Zone 44N")

    cbar = fig.colorbar(
        image,
        ax=ax,
        shrink=0.85
    )

    cbar.set_label(colorbar_label)

    ax.set_aspect("equal")

    plt.tight_layout()

    output_path = os.path.join(
        OUTPUT_DIR,
        output_name
    )

    plt.savefig(
        output_path,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    print("Created:", output_path)


# =========================================================
# SLOPE MAP
# =========================================================

plot_geographic_raster(
    filename="tirumala_slope_80m_gsi_aoi.tif",
    title="Tirumala Hills - Slope Map",
    output_name="tirumala_slope_geographic_map.png",
    cmap="terrain",
    colorbar_label="Slope (degrees)"
)


# =========================================================
# INSAR LOS MAP
# =========================================================

plot_geographic_raster(
    filename="tirumala_masked_los_disp_80m_gsi_aoi.tif",
    title="Tirumala Hills - InSAR LOS Displacement",
    output_name="tirumala_los_geographic_map.png",
    cmap="RdBu_r",
    colorbar_label="LOS displacement (m)"
)


print("\n========================================")
print("Geographic mapping completed.")
print("========================================")