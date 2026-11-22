
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

THRESHOLD = 0.5
SLOPE_CHANNEL = 12
DEM_CHANNEL = 13


def read_h5(path, key):
    with h5py.File(path, "r") as f:
        return np.asarray(f[key])


def sample_id(path):
    return int(path.stem.split("_")[-1])


def safe_mean(values):
    return float(np.mean(values)) if values.size else np.nan


def safe_median(values):
    return float(np.median(values)) if values.size else np.nan


def safe_percentile(values, percentile):
    return (
        float(np.percentile(values, percentile))
        if values.size else np.nan
    )


def main():
    for path in (IMAGE_DIR, MASK_DIR, CHECKPOINT):
        if not path.exists():
            raise FileNotFoundError(path)

    image_files = sorted(str(p) for p in IMAGE_DIR.glob("*.h5"))
    if not image_files:
        raise RuntimeError(f"No images found in {IMAGE_DIR}")

    # Match the existing validation split.
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

    rows = []

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

            probabilities = (
                torch.sigmoid(logits).squeeze().cpu().numpy()
            )
            pred = probabilities >= THRESHOLD

            tp_mask = pred & gt
            fp_mask = pred & ~gt
            fn_mask = ~pred & gt

            gt_pixels = int(gt.sum())
            pred_pixels = int(pred.sum())
            tp = int(tp_mask.sum())
            fp = int(fp_mask.sum())
            fn = int(fn_mask.sum())

            # Terrain summaries for each patch.
            slope = image[:, :, SLOPE_CHANNEL].ravel()
            dem = image[:, :, DEM_CHANNEL].ravel()

            slope = slope[np.isfinite(slope)]
            dem = dem[np.isfinite(dem)]

            negative_pixels = int((~gt).sum())

            if gt_pixels == 0:
                patch_type = (
                    "empty_gt_false_positive" if fp > 0
                    else "empty_gt_correctly_empty"
                )
            else:
                patch_type = "positive_gt"

            rows.append({
                "sample_id": sid,
                "patch_type": patch_type,
                "gt_pixels": gt_pixels,
                "predicted_pixels": pred_pixels,
                "TP": tp,
                "FP": fp,
                "FN": fn,
                "FP_rate_among_GT_negative_pixels": (
                    fp / negative_pixels if negative_pixels else np.nan
                ),
                "mean_FP_probability": safe_mean(
                    probabilities[fp_mask].ravel()
                ),
                "median_FP_probability": safe_median(
                    probabilities[fp_mask].ravel()
                ),
                "mean_TP_probability": safe_mean(
                    probabilities[tp_mask].ravel()
                ),
                "mean_slope": safe_mean(slope),
                "median_slope": safe_median(slope),
                "p90_slope": safe_percentile(slope, 90),
                "mean_DEM": safe_mean(dem),
                "median_DEM": safe_median(dem),
                "p90_DEM": safe_percentile(dem, 90),
            })

            if index % 100 == 0:
                print(f"Processed {index}/{len(val_files)} patches")

    detail = pd.DataFrame(rows)

    # Group-level summaries: patches, not pixels, are the unit here.
    summary_rows = []

    for patch_type, group in detail.groupby("patch_type"):
        summary_rows.append({
            "patch_type": patch_type,
            "patch_count": len(group),
            "mean_FP_pixels_per_patch": group["FP"].mean(),
            "median_FP_pixels_per_patch": group["FP"].median(),
            "total_FP_pixels": int(group["FP"].sum()),
            "mean_FP_rate": group[
                "FP_rate_among_GT_negative_pixels"
            ].mean(),
            "mean_slope": group["mean_slope"].mean(),
            "median_slope": group["mean_slope"].median(),
            "mean_p90_slope": group["p90_slope"].mean(),
            "mean_DEM": group["mean_DEM"].mean(),
            "median_DEM": group["median_DEM"].median(),
            "mean_p90_DEM": group["p90_DEM"].mean(),
            "mean_FP_probability": group[
                "mean_FP_probability"
            ].mean(),
        })

    summary = pd.DataFrame(summary_rows)
    print("DEBUG: group summary created", flush=True)

    # Spearman rank correlations using pandas ranks to avoid SciPy.
    # Restrict this analysis to empty-GT patches, where every
    # predicted positive pixel is a false positive.
    empty = detail[detail["gt_pixels"] == 0].copy()

    correlation_rows = []
    predictors = [
        "mean_slope",
        "median_slope",
        "p90_slope",
        "mean_DEM",
        "median_DEM",
        "p90_DEM",
    ]

    for feature in predictors:
        valid = empty[[feature, "FP"]].dropna()

        if len(valid) < 3 or valid[feature].nunique() < 2:
            rho = np.nan
        else:
            ranked = valid.rank(method="average")
            rho = ranked[feature].corr(ranked["FP"])

        correlation_rows.append({
            "terrain_feature": feature,
            "empty_gt_patch_count": len(empty),
            "patches_used": len(valid),
            "spearman_rho_with_FP_pixel_count": rho,
        })

    correlations = pd.DataFrame(correlation_rows)
    print("DEBUG: correlations created", flush=True)
    correlations = correlations.sort_values(
        "spearman_rho_with_FP_pixel_count",
        key=lambda col: col.abs(),
        ascending=False,
        na_position="last",
    )

    detail_path = OUTPUT_DIR / "false_positive_terrain_detail.csv"
    summary_path = OUTPUT_DIR / "false_positive_terrain_group_summary.csv"
    corr_path = OUTPUT_DIR / "false_positive_terrain_correlations.csv"

    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    correlations.to_csv(corr_path, index=False)

    print("\n=== GROUP SUMMARY ===")
    print(summary.to_string(
        index=False, float_format=lambda v: f"{v:.5f}"
    ))

    print("\n=== TERRAIN CORRELATIONS ON EMPTY-GT PATCHES ===")
    print(correlations.to_string(
        index=False, float_format=lambda v: f"{v:.5f}"
    ))

    print("\nSaved files:")
    print(detail_path)
    print(summary_path)
    print(corr_path)


if __name__ == "__main__":
    main()
