
from pathlib import Path
import h5py
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# Project paths
ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data" / "raw" / "landslide4sense" / "TrainData" / "img"
ERRORS_CSV = ROOT / "outputs" / "validation_analysis" / "per_image_errors.csv"
OUTPUT_DIR = ROOT / "outputs" / "validation_analysis"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Keep exactly the same validation split as the original model evaluation.
image_paths = sorted(str(p) for p in IMAGE_DIR.glob("*.h5"))
_, val_paths = train_test_split(
    image_paths, test_size=0.20, random_state=42
)
val_ids = {Path(p).stem.replace("image_", ""): p for p in val_paths}

if not ERRORS_CSV.exists():
    raise FileNotFoundError(f"Missing error analysis file: {ERRORS_CSV}")

errors = pd.read_csv(ERRORS_CSV)

# Find the expected columns without silently guessing.
required = {"sample_id", "gt_pixels", "t0.5_pred_pixels"}
missing = required - set(errors.columns)
if missing:
    raise ValueError(
        f"Missing columns in {ERRORS_CSV.name}: {sorted(missing)}. "
        f"Available columns: {list(errors.columns)}"
    )

errors["sample_id"] = errors["sample_id"].astype(str).str.replace(
    r"\.0$", "", regex=True
)
errors = errors[errors["sample_id"].isin(val_ids)].copy()

def classify(row):
    gt = float(row["gt_pixels"])
    pred = float(row["t0.5_pred_pixels"])

    if gt > 0:
        return "Positive ground truth"
    if pred > 0:
        return "Empty GT - false positive"
    return "Empty GT - no prediction"

errors["group"] = errors.apply(classify, axis=1)

# Extract per-patch terrain statistics.
records = []

for _, row in errors.iterrows():
    sample_id = row["sample_id"]
    image_path = val_ids[sample_id]

    with h5py.File(image_path, "r") as f:
        image = f["img"][:]

    if image.ndim != 3 or image.shape[2] != 14:
        raise ValueError(
            f"Unexpected image shape for sample {sample_id}: {image.shape}"
        )

    for channel_index, feature_name in [
        (12, "slope"),
        (13, "dem"),
    ]:
        values = np.asarray(image[:, :, channel_index], dtype=np.float64)
        values = values[np.isfinite(values)]

        if values.size == 0:
            continue

        records.append({
            "sample_id": sample_id,
            "group": row["group"],
            "feature": feature_name,
            "patch_mean": float(np.mean(values)),
            "patch_median": float(np.median(values)),
            "patch_std": float(np.std(values)),
            "patch_p10": float(np.percentile(values, 10)),
            "patch_p90": float(np.percentile(values, 90)),
            "gt_pixels": int(row["gt_pixels"]),
            "pred_pixels_at_0.5": int(row["t0.5_pred_pixels"]),
        })

patch_df = pd.DataFrame(records)

if patch_df.empty:
    raise ValueError("No terrain records were generated. Check file paths and IDs.")

patch_path = OUTPUT_DIR / "terrain_per_patch.csv"
patch_df.to_csv(patch_path, index=False)

# Summarize the distribution of per-patch statistics by group.
summary = (
    patch_df.groupby(["group", "feature"])
    .agg(
        patch_count=("sample_id", "nunique"),
        mean_of_patch_means=("patch_mean", "mean"),
        median_of_patch_means=("patch_mean", "median"),
        std_of_patch_means=("patch_mean", "std"),
        mean_of_patch_medians=("patch_median", "mean"),
        mean_of_patch_stds=("patch_std", "mean"),
        mean_of_patch_p10=("patch_p10", "mean"),
        mean_of_patch_p90=("patch_p90", "mean"),
    )
    .reset_index()
)

summary_path = OUTPUT_DIR / "terrain_group_summary.csv"
summary.to_csv(summary_path, index=False)

print("\nValidation group counts:")
print(errors["group"].value_counts().to_string())

print("\nTerrain comparison:")
print(summary.round(4).to_string(index=False))

print(f"\nSaved per-patch results: {patch_path}")
print(f"Saved group summary:     {summary_path}")
print("\nInterpretation note:")
print(
    "Differences show associations, not proof that slope or elevation "
    "caused false positives. Terrain values are compared across patches."
)
