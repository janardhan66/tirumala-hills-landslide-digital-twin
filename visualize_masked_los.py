import rasterio
import matplotlib.pyplot as plt

input_file = r"data\processed\dinsar\tirumala\clipped\tirumala_masked_los_disp_80m.tif"
output_file = r"data\processed\dinsar\tirumala\clipped\tirumala_masked_los_disp_80m.png"

with rasterio.open(input_file) as src:
    los = src.read(1, masked=True)

plt.figure(figsize=(8, 6))
plt.imshow(los)
plt.colorbar(label="LOS Displacement (m)")
plt.title("Tirumala Hills Quality-Masked LOS Displacement")
plt.xlabel("Column")
plt.ylabel("Row")
plt.tight_layout()

plt.savefig(output_file, dpi=150)
plt.close()

print("Created:", output_file)