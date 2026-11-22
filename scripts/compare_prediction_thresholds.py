
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

def calculate_metrics(c):
    tp, fp, fn, tn = c["TP"], c["FP"], c["FN"], c["TN"]

    return {
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
        "Accuracy": (tp + tn) / (tp + fp + fn + tn),
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
        raise RuntimeError(f"No image files found in {IMAGE_DIR}")

    # Reproduce the existing validation split exactly.
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

    counts = {
        t: {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
        for t in THRESHOLDS
    }

    with torch.no_grad():
        for index, image_name in enumerate(val_files, start=1):
            image_path = Path(image_name)
            sid = sample_id(image_path)
            mask_path = MASK_DIR / f"mask_{sid}.h5"

            if not mask_path.exists():
                raise FileNotFoundError(
                    f"Missing matching mask: {mask_path}"
                )

            image = read_h5(image_path, "img").astype(np.float32)
            gt = read_h5(mask_path, "mask") >= 0.5

            image = np.nan_to_num(
                image, nan=0.0, posinf=0.0, neginf=0.0
            )

            x = torch.from_numpy(image).permute(2, 0, 1)
            x = x.unsqueeze(0).to(device)

            probabilities = torch.sigmoid(model(x)).squeeze().cpu().numpy()

            for threshold in THRESHOLDS:
                pred = probabilities >= threshold

                counts[threshold]["TP"] += int((pred & gt).sum())
                counts[threshold]["FP"] += int((pred & ~gt).sum())
                counts[threshold]["FN"] += int((~pred & gt).sum())
                counts[threshold]["TN"] += int((~pred & ~gt).sum())

            if index % 100 == 0:
                print(f"Processed {index}/{len(val_files)} patches")

    rows = []
    for threshold in THRESHOLDS:
        row = {"Threshold": threshold}
        row.update(calculate_metrics(counts[threshold]))
        rows.append(row)

    results = pd.DataFrame(rows)
    output_file = OUTPUT_DIR / "threshold_comparison.csv"
    results.to_csv(output_file, index=False)

    print("\n=== GLOBAL PIXEL-LEVEL THRESHOLD COMPARISON ===")
    print(results.to_string(
        index=False,
        float_format=lambda value: f"{value:.5f}"
    ))
    print(f"\nSaved results to: {output_file}")

if __name__ == "__main__":
    main()
