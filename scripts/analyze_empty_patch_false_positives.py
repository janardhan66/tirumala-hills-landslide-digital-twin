
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

THRESHOLDS = [0.5, 0.6, 0.7]
BATCH_SIZE = 4

def read_h5(path, key):
    with h5py.File(path, "r") as f:
        return np.asarray(f[key])

def sample_id(path):
    return int(path.stem.split("_")[-1])

def main():
    image_files = sorted(str(p) for p in IMAGE_DIR.glob("*.h5"))
    if not image_files:
        raise RuntimeError(f"No images found: {IMAGE_DIR}")

    _, val_files = train_test_split(
        image_files,
        test_size=0.20,
        random_state=42,
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
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

    results = {
        t: {
            "empty_patches": 0,
            "empty_patches_with_fp": 0,
            "empty_patches_correctly_empty": 0,
            "empty_patch_fp_pixels": 0,
            "positive_patches": 0,
            "positive_patches_with_prediction": 0,
            "positive_patch_tp_pixels": 0,
            "positive_patch_fp_pixels": 0,
            "positive_patch_fn_pixels": 0,
        }
        for t in THRESHOLDS
    }

    total_validation_patches = 0

    with torch.no_grad():
        for i, filename in enumerate(val_files, start=1):
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

            probabilities = torch.sigmoid(model(x)).squeeze().cpu().numpy()
            total_validation_patches += 1

            is_empty = not gt.any()

            for threshold in THRESHOLDS:
                pred = probabilities >= threshold
                r = results[threshold]

                tp = int((pred & gt).sum())
                fp = int((pred & ~gt).sum())
                fn = int((~pred & gt).sum())

                if is_empty:
                    r["empty_patches"] += 1
                    r["empty_patch_fp_pixels"] += fp

                    if pred.any():
                        r["empty_patches_with_fp"] += 1
                    else:
                        r["empty_patches_correctly_empty"] += 1
                else:
                    r["positive_patches"] += 1
                    r["positive_patch_tp_pixels"] += tp
                    r["positive_patch_fp_pixels"] += fp
                    r["positive_patch_fn_pixels"] += fn

                    if pred.any():
                        r["positive_patches_with_prediction"] += 1

            if i % 100 == 0:
                print(f"Processed {i}/{len(val_files)} patches")

    rows = []
    for threshold in THRESHOLDS:
        r = results[threshold]
        rows.append({
            "Threshold": threshold,
            "Validation_patches": total_validation_patches,
            "Empty_GT_patches": r["empty_patches"],
            "Empty_patches_with_false_positives":
                r["empty_patches_with_fp"],
            "Empty_patches_correctly_empty":
                r["empty_patches_correctly_empty"],
            "Empty_patch_false_positive_pixels":
                r["empty_patch_fp_pixels"],
            "Empty_patch_FP_patch_rate_percent": (
                100 * r["empty_patches_with_fp"] / r["empty_patches"]
                if r["empty_patches"] else 0
            ),
            "Positive_GT_patches": r["positive_patches"],
            "Positive_patches_with_any_prediction":
                r["positive_patches_with_prediction"],
            "Positive_patch_TP_pixels": r["positive_patch_tp_pixels"],
            "Positive_patch_FP_pixels": r["positive_patch_fp_pixels"],
            "Positive_patch_FN_pixels": r["positive_patch_fn_pixels"],
        })

    df = pd.DataFrame(rows)
    output_file = OUTPUT_DIR / "empty_patch_false_positive_analysis.csv"
    df.to_csv(output_file, index=False)

    print("\n=== FALSE POSITIVES BY PATCH TYPE ===")
    print(df.to_string(
        index=False,
        float_format=lambda value: f"{value:.3f}"
    ))
    print(f"\nSaved: {output_file}")

if __name__ == "__main__":
    main()
