import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import h5py
import torch
import torch.nn as nn
from pathlib import Path


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="Moghalrajpuram Landslide Digital Twin",
    page_icon="🌍",
    layout="wide"
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = (
    BASE_DIR
    / "outputs"
    / "reports"
    / "moghalrajpuram_agent_assessment.csv"
)

RISK_MAP = (
    BASE_DIR
    / "outputs"
    / "maps"
    / "moghalrajpuram_final_risk_map.png"
)


# ---------------------------------------------------------
# Landslide Segmentation Model
# ---------------------------------------------------------

MODEL_FILE = (
    BASE_DIR
    / "models"
    / "landslide_unet_14channel_best.pth"
)


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

    def __init__(self):

        super().__init__()

        self.enc1 = DoubleConv(14, 32)
        self.enc2 = DoubleConv(32, 64)
        self.enc3 = DoubleConv(64, 128)

        self.pool = nn.MaxPool2d(2)

        self.bottleneck = DoubleConv(128, 256)

        self.up3 = nn.ConvTranspose2d(
            256, 128, 2, stride=2
        )

        self.dec3 = DoubleConv(
            256, 128
        )

        self.up2 = nn.ConvTranspose2d(
            128, 64, 2, stride=2
        )

        self.dec2 = DoubleConv(
            128, 64
        )

        self.up1 = nn.ConvTranspose2d(
            64, 32, 2, stride=2
        )

        self.dec1 = DoubleConv(
            64, 32
        )

        self.output = nn.Conv2d(
            32, 1, kernel_size=1
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
# ---------------------------------------------------------
# Load segmentation model
# ---------------------------------------------------------

@st.cache_resource
def load_segmentation_model():

    device = torch.device("cpu")

    model = UNet().to(device)

    checkpoint = torch.load(
        MODEL_FILE,
        map_location=device
    )

    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:

        model.load_state_dict(
            checkpoint["model_state_dict"]
        )

    else:

        model.load_state_dict(
            checkpoint
        )

    model.eval()

    return model, device


segmentation_model, segmentation_device = (
    load_segmentation_model()
)

# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

@st.cache_data
def load_data():

    return pd.read_csv(DATA_FILE)


df = load_data()


# ---------------------------------------------------------
# Title
# ---------------------------------------------------------

st.title(
    "🌍 Landslide Monitoring and Risk Assessment"
)

st.subheader(
    "Remote Sensing-Enabled Digital Twin and Intelligent Agent"
)

st.write(
    "Study Area: Moghalrajpuram, Vijayawada, Andhra Pradesh"
)
# ---------------------------------------------------------
# Uploaded Image Landslide Prediction
# ---------------------------------------------------------

st.header("🛰️ Landslide Detection from Uploaded Image")

st.write(
    "Upload a Landslide4Sense-compatible 14-channel "
    "HDF5 (.h5) satellite image for landslide prediction."
)

uploaded_file = st.file_uploader(
    "Upload 14-channel satellite image",
    type=["h5"]
)


if uploaded_file is not None:

    try:

        # -------------------------------------------------
        # Read uploaded HDF5 image
        # -------------------------------------------------

        with h5py.File(
            uploaded_file,
            "r"
        ) as h5_file:

            if "img" not in h5_file:

                st.error(
                    "Invalid file: 'img' dataset not found."
                )

                st.stop()

            image = h5_file["img"][:]


        # -------------------------------------------------
        # Validate image dimensions
        # -------------------------------------------------

        if image.shape != (128, 128, 14):

            st.error(
                f"Invalid image shape: {image.shape}. "
                "Expected (128, 128, 14)."
            )

            st.stop()


        # -------------------------------------------------
        # Convert image to PyTorch tensor
        # -------------------------------------------------

        image_tensor = torch.tensor(
            image,
            dtype=torch.float32
        )

        image_tensor = (
            image_tensor
            .permute(2, 0, 1)
            .unsqueeze(0)
            .to(segmentation_device)
        )


        # -------------------------------------------------
        # Model prediction
        # -------------------------------------------------

        with torch.no_grad():

            logits = segmentation_model(
                image_tensor
            )

            probability = torch.sigmoid(
                logits
            )[0, 0].cpu().numpy()


        # -------------------------------------------------
        # Binary landslide mask
        # -------------------------------------------------

        prediction_mask = (
            probability >= 0.5
        ).astype(np.uint8)


        # -------------------------------------------------
        # Calculate prediction statistics
        # -------------------------------------------------

        total_pixels = prediction_mask.size

        landslide_pixels = int(
            prediction_mask.sum()
        )

        landslide_percentage = (
            landslide_pixels
            / total_pixels
            * 100
        )


        if landslide_pixels > 0:

            landslide_confidence = float(
                probability[
                    prediction_mask == 1
                ].mean()
            )

        else:

            landslide_confidence = 0.0


        # -------------------------------------------------
        # Display prediction metrics
        # -------------------------------------------------

        st.success(
            "Landslide prediction completed successfully."
        )

        col1, col2, col3 = st.columns(3)


        with col1:

            st.metric(
                "Predicted Landslide Pixels",
                f"{landslide_pixels:,}"
            )


        with col2:

            st.metric(
                "Predicted Landslide Area",
                f"{landslide_percentage:.2f}%"
            )


        with col3:

            st.metric(
                "Average Confidence",
                f"{landslide_confidence * 100:.2f}%"
            )


        # -------------------------------------------------
        # Display probability map and mask
        # -------------------------------------------------

        st.subheader(
            "Landslide Probability Map"
        )

        st.image(
            probability,
            caption=(
                "Pixel-wise Landslide Probability"
            ),
            clamp=True,
            use_container_width=True
        )


        st.subheader(
            "Predicted Landslide Mask"
        )

        st.image(
            prediction_mask * 255,
            caption=(
                "White = Predicted Landslide"
            ),
            clamp=True,
            use_container_width=True
        )


    except Exception as e:

        st.error(
            f"Prediction failed: {e}"
        )


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

st.sidebar.header("Digital Twin Controls")

risk_filter = st.sidebar.multiselect(
    "Select Risk Category",
    options=[
        "Low",
        "Moderate",
        "High",
        "Very High"
    ],
    default=[
        "Low",
        "Moderate",
        "High",
        "Very High"
    ]
)


# ---------------------------------------------------------
# Filter data
# ---------------------------------------------------------

filtered_df = df[
    df["risk_category"].isin(risk_filter)
]


# ---------------------------------------------------------
# Key metrics
# ---------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)


with col1:
    st.metric(
        "Digital Twin Records",
        len(df)
    )


with col2:
    st.metric(
        "High Risk",
        int(
            (df["risk_category"] == "High").sum()
        )
    )


with col3:
    st.metric(
        "Very High Risk",
        int(
            (df["risk_category"] == "Very High").sum()
        )
    )


with col4:
    st.metric(
        "High Confidence",
        int(
            (
                df["insar_confidence"]
                == "High Confidence"
            ).sum()
        )
    )


# ---------------------------------------------------------
# Risk distribution
# ---------------------------------------------------------

st.header("Risk Distribution")

risk_counts = (
    filtered_df["risk_category"]
    .value_counts()
    .reindex(
        [
            "Low",
            "Moderate",
            "High",
            "Very High"
        ],
        fill_value=0
    )
)


fig, ax = plt.subplots(
    figsize=(8, 4)
)

risk_counts.plot(
    kind="bar",
    ax=ax
)

ax.set_xlabel("Risk Category")
ax.set_ylabel("Number of Pixels")
ax.set_title(
    "Moghalrajpuram Risk Distribution"
)

plt.xticks(
    rotation=0
)

plt.tight_layout()

st.pyplot(fig)


# ---------------------------------------------------------
# Risk Map
# ---------------------------------------------------------

st.header("Landslide Risk Map")

if RISK_MAP.exists():

    st.image(
        str(RISK_MAP),
        caption=(
            "Relative Landslide Risk Map – "
            "Moghalrajpuram"
        ),
        use_container_width=True
    )

else:

    st.warning(
        "Risk map not found."
    )


# ---------------------------------------------------------
# Intelligent Agent
# ---------------------------------------------------------

st.header("🤖 Intelligent Agent Assessment")

action_counts = (
    filtered_df["agent_action"]
    .value_counts()
)


st.write(
    "Recommended actions generated by the "
    "rule-based Intelligent Agent."
)


col1, col2 = st.columns(2)


with col1:

    st.dataframe(
        action_counts.rename(
            "Number of Pixels"
        )
    )


with col2:

    st.dataframe(
        filtered_df[
            [
                "twin_id",
                "latitude",
                "longitude",
                "risk_category",
                "risk_score",
                "insar_confidence",
                "agent_action",
                "agent_recommendation"
            ]
        ]
        .sort_values(
            "risk_score",
            ascending=False
        )
        .head(20),
        use_container_width=True
    )


# ---------------------------------------------------------
# Digital Twin Data
# ---------------------------------------------------------

st.header("Digital Twin State")

st.dataframe(
    filtered_df[
        [
            "twin_id",
            "latitude",
            "longitude",
            "elevation_m",
            "slope_deg",
            "los_displacement_m",
            "coherence",
            "reference_daily_rainfall_mm",
            "reference_3day_rainfall_mm",
            "reference_7day_rainfall_mm",
            "risk_score",
            "risk_category",
            "insar_confidence"
        ]
    ],
    use_container_width=True
)


# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------

st.divider()

st.caption(
    "Data sources: Sentinel-1 InSAR, Copernicus DEM, "
    "and GPM IMERG rainfall."
)

st.caption(
    "Risk classes represent a relative evidence index "
    "and are not calibrated landslide probabilities."
)