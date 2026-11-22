
from pathlib import Path
import h5py
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data" / "raw" / "landslide4sense" / "TrainData" / "img"
MASK_DIR = ROOT / "data" / "raw" / "landslide4sense" / "TrainData" / "mask"
OUTPUT_DIR = ROOT / "outputs" / "validation_analysis"

SAMPLE_IDS = [3192, 672, 3277, 2691, 866]
THRESHOLD = 0.5

# Load existing prediction counts; no model inference is required.
ERRORS_FILE = OUTPUT_DIR / "per_image_errors.csv"
errors = pd.read_csv(ERRORS_FILE)
errors["sample_id"] = (
    errors["sample_id"].astype(str).str.replace(r"\.0$", "", regex=True)
)

records = []

for sample_id in SAMPLE_IDS:
    image_path = IMAGE_DIR / f"image_{sample_id}.h5"
    mask_path = MASK_DIR / f"mask_{sample_id}.h5"

    with h5py.File(image_path, "r") as f:
        image = f["img"][:]

    with h5py.File(mask_path, "r") as f:
        ground_truth = f["mask"][:] > 0

    row = errors[errors["sample_id"] == str(sample_id)]
    if row.empty:
        raise ValueError(f"Sample {sample_id} not found in error CSV")

    predicted_pixels = int(row.iloc[0]["t0.5_pred_pixels"])

    # Reconstruct the binary prediction from the saved comparison image
    # is not reliable, so require the original probabilities/prediction
    # to be regenerated with the project model.
    # This script instead loads the model and reproduces inference.
    import torch
    import sys
    sys.path.insert(0, str(ROOT))
    from src.models.landslide_segmentation import UNet

    checkpoint_path = ROOT / "models" / "landslide_unet_14channel_best.pth"
    if sample_id == SAMPLE_IDS[0]:
        checkpoint = torch.load(
            checkpoint_path, map_location="cpu", weights_only=False
        )
        model = UNet()
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

    tensor = torch.from_numpy(
        np.nan_to_num(image.astype(np.float32)).transpose(2, 0, 1).copy()
    ).unsqueeze(0)

    with torch.inference_mode():
        probabilities = torch.sigmoid(model(tensor))[0, 0].numpy()

    prediction = probabilities >= THRESHOLD

    if int(prediction.sum()) != predicted_pixels:
        raise ValueError(
            f"Prediction count mismatch for {sample_id}: "
            f"new={prediction.sum()}, recorded={predicted_pixels}"
        )

    for channel, feature in [(12, "slope"), (13, "dem")]:
        values = image[:, :, channel].astype(np.float64)
        finite = np.isfinite(values)

        if not finite.all():
            raise ValueError(
                f"Non-finite {feature} values in sample {sample_id}"
            )

        cutoff = np.percentile(values, 75)
        high_terrain = values >= cutoff

        predicted_count = int(prediction.sum())
        high_count = int(high_terrain.sum())
        overlap = int(np.sum(prediction & high_terrain))

        # Baseline: percentage of all pixels in the top terrain quartile.
        baseline_pct = 100 * high_count / values.size

        # Percentage of predicted pixels in the top terrain quartile.
        predicted_in_high_pct = (
            100 * overlap / predicted_count if predicted_count else np.nan
        )

        # How much more often predicted pixels occur in high terrain
        # than expected from the overall area fraction.
        enrichment = (
            predicted_in_high_pct / baseline_pct
            if baseline_pct else np.nan
        )

        records.append({
            "sample_id": sample_id,
            "feature": feature,
            "predicted_pixels": predicted_count,
            "terrain_q75_cutoff": float(cutoff),
            "pixels_in_top_25pct_terrain": high_count,
            "predicted_pixels_in_top_25pct": overlap,
            "predicted_pixels_in_top_25pct_pct": predicted_in_high_pct,
            "baseline_top_25pct_area_pct": baseline_pct,
            "enrichment_ratio": enrichment,
            "ground_truth_pixels": int(ground_truth.sum()),
        })

result = pd.DataFrame(records)
output_path = OUTPUT_DIR / "terrain_spatial_overlap.csv"
result.to_csv(output_path, index=False)

print("\nTerrain overlap results:")
print(result.round(3).to_string(index=False))
print(f"\nSaved to: {output_path}")
print(
    "\nEnrichment > 1 means predictions are overrepresented in the "
    "top terrain quartile. This is descriptive, not causal evidence."
)
