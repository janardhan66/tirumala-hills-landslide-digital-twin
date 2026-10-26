import h5py
import numpy as np
import torch
from pathlib import Path

from landslide_segmentation import UNet


# =====================================================
# PATHS
# =====================================================

MODEL_PATH = Path(
    "models/landslide_unet_14channel_best.pth"
)

IMAGE_PATH = Path(
    "data/raw/landslide4sense/TrainData/img/image_100.h5"
)

MASK_PATH = Path(
    "data/raw/landslide4sense/TrainData/mask/mask_100.h5"
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

print("Model loaded successfully.")


# =====================================================
# LOAD IMAGE
# =====================================================

with h5py.File(
    IMAGE_PATH,
    "r"
) as f:

    image = f["img"][:]


# =====================================================
# LOAD REAL MASK
# =====================================================

with h5py.File(
    MASK_PATH,
    "r"
) as f:

    true_mask = f["mask"][:]


print(
    "Image shape:",
    image.shape
)

print(
    "True mask shape:",
    true_mask.shape
)


# =====================================================
# PREPROCESS IMAGE
# =====================================================

image = np.nan_to_num(
    image,
    nan=0.0,
    posinf=0.0,
    neginf=0.0
)

image = image.astype(
    np.float32
)

# HWC -> CHW
image = np.transpose(
    image,
    (2, 0, 1)
)

image_tensor = torch.from_numpy(
    image
).unsqueeze(0)

image_tensor = image_tensor.to(
    device
)


# =====================================================
# PREDICTION
# =====================================================

with torch.no_grad():

    output = model(
        image_tensor
    )

    probability = torch.sigmoid(
        output
    )

    prediction = (
        probability >= 0.5
    ).cpu().numpy().squeeze()


# =====================================================
# CONVERT TRUE MASK
# =====================================================

true_mask = (
    true_mask == 1
)


prediction = (
    prediction == 1
)


# =====================================================
# CONFUSION VALUES
# =====================================================

true_positive = np.logical_and(
    prediction,
    true_mask
).sum()

false_positive = np.logical_and(
    prediction,
    ~true_mask
).sum()

false_negative = np.logical_and(
    ~prediction,
    true_mask
).sum()

true_negative = np.logical_and(
    ~prediction,
    ~true_mask
).sum()


# =====================================================
# METRICS
# =====================================================

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

accuracy = (
    true_positive
    +
    true_negative
) / (
    true_positive
    +
    true_negative
    +
    false_positive
    +
    false_negative
)


# =====================================================
# AREA COMPARISON
# =====================================================

total_pixels = true_mask.size

actual_landslide_pixels = (
    true_mask.sum()
)

predicted_landslide_pixels = (
    prediction.sum()
)

actual_percentage = (
    actual_landslide_pixels
    /
    total_pixels
) * 100

predicted_percentage = (
    predicted_landslide_pixels
    /
    total_pixels
) * 100


# =====================================================
# RESULTS
# =====================================================

print()
print("=" * 60)
print("IMAGE 100 EVALUATION")
print("=" * 60)

print(
    "True Positive:",
    true_positive
)

print(
    "False Positive:",
    false_positive
)

print(
    "False Negative:",
    false_negative
)

print(
    "True Negative:",
    true_negative
)

print()

print(
    "Accuracy:",
    f"{accuracy:.4f}"
)

print(
    "Precision:",
    f"{precision:.4f}"
)

print(
    "Recall:",
    f"{recall:.4f}"
)

print(
    "Dice:",
    f"{dice:.4f}"
)

print(
    "IoU:",
    f"{iou:.4f}"
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
print("EVALUATION COMPLETED")
print("=" * 60)