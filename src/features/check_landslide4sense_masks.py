import h5py
import glob
import numpy as np

files = glob.glob(
    "data/raw/landslide4sense/TrainData/mask/*.h5"
)

total_landslide = 0
total_non_landslide = 0
patches_with_landslide = 0
patches_without_landslide = 0

positive_counts = []

for file in files:

    with h5py.File(file, "r") as f:
        mask = f["mask"][:]

    landslide_pixels = int(np.sum(mask == 1))
    non_landslide_pixels = int(np.sum(mask == 0))

    total_landslide += landslide_pixels
    total_non_landslide += non_landslide_pixels

    positive_counts.append(landslide_pixels)

    if landslide_pixels > 0:
        patches_with_landslide += 1
    else:
        patches_without_landslide += 1


print("=" * 70)
print("LANDSLIDE4SENSE MASK ANALYSIS")
print("=" * 70)

print("Total mask files:", len(files))
print("Total landslide pixels:", total_landslide)
print("Total non-landslide pixels:", total_non_landslide)
print("Patches with landslide:", patches_with_landslide)
print("Patches without landslide:", patches_without_landslide)

positive_patches = [
    x for x in positive_counts
    if x > 0
]

print(
    "Minimum positive pixels in positive patches:",
    min(positive_patches)
)

print(
    "Maximum positive pixels in a patch:",
    max(positive_counts)
)

total_pixels = total_landslide + total_non_landslide

print(
    "Overall landslide percentage:",
    round(total_landslide / total_pixels * 100, 2),
    "%"
)

print("=" * 70)