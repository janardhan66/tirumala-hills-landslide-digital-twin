
from pathlib import Path
import sys
import traceback

import h5py
import numpy as np
import torch
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.landslide_segmentation import UNet

IMAGE_DIR = PROJECT_ROOT / "data/raw/landslide4sense/TrainData/img"
MASK_DIR = PROJECT_ROOT / "data/raw/landslide4sense/TrainData/mask"
CHECKPOINT = PROJECT_ROOT / "models/landslide_unet_14channel_best.pth"
OUTPUT_DIR = PROJECT_ROOT / "outputs/validation_visuals"

THRESHOLD = 0.5
SAMPLE_IDS = [3192, 672, 3277, 2691, 866]
PANEL_SIZE = 256


def log(message):
    print(message, flush=True)


def load_h5(path, key):
    with h5py.File(path, "r") as f:
        return np.asarray(f[key])


def make_rgb(image):
    # Display-only composite using channels 3, 2, and 1.
    rgb = image[:, :, [3, 2, 1]].copy()
    low = np.percentile(rgb, 2, axis=(0, 1))
    high = np.percentile(rgb, 98, axis=(0, 1))
    rgb = np.clip((rgb - low) / (high - low + 1e-7), 0, 1)
    return (rgb * 255).astype(np.uint8)

def terrain_rgb(channel):
    """Create a grayscale visualization with per-patch contrast stretching."""
    channel = np.asarray(channel, dtype=np.float32)
    low, high = np.percentile(channel, [2, 98])

    normalized = np.clip(
        (channel - low) / (high - low + 1e-7), 0, 1
    )

    gray = (normalized * 255).astype(np.uint8)
    return np.stack([gray, gray, gray], axis=-1)


def mask_rgb(mask):
    result = np.zeros((*mask.shape, 3), dtype=np.uint8)
    result[mask == 1] = [255, 255, 255]
    return result


def overlay_prediction(rgb, prediction):
    result = rgb.copy()
    positive = prediction == 1

    # Red overlay for predicted landslide pixels.
    result[positive] = (
        0.5 * result[positive]
        + 0.5 * np.array([255, 0, 0])
    ).astype(np.uint8)

    return result


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log("Loading checkpoint...")
    checkpoint = torch.load(
        CHECKPOINT, map_location="cpu", weights_only=False
    )

    model = UNet()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    log(f"Checkpoint epoch: {checkpoint.get('epoch')}")
    log(f"Saving images to: {OUTPUT_DIR}")

    completed = 0

    for sample_id in SAMPLE_IDS:
        try:
            log(f"\nProcessing sample {sample_id}")

            image_path = IMAGE_DIR / f"image_{sample_id}.h5"
            mask_path = MASK_DIR / f"mask_{sample_id}.h5"

            if not image_path.exists() or not mask_path.exists():
                log("Skipping: image or mask file missing.")
                continue

            image = np.nan_to_num(
                load_h5(image_path, "img").astype(np.float32)
            )
            ground_truth = (
                load_h5(mask_path, "mask") > 0
            ).astype(np.uint8)

            if image.shape != (128, 128, 14):
                raise ValueError(f"Unexpected image shape: {image.shape}")

            tensor = torch.from_numpy(
                image.transpose(2, 0, 1).copy()
            ).unsqueeze(0)

            log("Running U-Net inference...")
            with torch.inference_mode():
                logits = model(tensor)
                probabilities = torch.sigmoid(logits)[0, 0].numpy()

            prediction = (probabilities >= THRESHOLD).astype(np.uint8)

            tp = int(np.sum((prediction == 1) & (ground_truth == 1)))
            fp = int(np.sum((prediction == 1) & (ground_truth == 0)))
            fn = int(np.sum((prediction == 0) & (ground_truth == 1)))

            dice = 2 * tp / (2 * tp + fp + fn + 1e-7)
            iou = tp / (tp + fp + fn + 1e-7)

            rgb = make_rgb(image)
            slope_rgb = terrain_rgb(image[:, :, 12])
            dem_rgb = terrain_rgb(image[:, :, 13])

            # Convert the four panels to Pillow images.
            
            panels = [
    Image.fromarray(rgb),
    Image.fromarray(mask_rgb(ground_truth)),
    Image.fromarray(dem_rgb),
    Image.fromarray(slope_rgb),
    Image.fromarray(mask_rgb(prediction)),
    Image.fromarray(overlay_prediction(rgb, prediction)),
                      ]

            labels = [
                "Input composite",
                "Ground truth",
                "DEM - channel 13",
                "Slope - channel 12",
                "U-Net prediction",
                "Prediction overlay",
            ]


            resized = [
                panel.resize((PANEL_SIZE, PANEL_SIZE), Image.Resampling.NEAREST)
                for panel in panels
            ]

            label_height = 32
            canvas = Image.new(
                "RGB",
                (PANEL_SIZE * 6, PANEL_SIZE + label_height + 35),
                "white",
            )
            draw = ImageDraw.Draw(canvas)

            for index, panel in enumerate(resized):
                x = index * PANEL_SIZE
                canvas.paste(panel, (x, label_height))
                draw.text((x + 6, 8), labels[index], fill="black")

            draw.text(
                (8, PANEL_SIZE + label_height + 8),
                f"Sample {sample_id} | Dice {dice:.4f} | IoU {iou:.4f}",
                fill="black",
            )

            output_path = OUTPUT_DIR / f"sample_{sample_id}_comparison.png"
            log(f"Saving {output_path}")

            canvas.save(output_path, format="PNG")

            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError("Output image was not saved.")

            completed += 1
            log(
                f"Saved successfully | GT pixels={int(ground_truth.sum())} "
                f"| Predicted pixels={int(prediction.sum())} "
                f"| Dice={dice:.4f} | IoU={iou:.4f}"
            )

        except Exception as exc:
            log(f"ERROR for sample {sample_id}: {exc}")
            traceback.print_exc()

    log(f"\nFinished: {completed}/{len(SAMPLE_IDS)} images saved.")


if __name__ == "__main__":
    main()
