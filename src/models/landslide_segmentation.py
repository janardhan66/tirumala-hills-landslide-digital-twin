import h5py
import numpy as np
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split


# =====================================================
# 1. DATASET
# =====================================================

class Landslide4SenseDataset(Dataset):

    def __init__(self, image_files):

        self.image_files = image_files

        self.mask_dir = Path(
            "data/raw/landslide4sense/TrainData/mask"
        )

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, index):

        image_path = self.image_files[index]

        image_name = Path(image_path).stem
        number = image_name.split("_")[-1]

        mask_path = (
            self.mask_dir /
            f"mask_{number}.h5"
        )

        with h5py.File(image_path, "r") as f:
            image = f["img"][:]

        with h5py.File(mask_path, "r") as f:
            mask = f["mask"][:]

        image = np.nan_to_num(
            image,
            nan=0.0,
            posinf=0.0,
            neginf=0.0
        )

        image = image.astype(np.float32)

        # HWC -> CHW
        image = np.transpose(
            image,
            (2, 0, 1)
        )

        mask = mask.astype(np.float32)

        # Add channel dimension
        mask = np.expand_dims(
            mask,
            axis=0
        )

        return (
            torch.from_numpy(image),
            torch.from_numpy(mask)
        )


# =====================================================
# 2. U-NET
# =====================================================

class DoubleConv(nn.Module):

    def __init__(self, in_channels, out_channels):

        super().__init__()

        self.block = nn.Sequential(

            nn.Conv2d(
                in_channels,
                out_channels,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(out_channels),

            nn.ReLU(inplace=True),

            nn.Conv2d(
                out_channels,
                out_channels,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(out_channels),

            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.block(x)


class UNet(nn.Module):

    def __init__(
        self,
        in_channels=14,
        out_channels=1
    ):

        super().__init__()

        self.enc1 = DoubleConv(
            in_channels,
            32
        )

        self.enc2 = DoubleConv(
            32,
            64
        )

        self.enc3 = DoubleConv(
            64,
            128
        )

        self.pool = nn.MaxPool2d(
            2,
            2
        )

        self.bottleneck = DoubleConv(
            128,
            256
        )

        self.up3 = nn.ConvTranspose2d(
            256,
            128,
            2,
            2
        )

        self.dec3 = DoubleConv(
            256,
            128
        )

        self.up2 = nn.ConvTranspose2d(
            128,
            64,
            2,
            2
        )

        self.dec2 = DoubleConv(
            128,
            64
        )

        self.up1 = nn.ConvTranspose2d(
            64,
            32,
            2,
            2
        )

        self.dec1 = DoubleConv(
            64,
            32
        )

        self.output = nn.Conv2d(
            32,
            out_channels,
            1
        )

    def forward(self, x):

        e1 = self.enc1(x)

        e2 = self.enc2(
            self.pool(e1)
        )

        e3 = self.enc3(
            self.pool(e2)
        )

        b = self.bottleneck(
            self.pool(e3)
        )

        d3 = self.up3(b)

        d3 = torch.cat(
            [d3, e3],
            dim=1
        )

        d3 = self.dec3(d3)

        d2 = self.up2(d3)

        d2 = torch.cat(
            [d2, e2],
            dim=1
        )

        d2 = self.dec2(d2)

        d1 = self.up1(d2)

        d1 = torch.cat(
            [d1, e1],
            dim=1
        )

        d1 = self.dec1(d1)

        return self.output(d1)


# =====================================================
# 3. DICE LOSS
# =====================================================

class DiceLoss(nn.Module):

    def __init__(self, smooth=1.0):

        super().__init__()

        self.smooth = smooth

    def forward(
        self,
        logits,
        targets
    ):

        probabilities = torch.sigmoid(
            logits
        )

        probabilities = probabilities.view(
            -1
        )

        targets = targets.view(
            -1
        )

        intersection = (
            probabilities * targets
        ).sum()

        dice = (
            2 * intersection +
            self.smooth
        ) / (
            probabilities.sum() +
            targets.sum() +
            self.smooth
        )

        return 1 - dice


# =====================================================
# 4. BCE + DICE LOSS
# =====================================================

class BCEDiceLoss(nn.Module):

    def __init__(self):

        super().__init__()

        self.bce = nn.BCEWithLogitsLoss()

        self.dice = DiceLoss()

    def forward(
        self,
        logits,
        targets
    ):

        return (
            self.bce(logits, targets)
            +
            self.dice(logits, targets)
        )


# =====================================================
# 5. METRICS
# =====================================================

def calculate_metrics(
    logits,
    targets,
    threshold=0.5
):

    probabilities = torch.sigmoid(
        logits
    )

    predictions = (
        probabilities >= threshold
    ).float()

    targets = targets.float()

    intersection = (
        predictions * targets
    ).sum()

    prediction_pixels = predictions.sum()

    target_pixels = targets.sum()

    union = (
        prediction_pixels
        +
        target_pixels
        -
        intersection
    )

    dice = (
        2 * intersection + 1e-7
    ) / (
        prediction_pixels
        +
        target_pixels
        +
        1e-7
    )

    iou = (
        intersection + 1e-7
    ) / (
        union + 1e-7
    )

    return (
        dice.item(),
        iou.item()
    )


# =====================================================
# 6. MAIN TRAINING
# =====================================================

def main():

    print("=" * 60)
    print("LANDSLIDE U-NET FINAL TRAINING")
    print("=" * 60)

    # -------------------------------------------------
    # Device
    # -------------------------------------------------

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print("Device:", device)

    # -------------------------------------------------
    # Files
    # -------------------------------------------------

    image_dir = Path(
        "data/raw/landslide4sense/TrainData/img"
    )

    image_files = sorted(
        str(x)
        for x in image_dir.glob("*.h5")
    )

    print(
        "Total patches:",
        len(image_files)
    )

    # -------------------------------------------------
    # Split
    # -------------------------------------------------

    train_files, val_files = train_test_split(
        image_files,
        test_size=0.20,
        random_state=42
    )

    print(
        "Training patches:",
        len(train_files)
    )

    print(
        "Validation patches:",
        len(val_files)
    )

    # -------------------------------------------------
    # Dataset
    # -------------------------------------------------

    train_dataset = Landslide4SenseDataset(
        train_files
    )

    val_dataset = Landslide4SenseDataset(
        val_files
    )

    # -------------------------------------------------
    # DataLoader
    # -------------------------------------------------

    train_loader = DataLoader(
        train_dataset,
        batch_size=4,
        shuffle=True,
        num_workers=0
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=4,
        shuffle=False,
        num_workers=0
    )

    print(
        "Training batches:",
        len(train_loader)
    )

    print(
        "Validation batches:",
        len(val_loader)
    )

    # -------------------------------------------------
    # Model
    # -------------------------------------------------

    model = UNet(
        in_channels=14,
        out_channels=1
    )

    model = model.to(device)

    # -------------------------------------------------
    # Loss and optimizer
    # -------------------------------------------------

    loss_function = BCEDiceLoss()

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=0.001
    )

    # -------------------------------------------------
    # Training configuration
    # -------------------------------------------------

    epochs = 5

    best_val_dice = 0.0

    model_dir = Path("models")

    model_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    best_model_path = (
        model_dir /
        "landslide_unet_14channel_best.pth"
    )

    # =================================================
    # TRAINING LOOP
    # =================================================

    for epoch in range(epochs):

        print()
        print(
            f"========== Epoch {epoch + 1}/{epochs} =========="
        )

        # -------------------------------------------------
        # Training
        # -------------------------------------------------

        model.train()

        train_loss = 0.0
        train_dice = 0.0
        train_iou = 0.0

        for batch_index, (
            images,
            masks
        ) in enumerate(train_loader):

            images = images.to(device)
            masks = masks.to(device)

            outputs = model(images)

            loss = loss_function(
                outputs,
                masks
            )

            optimizer.zero_grad()

            loss.backward()

            optimizer.step()

            dice, iou = calculate_metrics(
                outputs.detach(),
                masks
            )

            train_loss += loss.item()
            train_dice += dice
            train_iou += iou

            if (
                batch_index + 1
            ) % 100 == 0:

                print(
                    f"Training batch "
                    f"{batch_index + 1}/"
                    f"{len(train_loader)}"
                )

        train_loss /= len(train_loader)
        train_dice /= len(train_loader)
        train_iou /= len(train_loader)

        # -------------------------------------------------
        # Validation
        # -------------------------------------------------

        model.eval()

        val_loss = 0.0
        val_dice = 0.0
        val_iou = 0.0

        with torch.no_grad():

            for (
                images,
                masks
            ) in val_loader:

                images = images.to(device)
                masks = masks.to(device)

                outputs = model(images)

                loss = loss_function(
                    outputs,
                    masks
                )

                dice, iou = calculate_metrics(
                    outputs,
                    masks
                )

                val_loss += loss.item()
                val_dice += dice
                val_iou += iou

        val_loss /= len(val_loader)
        val_dice /= len(val_loader)
        val_iou /= len(val_loader)

        # -------------------------------------------------
        # Results
        # -------------------------------------------------

        print()
        print(
            f"Train Loss:       {train_loss:.4f}"
        )

        print(
            f"Train Dice:       {train_dice:.4f}"
        )

        print(
            f"Train IoU:        {train_iou:.4f}"
        )

        print(
            f"Validation Loss:  {val_loss:.4f}"
        )

        print(
            f"Validation Dice:  {val_dice:.4f}"
        )

        print(
            f"Validation IoU:   {val_iou:.4f}"
        )

        # -------------------------------------------------
        # Save best model
        # -------------------------------------------------

        if val_dice > best_val_dice:

            best_val_dice = val_dice

            torch.save(
                {
                    "model_state_dict":
                        model.state_dict(),

                    "validation_dice":
                        val_dice,

                    "validation_iou":
                        val_iou,

                    "epoch":
                        epoch + 1
                },
                best_model_path
            )

            print()
            print(
                "✓ Best model saved."
            )

    # =================================================
    # FINISHED
    # =================================================

    print()
    print("=" * 60)
    print("TRAINING COMPLETED")
    print("=" * 60)

    print(
        "Best validation Dice:",
        f"{best_val_dice:.4f}"
    )

    print(
        "Best model:",
        best_model_path
    )


if __name__ == "__main__":
    main()