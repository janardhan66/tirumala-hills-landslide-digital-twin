import h5py
import numpy as np
from pathlib import Path

import torch

from landslide_segmentation import UNet


# =====================================================
# CONFIGURATION
# =====================================================

MODEL_PATH = Path(
    "models/landslide_unet_14channel_best.pth"
)

INPUT_IMAGE = Path(
    "data/raw/landslide4sense/TrainData/img/image_100.h5"
)

OUTPUT_DIR = Path(
    "outputs/segmentation/upload_test"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
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
# LOAD UPLOADED IMAGE
# =====================================================

print()
print("Input file:", INPUT_IMAGE)

with h5py.File(
    INPUT_IMAGE,
    "r"
) as f:

    image = f["img"][:]


print(
    "Input shape:",
    image.shape
)


# =====================================================
# VALIDATE INPUT
# =====================================================

if image.shape != (128, 128, 14):

    raise ValueError(
        "Invalid input. Expected "
        "(128, 128, 14)."
    )


# =====================================================
# PREPROCESS
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

# Add batch dimension

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
    )


# =====================================================
# NUMPY CONVERSION
# =====================================================

probability_map = (
    probability
    .squeeze()
    .cpu()
    .numpy()
)

prediction_mask = (
    prediction
    .squeeze()
    .cpu()
    .numpy()
)


# =====================================================
# LANDSLIDE STATISTICS
# =====================================================

total_pixels = prediction_mask.size

landslide_pixels = np.sum(
    prediction_mask
)

landslide_percentage = (
    landslide_pixels /
    total_pixels
) * 100


# Average confidence of predicted
# landslide pixels

if landslide_pixels > 0:

    landslide_confidence = (
        probability_map[prediction_mask]
        .mean()
    )

else:

    landslide_confidence = 0.0


# =====================================================
# SAVE NUMERICAL OUTPUTS
# =====================================================

np.save(
    OUTPUT_DIR /
    "landslide_probability.npy",
    probability_map
)

np.save(
    OUTPUT_DIR /
    "landslide_mask.npy",
    prediction_mask.astype(
        np.uint8
    )
)


# =====================================================
# PRINT RESULTS
# =====================================================

print()
print("=" * 60)
print("UPLOADED IMAGE PREDICTION")
print("=" * 60)

print()

print(
    "Total pixels:",
    total_pixels
)

print(
    "Predicted landslide pixels:",
    landslide_pixels
)

print(
    "Predicted landslide area:",
    f"{landslide_percentage:.2f}%"
)

print(
    "Average landslide confidence:",
    f"{landslide_confidence:.4f}"
)

print()

print(
    "Probability range:",
    f"{probability_map.min():.4f}",
    "to",
    f"{probability_map.max():.4f}"
)

print()

print("Saved:")

print(
    OUTPUT_DIR /
    "landslide_probability.npy"
)

print(
    OUTPUT_DIR /
    "landslide_mask.npy"
)

print()
print("=" * 60)
print("PREDICTION COMPLETED")
print("=" * 60)