import os
import rasterio
import matplotlib.pyplot as plt

input_file = r"data\processed\dinsar\tirumala\clipped\tirumala_slope_80m.tif"
output_file = r"data\processed\dinsar\tirumala\clipped\tirumala_slope_80m.png"

with rasterio.open(input_file) as src:
    slope = src.read(1, masked=True)

plt.figure(figsize=(8, 6))
plt.imshow(slope)
plt.colorbar(label="Slope (degrees)")
plt.title("Tirumala Hills Slope")
plt.xlabel("Column")
plt.ylabel("Row")
plt.tight_layout()

plt.savefig(output_file, dpi=150)
plt.close()

print("Created:", output_file)