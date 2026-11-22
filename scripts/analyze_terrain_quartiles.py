
from pathlib import Path
import h5py
import numpy as np
import pandas as pd
import torch
import sys

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data/raw/landslide4sense/TrainData/img"
OUTPUT_DIR = ROOT / "outputs/validation_analysis"
CHECKPOINT_PATH = ROOT / "models/landslide_unet_14channel_best.pth"

SAMPLE_IDS = [3192, 672, 3277, 2691, 866]
THRESHOLD = 0.5

sys.path.insert(0, str(ROOT))
from src.models.landslide_segmentation import UNet

checkpoint = torch.load(
    CHECKPOINT_PATH, map_location="cpu", weights_only=False
)
model = UNet()
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

records = []

for sample_id in SAMPLE_IDS:
    path = IMAGE_DIR / f"image_{sample_id}.h5"

    with h5py.File(path, "r") as f:
        image = f["img"][:]

    image = np.nan_to_num(image.astype(np.float32))
    tensor = torch.from_numpy(
        image.transpose(2, 0, 1).copy()
    ).unsqueeze(0)

    with torch.inference_mode():
        probabilities = torch.sigmoid(model(tensor))[0, 0].numpy()

    prediction = probabilities >= THRESHOLD
    total_predicted = int(prediction.sum())

    print(f"Sample {sample_id}: {total_predicted} predicted pixels")

    if total_predicted == 0:
        print("  No predicted pixels; skipping quartile proportions.")
        continue

    for channel, feature in [(12, "slope"), (13, "dem")]:
        values = image[:, :, channel].astype(np.float64)
        cutoffs = np.percentile(values, [25, 50, 75])

        # Quartile 1 is the lowest 25%, quartile 4 the highest 25%.
        quartile_map = np.digitize(values, cutoffs, right=False) + 1

        for quartile in range(1, 5):
            region = quartile_map == quartile
            region_pixels = int(region.sum())
            predicted_in_region = int(np.sum(prediction & region))

            records.append({
                "sample_id": sample_id,
                "feature": feature,
                "quartile": quartile,
                "terrain_cutoff_lower": (
                    np.nan if quartile == 1 else float(cutoffs[quartile - 2])
                ),
                "terrain_cutoff_upper": (
                    np.nan if quartile == 4 else float(cutoffs[quartile - 1])
                ),
                "region_pixels": region_pixels,
                "predicted_pixels_in_region": predicted_in_region,
                "region_prediction_rate_pct": (
                    100 * predicted_in_region / region_pixels
                    if region_pixels else np.nan
                ),
                "share_of_all_predictions_pct": (
                    100 * predicted_in_region / total_predicted
                ),
                "baseline_area_share_pct": (
                    100 * region_pixels / values.size
                ),
                "enrichment_ratio": (
                    (predicted_in_region / total_predicted)
                    / (region_pixels / values.size)
                    if region_pixels else np.nan
                ),
            })

result = pd.DataFrame(records)
output = OUTPUT_DIR / "terrain_quartile_analysis.csv"
result.to_csv(output, index=False)

print("\nPrediction distribution across terrain quartiles:")
print(
    result[
        ["sample_id", "feature", "quartile",
         "share_of_all_predictions_pct", "enrichment_ratio"]
    ].round(3).to_string(index=False)
)
print(f"\nSaved results to: {output}")
print(
    "\nInterpretation: enrichment > 1 indicates overrepresentation "
    "of predictions in that quartile. Ties at percentile boundaries "
    "may cause quartiles to contain slightly different numbers of pixels."
)
