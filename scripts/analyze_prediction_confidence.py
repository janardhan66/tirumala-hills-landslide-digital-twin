
from pathlib import Path
import sys

import h5py
import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.landslide_segmentation import UNet

IMAGE_DIR = PROJECT_ROOT / "data/raw/landslide4sense/TrainData/img"
MASK_DIR = PROJECT_ROOT / "data/raw/landslide4sense/TrainData/mask"
CHECKPOINT = PROJECT_ROOT / "models/landslide_unet_14channel_best.pth"
OUTPUT_DIR = PROJECT_ROOT / "outputs/validation_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASELINE_THRESHOLD = 0.5
THRESHOLDS = [0.5, 0.6, 0.7]
BINS = np.linspace(0.0, 1.0, 21)


def read_h5(path, key):
    with h5py.File(path, "r") as f:
        return np.asarray(f[key])


def sample_id(path):
    return int(path.stem.split("_")[-1])


def summarize(values, group_name):
    if len(values) == 0:
        return {
            "Group": group_name,
            "Pixel_count": 0,
            "Mean_probability": np.nan,
            "Median_probability": np.nan,
            "P10": np.nan,
            "P25": np.nan,
            "P75": np.nan,
            "P90": np.nan,
            "P95": np.nan,
            "Minimum": np.nan,
            "Maximum": np.nan,
        }

    return {
        "Group": group_name,
        "Pixel_count": len(values),
        "Mean_probability": float(np.mean(values)),
        "Median_probability": float(np.median(values)),
        "P10": float(np.percentile(values, 10)),
        "P25": float(np.percentile(values, 25)),
        "P75": float(np.percentile(values, 75)),
        "P90": float(np.percentile(values, 90)),
        "P95": float(np.percentile(values, 95)),
        "Minimum": float(np.min(values)),
        "Maximum": float(np.max(values)),
    }


def main():
    if not IMAGE_DIR.exists():
        raise FileNotFoundError(IMAGE_DIR)
    if not MASK_DIR.exists():
        raise FileNotFoundError(MASK_DIR)
    if not CHECKPOINT.exists():
        raise FileNotFoundError(CHECKPOINT)

    image_files = sorted(str(p) for p in IMAGE_DIR.glob("*.h5"))
    if not image_files:
        raise RuntimeError(f"No images found: {IMAGE_DIR}")

    # Reproduce the existing validation split.
    _, val_files = train_test_split(
        image_files,
        test_size=0.20,
        random_state=42,
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    print(f"Device: {device}")
    print(f"Validation patches: {len(val_files)}")

    checkpoint = torch.load(CHECKPOINT, map_location=device)
    model = UNet(in_channels=14, out_channels=1).to(device)

    state_dict = (
        checkpoint["model_state_dict"]
        if isinstance(checkpoint, dict)
        and "model_state_dict" in checkpoint
        else checkpoint
    )
    model.load_state_dict(state_dict, strict=True)
    model.eval()

    # Probability arrays for baseline-threshold pixel groups.
    groups = {
        "True positive": [],
        "False positive": [],
        "False negative": [],
    }

    threshold_counts = {
        t: {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
        for t in THRESHOLDS
    }

    with torch.no_grad():
        for index, filename in enumerate(val_files, start=1):
            image_path = Path(filename)
            sid = sample_id(image_path)
            mask_path = MASK_DIR / f"mask_{sid}.h5"

            if not mask_path.exists():
                raise FileNotFoundError(mask_path)

            image = read_h5(image_path, "img").astype(np.float32)
            gt = read_h5(mask_path, "mask") >= 0.5

            image = np.nan_to_num(
                image, nan=0.0, posinf=0.0, neginf=0.0
            )

            x = torch.from_numpy(image).permute(2, 0, 1)
            x = x.unsqueeze(0).to(device)

            logits = model(x)
            if isinstance(logits, (tuple, list)):
                logits = logits[0]

            probs = torch.sigmoid(logits).squeeze().cpu().numpy()
            baseline_pred = probs >= BASELINE_THRESHOLD

            # Group pixels according to the baseline threshold of 0.5.
            tp_mask = baseline_pred & gt
            fp_mask = baseline_pred & ~gt
            fn_mask = ~baseline_pred & gt

            groups["True positive"].append(probs[tp_mask].ravel())
            groups["False positive"].append(probs[fp_mask].ravel())
            groups["False negative"].append(probs[fn_mask].ravel())

            # Recompute global metrics for each threshold.
            for threshold in THRESHOLDS:
                pred = probs >= threshold
                c = threshold_counts[threshold]
                c["TP"] += int((pred & gt).sum())
                c["FP"] += int((pred & ~gt).sum())
                c["FN"] += int((~pred & gt).sum())
                c["TN"] += int((~pred & ~gt).sum())

            if index % 100 == 0:
                print(f"Processed {index}/{len(val_files)} patches")

    # Summaries of probability distributions.
    summaries = []
    histogram_rows = []

    for group_name, arrays in groups.items():
        values = (
            np.concatenate(arrays)
            if arrays else np.array([], dtype=np.float32)
        )

        summaries.append(summarize(values, group_name))

        if len(values):
            counts, edges = np.histogram(values, bins=BINS)
            for i, count in enumerate(counts):
                histogram_rows.append({
                    "Group": group_name,
                    "Probability_bin_start": edges[i],
                    "Probability_bin_end": edges[i + 1],
                    "Pixel_count": int(count),
                    "Percentage_within_group": (
                        100 * count / len(values)
                    ),
                })

    summary_df = pd.DataFrame(summaries)
    histogram_df = pd.DataFrame(histogram_rows)

    # Threshold trade-off metrics.
    threshold_rows = []
    for threshold, c in threshold_counts.items():
        tp, fp, fn, tn = c["TP"], c["FP"], c["FN"], c["TN"]

        threshold_rows.append({
            "Threshold": threshold,
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "TN": tn,
            "Dice": 2 * tp / (2 * tp + fp + fn)
                if (2 * tp + fp + fn) else 0,
            "IoU": tp / (tp + fp + fn)
                if (tp + fp + fn) else 0,
            "Precision": tp / (tp + fp)
                if (tp + fp) else 0,
            "Recall": tp / (tp + fn)
                if (tp + fn) else 0,
        })

    threshold_df = pd.DataFrame(threshold_rows)

    summary_path = OUTPUT_DIR / "prediction_confidence_summary.csv"
    histogram_path = OUTPUT_DIR / "prediction_confidence_histogram.csv"
    threshold_path = OUTPUT_DIR / "prediction_confidence_threshold_metrics.csv"

    summary_df.to_csv(summary_path, index=False)
    histogram_df.to_csv(histogram_path, index=False)
    threshold_df.to_csv(threshold_path, index=False)

    print("\n=== BASELINE PIXEL CONFIDENCE SUMMARY ===")
    print(summary_df.to_string(
        index=False, float_format=lambda v: f"{v:.5f}"
    ))

    print("\n=== METRICS BY THRESHOLD ===")
    print(threshold_df.to_string(
        index=False, float_format=lambda v: f"{v:.5f}"
    ))

    print("\nFiles saved:")
    print(summary_path)
    print(histogram_path)
    print(threshold_path)


if __name__ == "__main__":
    main()
