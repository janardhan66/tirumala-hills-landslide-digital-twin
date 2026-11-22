
from pathlib import Path
import h5py
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "landslide4sense"
    / "TrainData"
    / "img"
)

SAMPLE_IDS = [3192, 672, 500]


def load_image(sample_id):
    path = IMAGE_DIR / f"image_{sample_id}.h5"
    with h5py.File(path, "r") as f:
        return np.asarray(f["img"], dtype=np.float32)


def main():
    images = {sid: load_image(sid) for sid in SAMPLE_IDS}

    print("CHANNEL STATISTICS COMPARISON")
    print("Values are mean and standard deviation per channel.\n")

    print(
        f"{'Channel':<10}"
        f"{'3192 mean':>12}{'3192 std':>12}"
        f"{'672 mean':>12}{'672 std':>12}"
        f"{'500 mean':>12}{'500 std':>12}"
    )

    for c in range(14):
        values = []
        for sid in SAMPLE_IDS:
            channel = images[sid][:, :, c]
            values.extend([
                float(np.mean(channel)),
                float(np.std(channel)),
            ])

        print(
            f"{c:<10}"
            f"{values[0]:>12.4f}{values[1]:>12.4f}"
            f"{values[2]:>12.4f}{values[3]:>12.4f}"
            f"{values[4]:>12.4f}{values[5]:>12.4f}"
        )


if __name__ == "__main__":
    main()
