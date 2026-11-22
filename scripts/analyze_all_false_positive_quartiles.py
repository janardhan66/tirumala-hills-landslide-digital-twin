
from pathlib import Path
import h5py
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data/raw/landslide4sense/TrainData/img"
ERRORS_FILE = ROOT / "outputs/validation_analysis/per_image_errors.csv"
OUTPUT_DIR = ROOT / "outputs/validation_analysis"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

errors = pd.read_csv(ERRORS_FILE)

required = {"sample_id", "gt_pixels", "t0.5_pred_pixels"}
missing = required - set(errors.columns)
if missing:
    raise ValueError(f"Missing CSV columns: {missing}")

errors["sample_id"] = (
    errors["sample_id"].astype(str).str.replace(r"\.0$", "", regex=True)
)

# Only empty-ground-truth patches
empty = errors[errors["gt_pixels"] == 0].copy()
empty["group"] = np.where(
    empty["t0.5_pred_pixels"] > 0,
    "False positive",
    "Correctly empty"
)

print("Patch counts:")
print(empty["group"].value_counts().to_string())

records = []

for _, row in empty.iterrows():
    sample_id = row["sample_id"]
    image_path = IMAGE_DIR / f"image_{sample_id}.h5"

    if not image_path.exists():
        raise FileNotFoundError(image_path)

    with h5py.File(image_path, "r") as f:
        image = f["img"][:]

    predicted_pixels = int(row["t0.5_pred_pixels"])
    total_pixels = image.shape[0] * image.shape[1]

    for channel, feature in [(12, "slope"), (13, "dem")]:
        values = np.asarray(image[:, :, channel], dtype=np.float64)

        if not np.isfinite(values).all():
            raise ValueError(f"Non-finite {feature} values in {sample_id}")

        # Quartiles are calculated separately for each patch.
        q25, q50, q75 = np.percentile(values, [25, 50, 75])
        quartiles = np.digitize(
            values, [q25, q50, q75], right=False
        ) + 1

        for quartile in range(1, 5):
            region_pixels = int(np.sum(quartiles == quartile))

            records.append({
                "sample_id": sample_id,
                "group": row["group"],
                "feature": feature,
                "quartile": quartile,
                "region_pixels": region_pixels,
                "predicted_pixels": predicted_pixels,
                "prediction_rate_pct": (
                    100 * predicted_pixels / total_pixels
                ),
                "region_area_pct": 100 * region_pixels / total_pixels,
            })

detail = pd.DataFrame(records)

# Save per-patch quartile sizes and prediction counts.
detail_path = OUTPUT_DIR / "all_empty_patch_quartiles.csv"
detail.to_csv(detail_path, index=False)

# Compare groups at the patch level.
summary = (
    detail.groupby(["group", "feature", "quartile"])
    .agg(
        patch_count=("sample_id", "nunique"),
        mean_region_area_pct=("region_area_pct", "mean"),
        mean_prediction_rate_pct=("prediction_rate_pct", "mean"),
    )
    .reset_index()
)

summary_path = OUTPUT_DIR / "all_empty_quartile_summary.csv"
summary.to_csv(summary_path, index=False)

print("\nQuartile summary:")
print(summary.round(3).to_string(index=False))

# Additional patch-level comparison:
# How many predicted pixels fall into each quartile?
# Reconstructing the mask is intentionally avoided here because the
# previous CSV stores only total predicted pixels, not their locations.
print("\nImportant limitation:")
print(
    "This summary compares overall patch prediction rates and terrain "
    "quartile sizes. It does not measure predicted-pixel overlap with "
    "each quartile. That requires regenerating the spatial predictions "
    "for all 322 patches."
)

print(f"\nSaved detail:  {detail_path}")
print(f"Saved summary: {summary_path}")
