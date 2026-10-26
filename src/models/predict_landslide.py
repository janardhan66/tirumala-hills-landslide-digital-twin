import h5py
import numpy as np
from pathlib import Path

import torch
import matplotlib.pyplot as plt

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

OUTPUT_DIR = Path(
    "outputs/segmentation"
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
# LOAD IMAGE
# =====================================================

with h5py.File(
    IMAGE_PATH,
    "r"
) as f:

    image = f["img"][:]


print(
    "Original image shape:",
    image.shape
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
    ).float()


# =====================================================
# CONVERT TO NUMPY
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
# STATISTICS
# =====================================================

total_pixels = prediction_mask.size

landslide_pixels = np.sum(
    prediction_mask == 1
)

landslide_percentage = (
    landslide_pixels /
    total_pixels
) * 100


print()
print(
    "Prediction completed."
)

print(
    "Prediction shape:",
    prediction_mask.shape
)

print(
    "Predicted landslide pixels:",
    landslide_pixels
)

print(
    "Total pixels:",
    total_pixels
)

print(
    "Predicted landslide percentage:",
    f"{landslide_percentage:.2f}%"
)


# =====================================================
# SAVE BINARY MASK
# =====================================================

mask_path = (
    OUTPUT_DIR /
    "landslide_prediction_mask.png"
)

plt.imsave(
    mask_path,
    prediction_mask,
    cmap="gray"
)


# =====================================================
# SAVE PROBABILITY MAP
# =====================================================

probability_path = (
    OUTPUT_DIR /
    "landslide_probability_map.png"
)

plt.imsave(
    probability_path,
    probability_map,
    cmap="viridis"
)


# =====================================================
# CREATE OVERLAY
# =====================================================

# Use Sentinel-2 RGB-like channels:
# B4, B3, B2 = channels 3, 2, 1

rgb = image[
    [3, 2, 1],
    :, :
]

# Normalize RGB for display
rgb_min = np.percentile(
    rgb,
    2
)

rgb_max = np.percentile(
    rgb,
    98
)

rgb = (
    rgb - rgb_min
) / (
    rgb_max - rgb_min + 1e-8
)

rgb = np.clip(
    rgb,
    0,
    1
)

rgb = np.transpose(
    rgb,
    (1, 2, 0)
)


# Create overlay
overlay = rgb.copy()

landslide_area = (
    prediction_mask == 1
)

# Highlight predicted landslide
overlay[landslide_area, 0] = 1.0
overlay[landslide_area, 1] *= 0.3
overlay[landslide_area, 2] *= 0.3


overlay_path = (
    OUTPUT_DIR /
    "landslide_prediction_overlay.png"
)

plt.imsave(
    overlay_path,
    overlay
)


# =====================================================
# FINISHED
# =====================================================

print()
print("Saved files:")

print(
    mask_path
)

print(
    probability_path
)

print(
    overlay_path
)

print()
print("=" * 60)
print("LANDSLIDE PREDICTION COMPLETED")
print("=" * 60)