
from pathlib import Path
import sys
import h5py

# Add the project root to Python's module search path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split

# Run from the project root:
# python scripts/diagnose_slope_suppression.py

IMAGE_DIR = ROOT / "data/raw/landslide4sense/TrainData/img"
MASK_DIR = ROOT / "data/raw/landslide4sense/TrainData/mask"
CHECKPOINT = ROOT / "models/landslide_unet_14channel_best.pth"
OUTPUT_DIR = ROOT / "outputs/validation_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

THRESHOLD = 0.5
SLOPE_CHANNEL = 12


# ---------------------------------------------------------
# IMPORTANT:
# Replace this import/initialization with the exact model
# loading code from your working validate_landslide_model.py.
# ---------------------------------------------------------
from src.models.landslide_segmentation import UNet

device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

checkpoint = torch.load(
    CHECKPOINT,
    map_location=device,
)

model = UNet(
    in_channels=14,
    out_channels=1,
).to(device)

state_dict = (
    checkpoint["model_state_dict"]
    if isinstance(checkpoint, dict)
    and "model_state_dict" in checkpoint
    else checkpoint
)

model.load_state_dict(state_dict, strict=True)
model.eval()

def read_h5(path, key):
    with h5py.File(path, "r") as f:
        return np.asarray(f[key])

def get_numeric_id(path):
    return int(path.stem.split("_")[-1])

images = sorted(IMAGE_DIR.glob("*.h5"))
masks_by_id = {get_numeric_id(p): p for p in MASK_DIR.glob("*.h5")}

# Match the split used by the original validation script.
images = sorted(IMAGE_DIR.glob("*.h5"), key=lambda p: str(p))

_, val_files = train_test_split(
    images,
    test_size=0.20,
    random_state=42,
)

missing_masks = [
    p for p in val_files
    if get_numeric_id(p) not in masks_by_id
]

if missing_masks:
    raise FileNotFoundError(
        f"Missing masks for validation images: {missing_masks[:5]}"
    )

totals = {
    "baseline": {"TP": 0, "FP": 0, "FN": 0, "TN": 0},
    "slope_q4_suppressed": {"TP": 0, "FP": 0, "FN": 0, "TN": 0},
}
fp_removed = 0
tp_lost = 0
predicted_pixels_removed = 0
empty_gt_fp_before = 0
empty_gt_fp_after = 0
patches = 0

def add_counts(store, pred, gt):
    store["TP"] += int(np.logical_and(pred, gt).sum())
    store["FP"] += int(np.logical_and(pred, ~gt).sum())
    store["FN"] += int(np.logical_and(~pred, gt).sum())
    store["TN"] += int(np.logical_and(~pred, ~gt).sum())

def metrics(c):
    tp, fp, fn, tn = c["TP"], c["FP"], c["FN"], c["TN"]
    dice = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0
    iou = tp / (tp + fp + fn) if (tp + fp + fn) else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    accuracy = (tp + tn) / (tp + fp + fn + tn)
    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "Dice": dice, "IoU": iou,
        "Precision": precision, "Recall": recall,
        "Accuracy": accuracy,
    }

with torch.no_grad():
    for image_path in val_files:
        sample_id = get_numeric_id(image_path)
        mask_path = masks_by_id[sample_id]

        image = read_h5(image_path, "img").astype(np.float32)
        gt = read_h5(mask_path, "mask") > 0

        image = np.nan_to_num(image, nan=0.0, posinf=0.0, neginf=0.0)

        # Original model input: HWC -> CHW -> batch dimension.
        x = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).to(device)
        logits = model(x)
        if isinstance(logits, (tuple, list)):
            logits = logits[0]
        probabilities = torch.sigmoid(logits).squeeze().cpu().numpy()
        baseline = probabilities >= THRESHOLD

        # Rank slope values within this patch into four groups.
        slope = image[:, :, SLOPE_CHANNEL]
        valid = np.isfinite(slope)
        q4 = np.zeros(slope.shape, dtype=bool)

        if valid.any():
            cutoff = np.quantile(slope[valid], 0.75)
            q4 = valid & (slope >= cutoff)

        # Diagnostic only: remove predictions in the highest
        # within-patch slope quartile.
        suppressed = baseline & ~q4

        add_counts(totals["baseline"], baseline, gt)
        add_counts(totals["slope_q4_suppressed"], suppressed, gt)

        removed = baseline & q4
        predicted_pixels_removed += int(removed.sum())
        fp_removed += int(np.logical_and(removed, ~gt).sum())
        tp_lost += int(np.logical_and(removed, gt).sum())

        if not gt.any():
            empty_gt_fp_before += int(baseline.sum())
            empty_gt_fp_after += int(suppressed.sum())

        patches += 1

baseline_metrics = metrics(totals["baseline"])
suppressed_metrics = metrics(totals["slope_q4_suppressed"])

summary = pd.DataFrame([
    {"Scenario": "Baseline threshold 0.5", **baseline_metrics},
    {"Scenario": "Suppress predictions in slope Q4", **suppressed_metrics},
])

summary.to_csv(OUTPUT_DIR / "slope_suppression_metrics.csv", index=False)

tradeoff = pd.DataFrame([{
    "Validation_patches": patches,
    "Threshold": THRESHOLD,
    "Predicted_pixels_removed": predicted_pixels_removed,
    "False_positive_pixels_removed": fp_removed,
    "True_positive_pixels_lost": tp_lost,
    "Empty_GT_FP_pixels_before": empty_gt_fp_before,
    "Empty_GT_FP_pixels_after": empty_gt_fp_after,
    "FP_pixel_reduction_percent": (
        100 * fp_removed / totals["baseline"]["FP"]
        if totals["baseline"]["FP"] else 0
    ),
    "TP_pixel_loss_percent": (
        100 * tp_lost / totals["baseline"]["TP"]
        if totals["baseline"]["TP"] else 0
    ),
}])
tradeoff.to_csv(OUTPUT_DIR / "slope_suppression_tradeoff.csv", index=False)

print("\n=== PIXEL-LEVEL METRICS ===")
print(summary.to_string(index=False, float_format=lambda v: f"{v:.5f}"))

print("\n=== FALSE-POSITIVE / TRUE-POSITIVE TRADE-OFF ===")
print(tradeoff.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

print(f"\nResults saved in: {OUTPUT_DIR}")
