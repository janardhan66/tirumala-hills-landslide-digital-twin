
from pathlib import Path
import csv
import re
import sys

# Add the project root to Python's import path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import h5py
import numpy as np
import torch
from sklearn.model_selection import train_test_split

from src.models.landslide_segmentation import UNet


# --------------------------------------------------
# 1. Paths and configuration
# --------------------------------------------------


IMAGE_DIR = ROOT / "data" / "raw" / "landslide4sense" / "TrainData" / "img"
MASK_DIR = ROOT / "data" / "raw" / "landslide4sense" / "TrainData" / "mask"
CHECKPOINT = ROOT / "models" / "landslide_unet_14channel_best.pth"

OUTPUT_DIR = ROOT / "outputs" / "validation_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "confidence_slope_threshold_comparison.csv"

BASELINE_THRESHOLD = 0.5
HIGH_SLOPE_QUANTILE = 0.75
SLOPE_THRESHOLDS = [0.6, 0.7]

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# --------------------------------------------------
# 2. Load the same validation split
# --------------------------------------------------
image_files = sorted(str(p) for p in IMAGE_DIR.glob("*.h5"))

if not image_files:
    raise FileNotFoundError(f"No HDF5 images found in {IMAGE_DIR}")

_, val_files = train_test_split(
    image_files,
    test_size=0.20,
    random_state=42,
)

print(f"Device: {DEVICE}")
print(f"Validation patches: {len(val_files)}")


def mask_path_for(image_path):
    match = re.search(r"(\d+)$", Path(image_path).stem)
    if not match:
        raise ValueError(f"Cannot extract sample ID from {image_path}")
    return MASK_DIR / f"mask_{match.group(1)}.h5"


# --------------------------------------------------
# 3. Load model
# --------------------------------------------------
checkpoint = torch.load(CHECKPOINT, map_location=DEVICE)

model = UNet(in_channels=14, out_channels=1).to(DEVICE)

state_dict = (
    checkpoint["model_state_dict"]
    if isinstance(checkpoint, dict)
    and "model_state_dict" in checkpoint
    else checkpoint
)

model.load_state_dict(state_dict, strict=True)
model.eval()


# --------------------------------------------------
# 4. Metric accumulator
# --------------------------------------------------
STRATEGIES = [
    "baseline_0.5",
    "global_0.6",
    "high_slope_0.6",
    "high_slope_0.7",
]

stats = {
    name: {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 0,
        "empty_patches": 0,
        "empty_patches_with_fp": 0,
        "empty_patch_fp_pixels": 0,
        "patches": 0,
    }
    for name in STRATEGIES
}


def update_metrics(name, prediction, truth):
    prediction = prediction.astype(bool)
    truth = truth.astype(bool)

    tp = int(np.count_nonzero(prediction & truth))
    fp = int(np.count_nonzero(prediction & ~truth))
    fn = int(np.count_nonzero(~prediction & truth))
    tn = int(np.count_nonzero(~prediction & ~truth))

    s = stats[name]
    s["tp"] += tp
    s["fp"] += fp
    s["fn"] += fn
    s["tn"] += tn
    s["patches"] += 1

    if not truth.any():
        s["empty_patches"] += 1
        if fp > 0:
            s["empty_patches_with_fp"] += 1
        s["empty_patch_fp_pixels"] += fp


# --------------------------------------------------
# 5. Run inference and compare strategies
# --------------------------------------------------
with torch.inference_mode():
    for index, image_path in enumerate(val_files, start=1):
        image_path = Path(image_path)
        mask_path = mask_path_for(image_path)

        if not mask_path.exists():
            raise FileNotFoundError(f"Missing mask: {mask_path}")

        with h5py.File(image_path, "r") as f:
            image = np.asarray(f["img"], dtype=np.float32)

        with h5py.File(mask_path, "r") as f:
            truth = np.asarray(f["mask"])

        image = np.nan_to_num(
            image, nan=0.0, posinf=0.0, neginf=0.0
        )

        if image.ndim != 3 or image.shape[-1] != 14:
            raise ValueError(
                f"Expected (H, W, 14), got {image.shape} "
                f"for {image_path.name}"
            )

        if truth.ndim == 3 and truth.shape[-1] == 1:
            truth = truth[..., 0]

        truth = truth > 0

        # Channel 12 is the slope channel in the current dataset setup.
        slope = image[..., 12]

        # Match the existing preprocessing: HWC -> CHW.
        x = torch.from_numpy(
            np.ascontiguousarray(image.transpose(2, 0, 1))
        ).unsqueeze(0).to(DEVICE)

        logits = model(x)
        probability = torch.sigmoid(logits)[0, 0].cpu().numpy()

        # Baseline and global-threshold comparisons.
        predictions = {
            "baseline_0.5": probability >= 0.5,
            "global_0.6": probability >= 0.6,
        }

        # Exploratory, within-patch slope-aware thresholds.
        slope_cutoff = np.quantile(slope, HIGH_SLOPE_QUANTILE)
        high_slope = slope >= slope_cutoff

        for threshold in SLOPE_THRESHOLDS:
            predictions[f"high_slope_{threshold:.1f}"] = (
                (probability >= threshold) & high_slope
            ) | (
                (probability >= BASELINE_THRESHOLD) & ~high_slope
            )

        for name, prediction in predictions.items():
            update_metrics(name, prediction, truth)

        if index % 50 == 0 or index == len(val_files):
            print(f"Processed {index}/{len(val_files)} patches")


# --------------------------------------------------
# 6. Summarize results
# --------------------------------------------------
rows = []

for name in STRATEGIES:
    s = stats[name]

    tp, fp, fn, tn = s["tp"], s["fp"], s["fn"], s["tn"]

    dice = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    accuracy = (tp + tn) / (tp + fp + fn + tn)

    empty_fp_rate = (
        s["empty_patches_with_fp"] / s["empty_patches"]
        if s["empty_patches"] else 0
    )

    rows.append({
        "strategy": name,
        "patches": s["patches"],
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "Dice": dice,
        "IoU": iou,
        "Precision": precision,
        "Recall": recall,
        "Accuracy": accuracy,
        "empty_GT_patches": s["empty_patches"],
        "empty_patches_with_FP": s["empty_patches_with_fp"],
        "empty_patch_FP_rate": empty_fp_rate,
        "empty_patch_FP_pixels": s["empty_patch_fp_pixels"],
        "FP_change_vs_baseline": fp - stats["baseline_0.5"]["fp"],
        "TP_change_vs_baseline": tp - stats["baseline_0.5"]["tp"],
    })

with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print("\nEXPERIMENT RESULTS")
print("-" * 90)

for row in rows:
    print(
        f"{row['strategy']:18s} "
        f"Dice={row['Dice']:.5f} "
        f"IoU={row['IoU']:.5f} "
        f"Precision={row['Precision']:.5f} "
        f"Recall={row['Recall']:.5f} "
        f"FP={row['FP']:,} "
        f"TP={row['TP']:,}"
    )

print(f"\nDetailed results saved to:\n{OUTPUT_FILE}")
