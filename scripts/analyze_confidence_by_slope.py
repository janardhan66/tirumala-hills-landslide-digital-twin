
from pathlib import Path
import csv
import re
import sys

import h5py
import numpy as np
import torch
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.models.landslide_segmentation import UNet

IMAGE_DIR = ROOT / "data/raw/landslide4sense/TrainData/img"
MASK_DIR = ROOT / "data/raw/landslide4sense/TrainData/mask"
CHECKPOINT = ROOT / "models/landslide_unet_14channel_best.pth"
OUT_DIR = ROOT / "outputs/validation_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FILE = OUT_DIR / "confidence_by_slope_quartile.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Confidence bands are diagnostic bins, not calibrated probabilities.
CONFIDENCE_EDGES = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.000001]

image_files = sorted(str(p) for p in IMAGE_DIR.glob("*.h5"))
if not image_files:
    raise FileNotFoundError(f"No images found: {IMAGE_DIR}")

_, val_files = train_test_split(
    image_files, test_size=0.20, random_state=42
)

checkpoint = torch.load(CHECKPOINT, map_location=DEVICE)
model = UNet(in_channels=14, out_channels=1).to(DEVICE)
state = (
    checkpoint["model_state_dict"]
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint
    else checkpoint
)
model.load_state_dict(state, strict=True)
model.eval()

# Each cell counts TP, FP, FN and TN pixels.
counts = {
    (q, b): {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    for q in range(1, 5)
    for b in range(len(CONFIDENCE_EDGES) - 1)
}


def get_mask_path(image_path):
    match = re.search(r"(\d+)$", Path(image_path).stem)
    if not match:
        raise ValueError(f"Cannot extract sample ID: {image_path}")
    return MASK_DIR / f"mask_{match.group(1)}.h5"


with torch.inference_mode():
    for i, image_path in enumerate(val_files, 1):
        mask_path = get_mask_path(image_path)
        if not mask_path.exists():
            raise FileNotFoundError(mask_path)

        with h5py.File(image_path, "r") as f:
            image = np.asarray(f["img"], dtype=np.float32)

        with h5py.File(mask_path, "r") as f:
            truth = np.asarray(f["mask"])

        if image.ndim != 3 or image.shape[-1] != 14:
            raise ValueError(f"Unexpected image shape: {image.shape}")

        if truth.ndim == 3 and truth.shape[-1] == 1:
            truth = truth[..., 0]

        image = np.nan_to_num(
            image, nan=0.0, posinf=0.0, neginf=0.0
        )
        truth = truth > 0
        slope = image[..., 12]

        x = torch.from_numpy(
            np.ascontiguousarray(image.transpose(2, 0, 1))
        ).unsqueeze(0).to(DEVICE)

        probability = torch.sigmoid(model(x))[0, 0].cpu().numpy()
        predicted = probability >= 0.5

        # Relative slope quartiles within each patch.
        q_edges = np.quantile(slope, [0.25, 0.50, 0.75])
        slope_quartile = (
            1
            + (slope > q_edges[0]).astype(np.int8)
            + (slope > q_edges[1]).astype(np.int8)
            + (slope > q_edges[2]).astype(np.int8)
        )

        confidence_bin = (
            np.digitize(probability, CONFIDENCE_EDGES[1:-1], right=False)
        )

        for q in range(1, 5):
            for b in range(len(CONFIDENCE_EDGES) - 1):
                cell = (slope_quartile == q) & (confidence_bin == b)
                if not cell.any():
                    continue

                y = truth[cell]
                p = predicted[cell]

                c = counts[(q, b)]
                c["TP"] += int(np.count_nonzero(p & y))
                c["FP"] += int(np.count_nonzero(p & ~y))
                c["FN"] += int(np.count_nonzero(~p & y))
                c["TN"] += int(np.count_nonzero(~p & ~y))

        if i % 100 == 0 or i == len(val_files):
            print(f"Processed {i}/{len(val_files)} patches")

with OUT_FILE.open("w", newline="", encoding="utf-8") as f:
    fields = [
        "slope_quartile", "confidence_lower", "confidence_upper",
        "TP", "FP", "FN", "TN", "predicted_pixels",
        "false_discovery_rate",
    ]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for (q, b), c in sorted(counts.items()):
        tp, fp = c["TP"], c["FP"]
        predicted_pixels = tp + fp

        writer.writerow({
            "slope_quartile": q,
            "confidence_lower": CONFIDENCE_EDGES[b],
            "confidence_upper": CONFIDENCE_EDGES[b + 1],
            **c,
            "predicted_pixels": predicted_pixels,
            "false_discovery_rate": (
                fp / predicted_pixels if predicted_pixels else 0
            ),
        })

print(f"\nSaved diagnostic results to:\n{OUT_FILE}")
