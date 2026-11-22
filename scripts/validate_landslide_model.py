
from pathlib import Path
import sys

import h5py
import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset, DataLoader

# ============================================================
# PROJECT PATHS
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.landslide_segmentation import UNet

IMAGE_DIR = PROJECT_ROOT / "data/raw/landslide4sense/TrainData/img"
MASK_DIR = PROJECT_ROOT / "data/raw/landslide4sense/TrainData/mask"
CHECKPOINT = PROJECT_ROOT / "models/landslide_unet_14channel_best.pth"

THRESHOLD = 0.5
BATCH_SIZE = 4


# ============================================================
# VALIDATION DATASET
# ============================================================
class ValidationDataset(Dataset):
    def __init__(self, files):
        self.files = files

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        image_path = self.files[idx]
        sample_id = Path(image_path).stem.split("_")[-1]
        mask_path = MASK_DIR / f"mask_{sample_id}.h5"

        with h5py.File(image_path, "r") as f:
            image = f["img"][:]

        with h5py.File(mask_path, "r") as f:
            mask = f["mask"][:]

        # Match the training preprocessing
        image = np.nan_to_num(
            image,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        ).astype(np.float32)

        image = np.transpose(image, (2, 0, 1))
        mask = mask.astype(np.float32)[None, ...]

        return torch.from_numpy(image), torch.from_numpy(mask)


# ============================================================
# VALIDATION
# ============================================================
def main():
    if not IMAGE_DIR.exists():
        raise FileNotFoundError(f"Image directory not found: {IMAGE_DIR}")

    if not MASK_DIR.exists():
        raise FileNotFoundError(f"Mask directory not found: {MASK_DIR}")

    if not CHECKPOINT.exists():
        raise FileNotFoundError(f"Checkpoint not found: {CHECKPOINT}")

    files = sorted(str(x) for x in IMAGE_DIR.glob("*.h5"))

    if not files:
        raise RuntimeError(f"No HDF5 images found in {IMAGE_DIR}")

    # Reproduce the training script's split
    _, val_files = train_test_split(
        files,
        test_size=0.20,
        random_state=42,
    )

    print("=" * 60)
    print("LANDSLIDE U-NET CHECKPOINT VALIDATION")
    print("=" * 60)
    print(f"Total images:      {len(files)}")
    print(f"Validation images: {len(val_files)}")
    print(f"Threshold:         {THRESHOLD}")
    print(f"Batch size:        {BATCH_SIZE}")

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    print(f"Device:            {device}")

    # Load checkpoint
    checkpoint = torch.load(
        CHECKPOINT,
        map_location=device,
    )

    model = UNet(
        in_channels=14,
        out_channels=1,
    ).to(device)

    state_dict = (
        checkpoint["model_state_dict"]
        if isinstance(checkpoint, dict)
        and "model_state_dict" in checkpoint
        else checkpoint
    )

    model.load_state_dict(state_dict, strict=True)
    model.eval()

    loader = DataLoader(
        ValidationDataset(val_files),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
    )

    # Global pixel counts
    tp = fp = fn = tn = 0

    # Training-style batch-averaged metrics
    batch_dice = []
    batch_iou = []

    with torch.no_grad():
        for batch_index, (images, masks) in enumerate(loader, start=1):
            images = images.to(device)
            masks = masks.to(device)

            logits = model(images)
            probabilities = torch.sigmoid(logits)

            predictions = probabilities >= THRESHOLD
            targets = masks >= 0.5

            # Global confusion counts
            tp += int((predictions & targets).sum().item())
            fp += int((predictions & ~targets).sum().item())
            fn += int((~predictions & targets).sum().item())
            tn += int((~predictions & ~targets).sum().item())

            # Batch-level metrics, matching the training script's approach
            intersection = (predictions & targets).sum().item()
            predicted_pixels = predictions.sum().item()
            target_pixels = targets.sum().item()

            union = predicted_pixels + target_pixels - intersection

            dice_value = (
                (2 * intersection + 1e-7)
                / (predicted_pixels + target_pixels + 1e-7)
            )

            iou_value = (
                (intersection + 1e-7)
                / (union + 1e-7)
            )

            batch_dice.append(dice_value)
            batch_iou.append(iou_value)

    # Global metrics
    dice = (
        2 * tp / (2 * tp + fp + fn)
        if (2 * tp + fp + fn) else 0.0
    )

    iou = (
        tp / (tp + fp + fn)
        if (tp + fp + fn) else 0.0
    )

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    accuracy = (
        (tp + tn) / (tp + tn + fp + fn)
        if (tp + tn + fp + fn) else 0.0
    )

    print("\n=== GLOBAL PIXEL-LEVEL RESULTS ===")
    print(f"TP: {tp:,} | FP: {fp:,} | FN: {fn:,} | TN: {tn:,}")
    print(f"Dice:      {dice:.4f}")
    print(f"IoU:       {iou:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"Accuracy:  {accuracy:.4f}")

    print("\n=== BATCH-AVERAGED RESULTS ===")
    print(f"Batch-averaged Dice: {np.mean(batch_dice):.4f}")
    print(f"Batch-averaged IoU:  {np.mean(batch_iou):.4f}")
    print(f"Number of batches:   {len(batch_dice)}")

    if isinstance(checkpoint, dict):
        print("\n=== CHECKPOINT METADATA ===")
        for key in ("epoch", "validation_dice", "validation_iou"):
            if key in checkpoint:
                print(f"{key}: {checkpoint[key]}")

    print("\nValidation finished. No model weights or dataset files were changed.")


if __name__ == "__main__":
    main()
