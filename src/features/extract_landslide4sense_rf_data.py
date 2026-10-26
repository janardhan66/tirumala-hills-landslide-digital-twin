import h5py
import glob
import numpy as np
import pandas as pd
import os

IMAGE_DIR = "data/raw/landslide4sense/TrainData/img"
MASK_DIR = "data/raw/landslide4sense/TrainData/mask"

OUTPUT_FILE = "data/features/landslide4sense_rf_training_v3.csv"

TOTAL_LANDSLIDE = 100000
TOTAL_NON_LANDSLIDE = 100000

rng = np.random.default_rng(42)

image_files = sorted(
    glob.glob(os.path.join(IMAGE_DIR, "image_*.h5")),
    key=lambda x: int(
        os.path.basename(x).split("_")[1].split(".")[0]
    )
)

print("=" * 70)
print("CREATING PATCH-DISTRIBUTED LANDSLIDE4SENSE DATASET")
print("=" * 70)
print("Total patches:", len(image_files))

# ---------------------------------------------------------
# First pass: count available pixels in each patch
# ---------------------------------------------------------

patch_info = []

for index, image_file in enumerate(image_files):

    image_id = int(
        os.path.basename(image_file)
        .split("_")[1]
        .split(".")[0]
    )

    mask_file = os.path.join(
        MASK_DIR,
        f"mask_{image_id}.h5"
    )

    with h5py.File(mask_file, "r") as f:
        mask = f["mask"][:]

    landslide_count = int((mask == 1).sum())
    non_landslide_count = int((mask == 0).sum())

    patch_info.append(
        [
            image_id,
            landslide_count,
            non_landslide_count
        ]
    )

patch_info = pd.DataFrame(
    patch_info,
    columns=[
        "patch_id",
        "landslide_count",
        "non_landslide_count"
    ]
)

# ---------------------------------------------------------
# Select patches randomly
# ---------------------------------------------------------
positive_patches = patch_info[
    patch_info["landslide_count"] > 0
]["patch_id"].values.copy()

all_patches = patch_info["patch_id"].values.copy()

rng.shuffle(positive_patches)
rng.shuffle(all_patches)

print("Patches containing landslides:", len(positive_patches))
print("Total patches:", len(all_patches))

# ---------------------------------------------------------
# Calculate samples per patch
# ---------------------------------------------------------

positive_per_patch = max(
    1,
    TOTAL_LANDSLIDE // len(positive_patches)
)

negative_per_patch = max(
    1,
    TOTAL_NON_LANDSLIDE // len(all_patches)
)

print("Target landslide samples per patch:", positive_per_patch)
print("Target non-landslide samples per patch:", negative_per_patch)

# ---------------------------------------------------------
# Second pass: extract samples
# ---------------------------------------------------------

landslide_samples = []
non_landslide_samples = []

for index, image_id in enumerate(all_patches):

    if (
        len(landslide_samples) >= TOTAL_LANDSLIDE
        and len(non_landslide_samples) >= TOTAL_NON_LANDSLIDE
    ):
        break

    image_file = os.path.join(
        IMAGE_DIR,
        f"image_{image_id}.h5"
    )

    mask_file = os.path.join(
        MASK_DIR,
        f"mask_{image_id}.h5"
    )

    with h5py.File(image_file, "r") as f:
        image = f["img"][:]

    with h5py.File(mask_file, "r") as f:
        mask = f["mask"][:]

    slope = image[:, :, 12]
    elevation = image[:, :, 13]

    # -------------------------------
    # Landslide samples
    # -------------------------------

    if len(landslide_samples) < TOTAL_LANDSLIDE:

        positions = np.argwhere(mask == 1)

        if len(positions) > 0:

            remaining = min(
                positive_per_patch,
                TOTAL_LANDSLIDE - len(landslide_samples)
            )

            if len(positions) > remaining:
                selected = rng.choice(
                    len(positions),
                    size=remaining,
                    replace=False
                )
                positions = positions[selected]

            for row, col in positions:
                landslide_samples.append(
                    [
                        image_id,
                        float(slope[row, col]),
                        float(elevation[row, col]),
                        1
                    ]
                )

    # -------------------------------
    # Non-landslide samples
    # -------------------------------

    if len(non_landslide_samples) < TOTAL_NON_LANDSLIDE:

        positions = np.argwhere(mask == 0)

        remaining = min(
            negative_per_patch,
            TOTAL_NON_LANDSLIDE - len(non_landslide_samples)
        )

        if len(positions) > remaining:
            selected = rng.choice(
                len(positions),
                size=remaining,
                replace=False
            )
            positions = positions[selected]

        for row, col in positions:
            non_landslide_samples.append(
                [
                    image_id,
                    float(slope[row, col]),
                    float(elevation[row, col]),
                    0
                ]
            )

    if (index + 1) % 250 == 0:
        print(
            f"Processed {index + 1}/{len(all_patches)} patches "
            f"| Landslide: {len(landslide_samples)} "
            f"| Non-landslide: {len(non_landslide_samples)}"
        )


# ---------------------------------------------------------
# Create dataframe
# ---------------------------------------------------------

data = landslide_samples + non_landslide_samples

df = pd.DataFrame(
    data,
    columns=[
        "patch_id",
        "slope",
        "elevation",
        "label"
    ]
)

df = df.sample(
    frac=1,
    random_state=42
).reset_index(drop=True)

os.makedirs(
    os.path.dirname(OUTPUT_FILE),
    exist_ok=True
)

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print()
print("=" * 70)
print("PATCH-DISTRIBUTED DATASET CREATED")
print("=" * 70)

print("Rows:", len(df))
print("Columns:", list(df.columns))
print("Unique patches:", df["patch_id"].nunique())

print()
print("Class distribution:")
print(df["label"].value_counts())

print()
print("Landslide samples:", (df["label"] == 1).sum())
print("Non-landslide samples:", (df["label"] == 0).sum())

print()
print("Saved:", OUTPUT_FILE)

print("=" * 70)