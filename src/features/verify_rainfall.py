import rasterio
import glob
import os
import re
import numpy as np

# Moghalrajpuram coordinate
lon = 80.6414837
lat = 16.5060235

# Find daily IMERG rainfall files
files = sorted(
    glob.glob(
        "data/raw/rainfall/extracted/3B-DAY-L.GIS.IMERG.*.V07C.tif"
    )
)

print()
print("IMERG RAINFALL VERIFICATION")
print("=" * 80)
print(f"{'DATE':<12}{'MOGHALRAJPURAM(mm)':>22}{'MIN(mm)':>15}{'MAX(mm)':>15}{'MEAN(mm)':>15}")
print("-" * 80)

for file in files:

    # Extract date from filename
    filename = os.path.basename(file)
    match = re.search(r"IMERG\.(\d{8})\.", filename)

    if not match:
        continue

    date = match.group(1)

    with rasterio.open(file) as src:

        data = src.read(1).astype(float)

        # Convert missing-data value 29999 to NaN
        data[data == 29999] = np.nan

        # Convert stored values to mm
        data = data / 10.0

        # Find Moghalrajpuram pixel
        row, col = src.index(lon, lat)

        rainfall = data[row, col]

        # Calculate statistics
        minimum = np.nanmin(data)
        maximum = np.nanmax(data)
        mean = np.nanmean(data)

        print(
            f"{date:<12}"
            f"{rainfall:>22.2f}"
            f"{minimum:>15.2f}"
            f"{maximum:>15.2f}"
            f"{mean:>15.2f}"
        )

print("-" * 80)
print(f"Total rainfall files found: {len(files)}")
print()
print("Verification completed.")