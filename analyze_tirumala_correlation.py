import numpy as np
import rasterio

input_file = r"data\processed\dinsar\tirumala\clipped\tirumala_corr_80m.tif"

with rasterio.open(input_file) as src:
    corr = src.read(1, masked=True).compressed()

print("Correlation statistics")
print("----------------------")
print("Valid pixels:", len(corr))
print("Minimum:", float(np.min(corr)))
print("Maximum:", float(np.max(corr)))
print("Mean:", float(np.mean(corr)))

for p in [10, 25, 50, 75, 90]:
    print(f"{p}th percentile:", float(np.percentile(corr, p)))

print("\nPixels above thresholds")
print("-----------------------")

for threshold in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
    count = np.sum(corr >= threshold)
    percentage = count / len(corr) * 100

    print(
        f"Correlation >= {threshold:.1f}: "
        f"{count} pixels ({percentage:.2f}%)"
    )