import h5py
import numpy as np
import torch
from pathlib import Path

from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split

from landslide_segmentation import (
    Landslide4SenseDataset,
    UNet
)


# =====================================================
# PATHS
# =====================================================

MODEL_PATH = Path(
    "models/landslide_unet_14channel_best.pth"
)

IMAGE_DIR = Path(
    "data/raw/landslide4sense/TrainData/img"
)


# =====================================================
# DEVICE
# =====================================================

device = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)

print("Device:", device)


# =====================================================
# LOAD ALL IMAGE FILES
# =====================================================

image_files = sorted(
    str(x)
    for x in IMAGE_DIR.glob("*.h5")
)

print(
    "Total patches:",
    len(image_files)
)


# =====================================================
# SAME VALIDATION SPLIT
# =====================================================

train_files, val_files = train_test_split(
    image_files,
    test_size=0.20,
    random_state=42
)

print(
    "Validation patches:",
    len(val_files)
)


# =====================================================
# VALIDATION DATASET
# =====================================================

val_dataset = Landslide4SenseDataset(
    val_files
)

val_loader = DataLoader(
    val_dataset,
    batch_size=4,
    shuffle=False,
    num_workers=0
)

print(
    "Validation batches:",
    len(val_loader)
)


# =====================================================
# LOAD MODEL
# =====================================================

model = UNet(
    in_channels=14,
    out_channels=1
)

checkpoint = torch.load(
    MODEL_PATH,
    map_location=device
)

model.load_state_dict(
    checkpoint["model_state_dict"]
)

model = model.to(device)

model.eval()

print("Best model loaded successfully.")


# =====================================================
# GLOBAL CONFUSION MATRIX
# =====================================================

true_positive = 0
false_positive = 0
false_negative = 0
true_negative = 0


# =====================================================
# VALIDATION
# =====================================================

print()
print("Starting full validation...")
print()


with torch.no_grad():

    for batch_index, (
        images,
        masks
    ) in enumerate(val_loader):

        images = images.to(device)
        masks = masks.to(device)

        outputs = model(images)

        probabilities = torch.sigmoid(
            outputs
        )

        predictions = (
            probabilities >= 0.5
        )

        targets = (
            masks >= 0.5
        )

        true_positive += torch.logical_and(
            predictions,
            targets
        ).sum().item()

        false_positive += torch.logical_and(
            predictions,
            ~targets
        ).sum().item()

        false_negative += torch.logical_and(
            ~predictions,
            targets
        ).sum().item()

        true_negative += torch.logical_and(
            ~predictions,
            ~targets
        ).sum().item()

        if (
            batch_index + 1
        ) % 25 == 0:

            print(
                f"Validated batch "
                f"{batch_index + 1}/"
                f"{len(val_loader)}"
            )


# =====================================================
# METRICS
# =====================================================

total = (
    true_positive
    +
    false_positive
    +
    false_negative
    +
    true_negative
)

precision = (
    true_positive
    /
    (
        true_positive
        +
        false_positive
        +
        1e-8
    )
)

recall = (
    true_positive
    /
    (
        true_positive
        +
        false_negative
        +
        1e-8
    )
)

dice = (
    2 * true_positive
    /
    (
        2 * true_positive
        +
        false_positive
        +
        false_negative
        +
        1e-8
    )
)

iou = (
    true_positive
    /
    (
        true_positive
        +
        false_positive
        +
        false_negative
        +
        1e-8
    )
)

accuracy = (
    true_positive
    +
    true_negative
) / total


# =====================================================
# PIXEL COUNTS
# =====================================================

actual_landslide_pixels = (
    true_positive
    +
    false_negative
)

predicted_landslide_pixels = (
    true_positive
    +
    false_positive
)

actual_percentage = (
    actual_landslide_pixels
    /
    total
) * 100

predicted_percentage = (
    predicted_landslide_pixels
    /
    total
) * 100


# =====================================================
# RESULTS
# =====================================================

print()
print("=" * 60)
print("FULL VALIDATION RESULTS")
print("=" * 60)

print()
print("Confusion Matrix:")
print(
    f"True Positive:  {true_positive}"
)

print(
    f"False Positive: {false_positive}"
)

print(
    f"False Negative: {false_negative}"
)

print(
    f"True Negative:  {true_negative}"
)

print()

print(
    f"Accuracy:  {accuracy:.4f}"
)

print(
    f"Precision: {precision:.4f}"
)

print(
    f"Recall:    {recall:.4f}"
)

print(
    f"Dice:      {dice:.4f}"
)

print(
    f"IoU:       {iou:.4f}"
)

print()

print(
    "Actual landslide pixels:",
    actual_landslide_pixels
)

print(
    "Predicted landslide pixels:",
    predicted_landslide_pixels
)

print(
    "Actual landslide percentage:",
    f"{actual_percentage:.2f}%"
)

print(
    "Predicted landslide percentage:",
    f"{predicted_percentage:.2f}%"
)

print()
print("=" * 60)
print("FULL VALIDATION COMPLETED")
print("=" * 60)