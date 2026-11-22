
from pathlib import Path
import sys
import csv

import h5py
import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset, DataLoader
from src.models.landslide_segmentation import UNet

IMAGE_DIR = PROJECT_ROOT / "data/raw/landslide4sense/TrainData/img"
MASK_DIR = PROJECT_ROOT / "data/raw/landslide4sense/TrainData/mask"
CHECKPOINT = PROJECT_ROOT / "models/landslide_unet_14channel_best.pth"
OUTPUT_DIR = PROJECT_ROOT / "outputs/validation_analysis"

BATCH_SIZE = 4
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]
EPS = 1e-7


class LandslideDataset(Dataset):
    def __init__(self, image_paths):
        self.image_paths = image_paths

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, index):
        image_path = Path(self.image_paths[index])
        sample_id = image_path.stem.split("_")[-1]
        mask_path = MASK_DIR / f"mask_{sample_id}.h5"

        with h5py.File(image_path, "r") as f:
            image = np.asarray(f["img"], dtype=np.float32)

        with h5py.File(mask_path, "r") as f:
            mask = np.asarray(f["mask"])

        image = np.nan_to_num(image)
        mask = (mask > 0).astype(np.float32)

        image = torch.from_numpy(image.transpose(2, 0, 1).copy())
        mask = torch.from_numpy(mask[None, :, :].copy())

        return image, mask, int(sample_id)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading checkpoint...", flush=True)
    checkpoint = torch.load(
        CHECKPOINT, map_location="cpu", weights_only=False
    )

    model = UNet()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Reproduce the lexicographic file order and original 80/20 split.
    image_paths = sorted(str(p) for p in IMAGE_DIR.glob("*.h5"))
    train_paths, val_paths = train_test_split(
        image_paths, test_size=0.20, random_state=42
    )

    print(f"Total images: {len(image_paths)}")
    print(f"Validation images: {len(val_paths)}")

    loader = DataLoader(
        LandslideDataset(val_paths),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )

    records = []

    threshold_totals = {
        t: {"tp": 0, "fp": 0, "fn": 0, "tn": 0,
            "dice_sum": 0.0, "iou_sum": 0.0, "batches": 0}
        for t in THRESHOLDS
    }

    print("Running inference on validation images...", flush=True)

    with torch.inference_mode():
        for batch_index, (images, masks, sample_ids) in enumerate(loader, 1):
            logits = model(images)
            probabilities = torch.sigmoid(logits).cpu().numpy()
            targets = masks.numpy().astype(bool)

            for i, sample_id in enumerate(sample_ids.tolist()):
                target = targets[i, 0]
                gt_pixels = int(target.sum())
                prob = probabilities[i, 0]

                row = {
                    "sample_id": sample_id,
                    "gt_pixels": gt_pixels,
                }

                for threshold in THRESHOLDS:
                    pred = prob >= threshold

                    tp = int(np.sum(pred & target))
                    fp = int(np.sum(pred & ~target))
                    fn = int(np.sum(~pred & target))
                    tn = int(np.sum(~pred & ~target))

                    dice = (2 * tp) / (2 * tp + fp + fn + EPS)
                    iou = tp / (tp + fp + fn + EPS)
                    precision = tp / (tp + fp + EPS)
                    recall = tp / (tp + fn + EPS)

                    prefix = f"t{threshold:.1f}_"
                    row[prefix + "pred_pixels"] = int(pred.sum())
                    row[prefix + "tp"] = tp
                    row[prefix + "fp"] = fp
                    row[prefix + "fn"] = fn
                    row[prefix + "tn"] = tn
                    row[prefix + "dice"] = dice
                    row[prefix + "iou"] = iou
                    row[prefix + "precision"] = precision
                    row[prefix + "recall"] = recall

                    totals = threshold_totals[threshold]
                    totals["tp"] += tp
                    totals["fp"] += fp
                    totals["fn"] += fn
                    totals["tn"] += tn

                records.append(row)

            if batch_index % 25 == 0:
                print(
                    f"Processed {min(batch_index * BATCH_SIZE, len(val_paths))}"
                    f"/{len(val_paths)} images",
                    flush=True,
                )

    # Calculate per-image averages and aggregate pixel-level metrics.
    summary_rows = []

    for threshold in THRESHOLDS:
        prefix = f"t{threshold:.1f}_"
        totals = threshold_totals[threshold]

        dices = [r[prefix + "dice"] for r in records]
        ious = [r[prefix + "iou"] for r in records]

        # Empty-mask cases need separate reporting: their standard Dice/IoU
        # is undefined when both ground truth and prediction are empty.
        empty_gt = [r for r in records if r["gt_pixels"] == 0]
        empty_gt_no_pred = [
            r for r in empty_gt if r[prefix + "pred_pixels"] == 0
        ]

        tp, fp, fn, tn = (
            totals["tp"], totals["fp"], totals["fn"], totals["tn"]
        )

        global_dice = (2 * tp) / (2 * tp + fp + fn + EPS)
        global_iou = tp / (tp + fp + fn + EPS)

        summary_rows.append({
            "threshold": threshold,
            "global_dice": global_dice,
            "global_iou": global_iou,
            "mean_image_dice_including_empty_as_zero": float(np.mean(dices)),
            "mean_image_iou_including_empty_as_zero": float(np.mean(ious)),
            "precision": tp / (tp + fp + EPS),
            "recall": tp / (tp + fn + EPS),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "empty_gt_images": len(empty_gt),
            "empty_gt_with_no_prediction": len(empty_gt_no_pred),
        })

    per_image_path = OUTPUT_DIR / "per_image_errors.csv"
    with per_image_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    summary_path = OUTPUT_DIR / "threshold_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    # Rank difficult images using Dice at threshold 0.5.
    records.sort(key=lambda r: r["t0.5_dice"])
    hard_path = OUTPUT_DIR / "hardest_samples.csv"

    with hard_path.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "sample_id", "gt_pixels", "t0.5_pred_pixels",
            "t0.5_dice", "t0.5_iou", "t0.5_fp", "t0.5_fn"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for row in records[:30]:
            writer.writerow({
                "sample_id": row["sample_id"],
                "gt_pixels": row["gt_pixels"],
                "t0.5_pred_pixels": row["t0.5_pred_pixels"],
                "t0.5_dice": row["t0.5_dice"],
                "t0.5_iou": row["t0.5_iou"],
                "t0.5_fp": row["t0.5_fp"],
                "t0.5_fn": row["t0.5_fn"],
            })

    print("\n=== THRESHOLD SUMMARY ===")
    for row in summary_rows:
        print(
            f"Threshold {row['threshold']:.1f} | "
            f"Global Dice={row['global_dice']:.4f} | "
            f"Global IoU={row['global_iou']:.4f} | "
            f"Precision={row['precision']:.4f} | "
            f"Recall={row['recall']:.4f} | "
            f"Empty-mask images with no prediction="
            f"{row['empty_gt_with_no_prediction']}/"
            f"{row['empty_gt_images']}"
        )

    print("\n=== HARDEST SAMPLES AT THRESHOLD 0.5 ===")
    for row in records[:10]:
        print(
            f"ID={row['sample_id']} | GT={row['gt_pixels']} | "
            f"Pred={row['t0.5_pred_pixels']} | "
            f"Dice={row['t0.5_dice']:.4f} | "
            f"FP={row['t0.5_fp']} | FN={row['t0.5_fn']}"
        )

    print("\nAnalysis complete.")
    print("Results saved to:", OUTPUT_DIR)
    print("Checkpoint and dataset were not modified.")


if __name__ == "__main__":
    main()
