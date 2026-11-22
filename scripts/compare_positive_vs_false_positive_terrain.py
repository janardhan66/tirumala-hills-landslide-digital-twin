
from pathlib import Path
import sys

import h5py
import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data/raw/landslide4sense/TrainData/img"
MASK_DIR = ROOT / "data/raw/landslide4sense/TrainData/mask"
ERRORS_FILE = ROOT / "outputs/validation_analysis/per_image_errors.csv"
OUTPUT_DIR = ROOT / "outputs/validation_analysis"
CHECKPOINT_PATH = ROOT / "models/landslide_unet_14channel_best.pth"

THRESHOLD = 0.5
CHANNELS = [(12, "slope"), (13, "dem")]

sys.path.insert(0, str(ROOT))
from src.models.landslide_segmentation import UNet

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

errors = pd.read_csv(ERRORS_FILE)
errors["sample_id"] = (
    errors["sample_id"].astype(str).str.replace(r"\.0$", "", regex=True)
)

checkpoint = torch.load(
    CHECKPOINT_PATH, map_location="cpu", weights_only=False
)
model = UNet()
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

records = []

for _, row in errors.iterrows():
    sample_id = row["sample_id"]
    image_path = IMAGE_DIR / f"image_{sample_id}.h5"
    mask_path = MASK_DIR / f"mask_{sample_id}.h5"

    with h5py.File(image_path, "r") as f:
        image = f["img"][:]

    with h5py.File(mask_path, "r") as f:
        gt = f["mask"][:] > 0

    image = np.nan_to_num(image.astype(np.float32))
    tensor = torch.from_numpy(
        image.transpose(2, 0, 1).copy()
    ).unsqueeze(0)

    with torch.inference_mode():
        probabilities = torch.sigmoid(model(tensor))[0, 0].numpy()

    prediction = probabilities >= THRESHOLD
    gt_count = int(gt.sum())
    pred_count = int(prediction.sum())

    if pred_count != int(row["t0.5_pred_pixels"]):
        raise ValueError(f"Prediction count mismatch: {sample_id}")

    group = "Positive GT" if gt_count > 0 else (
        "False positive" if pred_count > 0 else "Correctly empty"
    )

    for channel, feature in CHANNELS:
        values = image[:, :, channel].astype(np.float64)
        q25, q50, q75 = np.percentile(values, [25, 50, 75])
        quartiles = np.digitize(
            values, [q25, q50, q75], right=False
        ) + 1

        for q in range(1, 5):
            region = quartiles == q
            region_count = int(region.sum())

            pred_in_region = int(np.sum(prediction & region))
            gt_in_region = int(np.sum(gt & region))

            records.append({
                "sample_id": sample_id,
                "group": group,
                "feature": feature,
                "quartile": q,
                "gt_pixels": gt_count,
                "pred_pixels": pred_count,
                "prediction_share_pct": (
                    100 * pred_in_region / pred_count
                    if pred_count else np.nan
                ),
                "gt_share_pct": (
                    100 * gt_in_region / gt_count
                    if gt_count else np.nan
                ),
                "prediction_rate_pct": (
                    100 * pred_in_region / region_count
                    if region_count else np.nan
                ),
                "gt_rate_pct": (
                    100 * gt_in_region / region_count
                    if region_count else np.nan
                ),
            })

detail = pd.DataFrame(records)

detail_path = OUTPUT_DIR / "positive_vs_false_positive_terrain_detail.csv"
detail.to_csv(detail_path, index=False)

# Summarize by patch first, then by group.
summary = (
    detail.groupby(["group", "feature", "quartile"])
    .agg(
        patch_count=("sample_id", "nunique"),
        mean_prediction_share_pct=("prediction_share_pct", "mean"),
        median_prediction_share_pct=("prediction_share_pct", "median"),
        mean_gt_share_pct=("gt_share_pct", "mean"),
        mean_prediction_rate_pct=("prediction_rate_pct", "mean"),
        mean_gt_rate_pct=("gt_rate_pct", "mean"),
    )
    .reset_index()
)

summary_path = OUTPUT_DIR / "positive_vs_false_positive_terrain_summary.csv"
summary.to_csv(summary_path, index=False)

print("\nPatch groups:")
print(errors.assign(
    group=np.where(
        errors["gt_pixels"] > 0, "Positive GT",
        np.where(errors["t0.5_pred_pixels"] > 0,
                 "False positive", "Correctly empty")
    )
)["group"].value_counts().to_string())

print("\nTerrain quartile comparison:")
print(summary.round(3).to_string(index=False))
print(f"\nDetailed results: {detail_path}")
print(f"Summary results: {summary_path}")
