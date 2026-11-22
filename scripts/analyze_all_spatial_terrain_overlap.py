
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
required = {"sample_id", "gt_pixels", "t0.5_pred_pixels"}
missing = required - set(errors.columns)

if missing:
    raise ValueError(f"Missing columns in errors CSV: {missing}")

errors["sample_id"] = (
    errors["sample_id"].astype(str).str.replace(r"\.0$", "", regex=True)
)

# Analyze only empty-ground-truth patches.
empty = errors[errors["gt_pixels"] == 0].copy()
empty["group"] = np.where(
    empty["t0.5_pred_pixels"] > 0,
    "False positive",
    "Correctly empty",
)

print("Patch counts:")
print(empty["group"].value_counts().to_string())

checkpoint = torch.load(
    CHECKPOINT_PATH, map_location="cpu", weights_only=False
)
model = UNet()
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

records = []

for _, row in empty.iterrows():
    sample_id = row["sample_id"]
    image_path = IMAGE_DIR / f"image_{sample_id}.h5"
    mask_path = MASK_DIR / f"mask_{sample_id}.h5"

    with h5py.File(image_path, "r") as f:
        image = f["img"][:]

    with h5py.File(mask_path, "r") as f:
        ground_truth = f["mask"][:] > 0

    if image.shape != (128, 128, 14):
        raise ValueError(f"Unexpected shape for {sample_id}: {image.shape}")

    image = np.nan_to_num(image.astype(np.float32))
    tensor = torch.from_numpy(
        image.transpose(2, 0, 1).copy()
    ).unsqueeze(0)

    with torch.inference_mode():
        probabilities = torch.sigmoid(model(tensor))[0, 0].numpy()

    prediction = probabilities >= THRESHOLD
    predicted_count = int(prediction.sum())
    recorded_count = int(row["t0.5_pred_pixels"])

    if predicted_count != recorded_count:
        raise ValueError(
            f"Prediction mismatch for {sample_id}: "
            f"recomputed={predicted_count}, recorded={recorded_count}"
        )

    if ground_truth.any():
        raise ValueError(f"Expected empty ground truth for {sample_id}")

    for channel, feature in CHANNELS:
        values = image[:, :, channel].astype(np.float64)
        q25, q50, q75 = np.percentile(values, [25, 50, 75])
        quartile_map = np.digitize(
            values, [q25, q50, q75], right=False
        ) + 1

        for quartile in range(1, 5):
            region = quartile_map == quartile
            area_count = int(region.sum())
            overlap_count = int(np.sum(prediction & region))

            records.append({
                "sample_id": sample_id,
                "group": row["group"],
                "feature": feature,
                "quartile": quartile,
                "predicted_pixels_total": predicted_count,
                "pixels_in_quartile": area_count,
                "predicted_pixels_in_quartile": overlap_count,
                "share_of_predictions_pct": (
                    100 * overlap_count / predicted_count
                    if predicted_count else np.nan
                ),
                "quartile_area_pct": 100 * area_count / values.size,
                "prediction_rate_in_quartile_pct": (
                    100 * overlap_count / area_count
                    if area_count else np.nan
                ),
                "enrichment_ratio": (
                    (overlap_count / predicted_count)
                    / (area_count / values.size)
                    if predicted_count and area_count else np.nan
                ),
            })

detail = pd.DataFrame(records)
detail_path = OUTPUT_DIR / "all_spatial_terrain_overlap_detail.csv"
detail.to_csv(detail_path, index=False)

# First average within each patch, then summarize across patches.
# This avoids treating every pixel as an independent observation.
summary = (
    detail.groupby(["group", "feature", "quartile"])
    .agg(
        patch_count=("sample_id", "nunique"),
        mean_prediction_share_pct=("share_of_predictions_pct", "mean"),
        median_prediction_share_pct=("share_of_predictions_pct", "median"),
        mean_enrichment=("enrichment_ratio", "mean"),
        median_enrichment=("enrichment_ratio", "median"),
        mean_prediction_rate_pct=("prediction_rate_in_quartile_pct", "mean"),
    )
    .reset_index()
)

summary_path = OUTPUT_DIR / "all_spatial_terrain_overlap_summary.csv"
summary.to_csv(summary_path, index=False)

print("\nSpatial overlap summary:")
print(summary.round(3).to_string(index=False))
print(f"\nDetailed results: {detail_path}")
print(f"Group summary:   {summary_path}")
print(
    "\nEnrichment above 1 means predictions are overrepresented in a "
    "quartile relative to its area. These descriptive comparisons "
    "do not establish causation."
)
