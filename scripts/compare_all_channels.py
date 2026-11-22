
from pathlib import Path
import h5py
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "data" / "raw" / "landslide4sense" / "TrainData" / "img"
ERRORS_CSV = ROOT / "outputs" / "validation_analysis" / "per_image_errors.csv"
OUTPUT_DIR = ROOT / "outputs" / "validation_analysis"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load existing validation errors
errors = pd.read_csv(ERRORS_CSV)

required = {"sample_id", "gt_pixels", "t0.5_pred_pixels"}
missing = required - set(errors.columns)
if missing:
    raise ValueError(
        f"Missing columns: {missing}. Available: {list(errors.columns)}"
    )

errors["sample_id"] = (
    errors["sample_id"].astype(str).str.replace(r"\.0$", "", regex=True)
)

# Select empty-ground-truth patches only
empty = errors[errors["gt_pixels"] == 0].copy()

empty["group"] = np.where(
    empty["t0.5_pred_pixels"] > 0,
    "False positive",
    "Correctly empty"
)

print("Group counts:")
print(empty["group"].value_counts().to_string())

# Read all 14 channels and calculate per-patch statistics
records = []

for _, row in empty.iterrows():
    sample_id = row["sample_id"]
    image_path = IMAGE_DIR / f"image_{sample_id}.h5"

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with h5py.File(image_path, "r") as f:
        image = f["img"][:]

    if image.ndim != 3 or image.shape[2] != 14:
        raise ValueError(
            f"Unexpected shape for {sample_id}: {image.shape}"
        )

    for channel in range(14):
        values = image[:, :, channel].astype(np.float64)
        values = values[np.isfinite(values)]

        if values.size == 0:
            continue

        records.append({
            "sample_id": sample_id,
            "group": row["group"],
            "channel": channel,
            "patch_mean": float(np.mean(values)),
            "patch_median": float(np.median(values)),
            "patch_std": float(np.std(values)),
            "predicted_pixels": int(row["t0.5_pred_pixels"]),
        })

patch_df = pd.DataFrame(records)

patch_file = OUTPUT_DIR / "all_channel_per_patch.csv"
patch_df.to_csv(patch_file, index=False)

# Compare the two groups for every channel
summary = []

for channel in range(14):
    channel_df = patch_df[patch_df["channel"] == channel]

    fp = channel_df.loc[
        channel_df["group"] == "False positive", "patch_mean"
    ].to_numpy(dtype=float)

    correct = channel_df.loc[
        channel_df["group"] == "Correctly empty", "patch_mean"
    ].to_numpy(dtype=float)

    if len(fp) == 0 or len(correct) == 0:
        continue

    test = mannwhitneyu(fp, correct, alternative="two-sided")

    # Cliff's delta calculated from average ranks
    combined = np.concatenate([fp, correct])
    ranks = pd.Series(combined).rank(method="average").to_numpy()

    n1 = len(fp)
    n2 = len(correct)
    u_fp = ranks[:n1].sum() - n1 * (n1 + 1) / 2
    delta = 2 * (u_fp / (n1 * n2)) - 1

    summary.append({
        "channel": channel,
        "false_positive_count": n1,
        "correctly_empty_count": n2,
        "false_positive_mean": fp.mean(),
        "correctly_empty_mean": correct.mean(),
        "mean_difference": fp.mean() - correct.mean(),
        "mann_whitney_U": float(test.statistic),
        "p_value": float(test.pvalue),
        "cliffs_delta": float(delta),
    })

summary_df = pd.DataFrame(summary)

# Holm correction for 14 channel-wise tests
p_values = summary_df["p_value"].to_numpy()
order = np.argsort(p_values)
adjusted = np.empty(len(p_values))
running_max = 0.0

for rank, index in enumerate(order):
    value = min(1.0, (len(p_values) - rank) * p_values[index])
    running_max = max(running_max, value)
    adjusted[index] = running_max

summary_df["holm_adjusted_p_value"] = adjusted
summary_df["absolute_cliffs_delta"] = summary_df["cliffs_delta"].abs()

summary_df = summary_df.sort_values(
    "holm_adjusted_p_value"
).reset_index(drop=True)

summary_file = OUTPUT_DIR / "all_channel_comparison.csv"
summary_df.to_csv(summary_file, index=False)

print("\nChannel comparison, sorted by adjusted p-value:")
print(summary_df.round(5).to_string(index=False))

print(f"\nPer-patch data saved to: {patch_file}")
print(f"Comparison summary saved to: {summary_file}")
print(
    "\nReminder: statistical differences show associations, not "
    "proof that a channel causes false-positive predictions."
)
