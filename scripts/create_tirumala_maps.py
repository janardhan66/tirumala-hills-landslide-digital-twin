import os
import rasterio
import matplotlib.pyplot as plt


INPUT_DIR = r"data\processed\dinsar\tirumala\gsi_aoi"
OUTPUT_DIR = r"results\maps"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def plot_raster(filename, title, output_name, cmap, colorbar_label):
    path = os.path.join(INPUT_DIR, filename)

    with rasterio.open(path) as src:
        data = src.read(1)
        nodata = src.nodata

    if nodata is not None:
        data = data.astype(float)
        data[data == nodata] = float("nan")

    plt.figure(figsize=(9, 6))

    image = plt.imshow(data, cmap=cmap)

    plt.title(title)
    plt.xlabel("Raster Column")
    plt.ylabel("Raster Row")

    cbar = plt.colorbar(image)
    cbar.set_label(colorbar_label)

    plt.tight_layout()

    output_path = os.path.join(OUTPUT_DIR, output_name)
    plt.savefig(output_path, dpi=300)
    plt.close()

    print("Created:", output_path)


# ---------------------------------------------------------
# SLOPE MAP
# ---------------------------------------------------------

plot_raster(
    "tirumala_slope_80m_gsi_aoi.tif",
    "Tirumala Hills - Slope Map",
    "tirumala_slope_map.png",
    "terrain",
    "Slope (degrees)"
)


# ---------------------------------------------------------
# LOS DISPLACEMENT MAP
# ---------------------------------------------------------

plot_raster(
    "tirumala_masked_los_disp_80m_gsi_aoi.tif",
    "Tirumala Hills - InSAR LOS Displacement",
    "tirumala_los_displacement_map.png",
    "RdBu_r",
    "LOS displacement (m)"
)


print("\nMapping completed.")