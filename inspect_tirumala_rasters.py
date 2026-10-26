import os
import rasterio
import matplotlib.pyplot as plt

folder = r"data\processed\dinsar\tirumala\clipped"

files = [
    "tirumala_dem_80m.tif",
    "tirumala_corr_80m.tif",
    "tirumala_los_disp_80m.tif",
]

titles = [
    "Tirumala Hills DEM",
    "Tirumala Hills InSAR Correlation",
    "Tirumala Hills LOS Displacement",
]

for filename, title in zip(files, titles):
    path = os.path.join(folder, filename)

    with rasterio.open(path) as src:
        data = src.read(1, masked=True)

    plt.figure(figsize=(8, 6))
    plt.imshow(data)
    plt.colorbar()
    plt.title(title)
    plt.xlabel("Column")
    plt.ylabel("Row")
    plt.tight_layout()

    output = os.path.join(
        folder,
        filename.replace(".tif", ".png")
    )

    plt.savefig(output, dpi=150)
    plt.close()

    print("Created:", output)

print("\nVisualization completed.")