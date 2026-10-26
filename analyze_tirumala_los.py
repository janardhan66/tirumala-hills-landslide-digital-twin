import numpy as np
import rasterio

input_file = r"data\processed\dinsar\tirumala\clipped\tirumala_masked_los_disp_80m.tif"

with rasterio.open(input_file) as src:
    los = src.read(1, masked=True).compressed()

# Convert metres to millimetres
los_mm = los * 1000.0

print("Tirumala Hills Quality-Masked LOS Displacement")
print("-----------------------------------------------")
print("Valid pixels:", len(los_mm))
print("Minimum (mm):", float(np.min(los_mm)))
print("Maximum (mm):", float(np.max(los_mm)))
print("Mean (mm):", float(np.mean(los_mm)))
print("Median (mm):", float(np.median(los_mm)))

for p in [10, 25, 75, 90, 95]:
    print(
        f"{p}th percentile (mm):",
        float(np.percentile(los_mm, p))
    )

print("\nAbsolute LOS magnitude")
print("----------------------")

absolute_mm = np.abs(los_mm)

print("Minimum |LOS| (mm):", float(np.min(absolute_mm)))
print("Maximum |LOS| (mm):", float(np.max(absolute_mm)))
print("Mean |LOS| (mm):", float(np.mean(absolute_mm)))
print("Median |LOS| (mm):", float(np.median(absolute_mm)))