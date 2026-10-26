import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import h5py
import torch
import torch.nn as nn
from pathlib import Path
from datetime import datetime

try:
    import streamlit.components.v1 as components
except Exception:
    components = None


# =========================================================
# PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Tirumala Hills Landslide Monitoring",
    page_icon="🌍",
    layout="wide",
)


# =========================================================
# PROJECT PATHS
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent

FINAL_AGENT_FILE = (
    BASE_DIR
    / "data"
    / "features"
    / "tirumala_final_agent_evidence.csv"
)

FALLBACK_AGENT_FILE = (
    BASE_DIR
    / "outputs"
    / "reports"
    / "moghalrajpuram_agent_assessment.csv"
)

DIGITAL_TWIN_FILE = (
    BASE_DIR
    / "results"
    / "digital_twin"
    / "tirumala_final_digital_twin.html"
)

SEGMENTATION_AGENT_FILE = (
    BASE_DIR
    / "outputs"
    / "reports"
    / "segmentation_agent_assessment.csv"
)

MODEL_FILE = (
    BASE_DIR
    / "models"
    / "landslide_unet_14channel_best.pth"
)


# =========================================================
# CONSTANTS
# =========================================================
EXPECTED_SHAPE = (128, 128, 14)
PREDICTION_THRESHOLD = 0.50


# =========================================================
# U-NET ARCHITECTURE
# IMPORTANT:
# This architecture matches the checkpoint keys:
# enc1.block.0, enc2.block.0, ..., output.weight
# =========================================================
class DoubleConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()

        self.block = nn.Sequential(
            nn.Conv2d(
                in_channels,
                out_channels,
                kernel_size=3,
                padding=1,
            ),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),

            nn.Conv2d(
                out_channels,
                out_channels,
                kernel_size=3,
                padding=1,
            ),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
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
            256,
            128,
            kernel_size=2,
            stride=2,
        )

        self.dec3 = DoubleConv(256, 128)

        self.up2 = nn.ConvTranspose2d(
            128,
            64,
            kernel_size=2,
            stride=2,
        )

        self.dec2 = DoubleConv(128, 64)

        self.up1 = nn.ConvTranspose2d(
            64,
            32,
            kernel_size=2,
            stride=2,
        )

        self.dec1 = DoubleConv(64, 32)

        self.output = nn.Conv2d(
            32,
            1,
            kernel_size=1,
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
            dim=1,
        )
        d3 = self.dec3(d3)

        d2 = self.up2(d3)
        d2 = torch.cat(
            [d2, e2],
            dim=1,
        )
        d2 = self.dec2(d2)

        d1 = self.up1(d2)
        d1 = torch.cat(
            [d1, e1],
            dim=1,
        )
        d1 = self.dec1(d1)

        return self.output(d1)


# =========================================================
# MODEL LOADING
# =========================================================
@st.cache_resource
def load_segmentation_model():
    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"U-Net checkpoint not found:\n{MODEL_FILE}"
        )

    device = torch.device("cpu")

    model = UNet().to(device)

    checkpoint = torch.load(
        MODEL_FILE,
        map_location=device,
    )

    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
        epoch = checkpoint.get("epoch", "N/A")
        validation_dice = checkpoint.get(
            "validation_dice",
            None,
        )
        validation_iou = checkpoint.get(
            "validation_iou",
            None,
        )
    else:
        state_dict = checkpoint
        epoch = "N/A"
        validation_dice = None
        validation_iou = None

    # Handle checkpoints saved with DataParallel.
    cleaned_state_dict = {}

    for key, value in state_dict.items():
        if key.startswith("module."):
            key = key[len("module."):]
        cleaned_state_dict[key] = value

    model.load_state_dict(
        cleaned_state_dict,
        strict=True,
    )

    model.eval()

    return (
        model,
        device,
        epoch,
        validation_dice,
        validation_iou,
    )


# =========================================================
# DATA LOADING
# =========================================================
@st.cache_data
def load_agent_data():
    if FINAL_AGENT_FILE.exists():
        return pd.read_csv(FINAL_AGENT_FILE), "Tirumala final agent evidence"

    if FALLBACK_AGENT_FILE.exists():
        return pd.read_csv(FALLBACK_AGENT_FILE), "Fallback assessment"

    return pd.DataFrame(), "No assessment file"


def safe_number(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def get_first_existing_column(df, names):
    for name in names:
        if name in df.columns:
            return name
    return None


def get_evidence_series(df):
    """Return the project's final evidence classes in a consistent form."""
    evidence_col = get_first_existing_column(
        df,
        [
            "evidence_class",
            "final_agent_evidence",
            "agent_evidence",
            "evidence",
        ],
    )

    if evidence_col is None:
        return None, None

    series = df[evidence_col].fillna("Unknown").astype(str).str.strip()

    # The research CSV stores labels such as "Terrain evidence",
    # while the dashboard legend uses "Terrain". Normalize only the
    # display label; the original CSV column is left unchanged.
    series = series.str.replace(
        r"\s+evidence$",
        "",
        regex=True,
    )

    return series, evidence_col


def agent_decision_from_evidence(evidence_label):
    """Create transparent rule-based agent text from existing evidence."""
    label = str(evidence_label)

    if label == "Multiple spatial + temporal":
        return (
            "Enhanced monitoring",
            "Multiple spatial and temporal evidence is present. Cross-check the location with independent remote-sensing and field evidence.",
        )
    if label == "Multiple spatial":
        return (
            "Enhanced monitoring",
            "Multiple spatial evidence indicators are present. Continue monitoring and cross-check with temporal and field evidence.",
        )
    if label == "InSAR + temporal":
        return (
            "Enhanced monitoring",
            "InSAR monitoring and temporal-change evidence are both present. Review the location against independent evidence.",
        )
    if label == "InSAR monitoring":
        return (
            "InSAR monitoring",
            "InSAR monitoring evidence is present. Continue deformation monitoring and independent validation.",
        )
    if label == "Terrain + temporal":
        return (
            "Terrain and temporal review",
            "Terrain and temporal evidence are present. Review slope conditions and compare with deformation observations.",
        )
    if label == "Terrain":
        return (
            "Terrain review",
            "Terrain evidence is present. Review slope characteristics and compare with other remote-sensing evidence.",
        )
    if label == "Temporal-change":
        return (
            "Temporal-change review",
            "Temporal-change evidence is present. Review the observed change with independent InSAR and field evidence.",
        )

    return (
        "Continue monitoring",
        "No high spatial evidence is identified by the current rule-based integration. This does not establish that the area is safe.",
    )


# =========================================================
# SEGMENTATION AGENT
# =========================================================
def generate_segmentation_agent_decision(
    landslide_percentage,
    average_confidence,
    predicted_pixels,
):
    """
    Transparent evidence-based decision.

    This is NOT a calibrated probability or a geological hazard
    classification. It only summarizes the U-Net prediction.
    """

    if predicted_pixels == 0:
        action = "No segmentation evidence"
        recommendation = (
            "The U-Net did not identify pixels above the "
            "0.50 prediction threshold. Continue monitoring "
            "with independent remote-sensing evidence."
        )

    elif average_confidence >= 0.75:
        action = "Enhanced monitoring"
        recommendation = (
            "The uploaded image contains a non-zero segmented "
            "region with relatively high model confidence. "
            "Review the predicted region against InSAR, terrain, "
            "rainfall, historical GSI evidence, and field evidence."
        )

    else:
        action = "Priority review"
        recommendation = (
            "The U-Net identified a segmented region, but the "
            "average confidence is below 0.75. Cross-check the "
            "prediction with independent remote-sensing and "
            "field evidence before drawing conclusions."
        )

    return action, recommendation


def save_segmentation_agent_assessment(
    filename,
    image_shape,
    predicted_pixels,
    landslide_percentage,
    average_confidence,
    action,
    recommendation,
):
    SEGMENTATION_AGENT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source_file": filename,
        "image_shape": str(tuple(image_shape)),
        "predicted_landslide_pixels": int(predicted_pixels),
        "predicted_landslide_percentage": float(
            landslide_percentage
        ),
        "average_confidence": float(
            average_confidence
        ),
        "prediction_threshold": PREDICTION_THRESHOLD,
        "agent_action": action,
        "agent_recommendation": recommendation,
    }

    pd.DataFrame([row]).to_csv(
        SEGMENTATION_AGENT_FILE,
        index=False,
    )


# =========================================================
# HDF5 READER
# =========================================================
def read_h5_image(uploaded_file):
    uploaded_file.seek(0)

    with h5py.File(
        uploaded_file,
        "r",
    ) as h5_file:

        if "img" not in h5_file:
            raise ValueError(
                "Invalid HDF5 file: the required 'img' dataset "
                "was not found."
            )

        image = np.asarray(
            h5_file["img"][:],
            dtype=np.float32,
        )

    if image.shape != EXPECTED_SHAPE:
        raise ValueError(
            f"Invalid image shape: {image.shape}. "
            f"The trained U-Net expects exactly "
            f"{EXPECTED_SHAPE}."
        )

    if not np.isfinite(image).all():
        raise ValueError(
            "The uploaded image contains NaN or infinite values."
        )

    return image


def run_unet_prediction(image):
    (
        segmentation_model,
        segmentation_device,
        _,
        _,
        _,
    ) = load_segmentation_model()

    image_tensor = torch.from_numpy(
        image
    ).permute(
        2,
        0,
        1,
    ).unsqueeze(
        0
    ).to(
        segmentation_device
    )

    with torch.no_grad():
        logits = segmentation_model(
            image_tensor
        )

        probability = torch.sigmoid(
            logits
        )[0, 0].cpu().numpy()

    prediction_mask = (
        probability >= PREDICTION_THRESHOLD
    ).astype(
        np.uint8
    )

    predicted_pixels = int(
        prediction_mask.sum()
    )

    total_pixels = int(
        prediction_mask.size
    )

    landslide_percentage = (
        predicted_pixels
        / total_pixels
        * 100.0
    )

    if predicted_pixels > 0:
        average_confidence = float(
            probability[
                prediction_mask == 1
            ].mean()
        )
    else:
        average_confidence = 0.0

    return (
        probability,
        prediction_mask,
        predicted_pixels,
        landslide_percentage,
        average_confidence,
    )


def make_rgb_preview(image):
    # The current trained model/data pipeline uses the
    # Landslide4Sense-style 14-channel input.
    # Channels 3,2,1 are used only for visualization.
    rgb_image = image[
        :,
        :,
        [3, 2, 1],
    ].copy()

    rgb_min = rgb_image.min(
        axis=(0, 1),
        keepdims=True,
    )

    rgb_max = rgb_image.max(
        axis=(0, 1),
        keepdims=True,
    )

    rgb_image = (
        (rgb_image - rgb_min)
        / (
            rgb_max
            - rgb_min
            + 1e-8
        )
    )

    return np.clip(
        rgb_image,
        0,
        1,
    )


# =========================================================
# LOAD MODEL
# =========================================================
try:
    (
        segmentation_model,
        segmentation_device,
        model_epoch,
        validation_dice,
        validation_iou,
    ) = load_segmentation_model()

    model_loaded = True

except Exception as model_error:
    segmentation_model = None
    segmentation_device = None
    model_epoch = "N/A"
    validation_dice = None
    validation_iou = None
    model_loaded = False
    model_error_message = str(model_error)


# =========================================================
# LOAD RESEARCH DATA
# =========================================================
df, data_source = load_agent_data()


# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.header("System Information")

if not df.empty:
    st.sidebar.metric(
        "Spatial observations",
        len(df),
    )
else:
    st.sidebar.metric(
        "Spatial observations",
        0,
    )

# The current research pipeline has 2,569 temporal observations.
st.sidebar.metric(
    "Temporal observations",
    2569,
)

st.sidebar.metric(
    "GSI historical locations",
    15,
)

if model_loaded:
    st.sidebar.success(
        "U-Net model loaded"
    )
    st.sidebar.caption(
        f"Model checkpoint epoch: {model_epoch}"
    )
else:
    st.sidebar.error(
        "U-Net model failed to load"
    )
    st.sidebar.caption(
        model_error_message
    )


# =========================================================
# TITLE
# =========================================================
st.title(
    "🌍 Tirumala Hills Landslide Monitoring"
)

st.subheader(
    "Remote Sensing-Enabled Digital Twin and Intelligent Agent"
)

st.write(
    "**Study Area:** Tirumala Hills, Tirupati, Andhra Pradesh"
)

st.write(
    "This research prototype integrates terrain evidence, "
    "Sentinel-1 InSAR monitoring, multi-temporal InSAR change, "
    "rainfall context, historical GSI evidence, and an "
    "explainable intelligent-agent evidence framework."
)


# =========================================================
# SATELLITE DATA INPUT
# =========================================================
st.header(
    "📡 Satellite Data Input"
)

st.write(
    "Upload a Landslide4Sense-compatible 14-channel HDF5 "
    "(.h5) satellite image for U-Net landslide segmentation."
)

uploaded_file = st.file_uploader(
    "Upload 14-channel satellite image",
    type=["h5"],
    help=(
        "The trained checkpoint expects an HDF5 file containing "
        "an 'img' dataset with shape (128, 128, 14)."
    ),
)

st.info(
    "The current trained U-Net accepts only a 14-channel HDF5 "
    "input with shape (128, 128, 14). A normal GeoTIFF or "
    "Sentinel-1 ZIP cannot be passed directly to this model "
    "without a separate preprocessing/conversion pipeline."
)


# =========================================================
# UPLOADED IMAGE PREDICTION
# =========================================================
if uploaded_file is not None:

    if not model_loaded:
        st.error(
            "Prediction cannot start because the U-Net "
            "checkpoint failed to load."
        )

    else:
        try:
            image = read_h5_image(
                uploaded_file
            )

            (
                probability,
                prediction_mask,
                predicted_pixels,
                landslide_percentage,
                average_confidence,
            ) = run_unet_prediction(
                image
            )

            (
                agent_action,
                agent_recommendation,
            ) = generate_segmentation_agent_decision(
                landslide_percentage,
                average_confidence,
                predicted_pixels,
            )

            # Save latest dynamic U-Net agent assessment.
            save_segmentation_agent_assessment(
                filename=uploaded_file.name,
                image_shape=image.shape,
                predicted_pixels=predicted_pixels,
                landslide_percentage=landslide_percentage,
                average_confidence=average_confidence,
                action=agent_action,
                recommendation=agent_recommendation,
            )

            st.success(
                "U-Net landslide segmentation completed successfully."
            )

            st.subheader(
                "Uploaded Image Assessment"
            )

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Predicted Landslide Pixels",
                    f"{predicted_pixels:,}",
                )

            with col2:
                st.metric(
                    "Predicted Area",
                    f"{landslide_percentage:.2f}%",
                )

            with col3:
                st.metric(
                    "Average Confidence",
                    f"{average_confidence * 100:.2f}%",
                )

            with col4:
                st.metric(
                    "Agent Action",
                    agent_action,
                )

            st.write(
                f"**Uploaded file:** `{uploaded_file.name}`"
            )

            st.write(
                "**Important:** The segmentation output is "
                "model evidence from the uploaded image. It is "
                "not a calibrated landslide probability."
            )

            st.subheader(
                "Landslide Probability Map"
            )

            st.image(
                probability,
                caption=(
                    "Pixel-wise U-Net landslide probability"
                ),
                clamp=True,
                use_container_width=True,
            )

            st.subheader(
                "Predicted Landslide Mask"
            )

            st.image(
                prediction_mask * 255,
                caption=(
                    "White = pixels predicted as landslide "
                    f"(threshold = {PREDICTION_THRESHOLD:.2f})"
                ),
                clamp=True,
                use_container_width=True,
            )

            st.subheader(
                "Landslide Detection Overlay"
            )

            rgb_image = make_rgb_preview(
                image
            )

            overlay = rgb_image.copy()

            overlay[
                prediction_mask == 1
            ] = [1.0, 0.0, 0.0]

            st.image(
                overlay,
                caption=(
                    "Red = predicted landslide regions"
                ),
                clamp=True,
                use_container_width=True,
            )

            st.subheader(
                "U-Net Intelligent-Agent Interpretation"
            )

            if agent_action == "Priority review":
                st.warning(
                    agent_recommendation
                )
            elif agent_action == "Enhanced monitoring":
                st.info(
                    agent_recommendation
                )
            else:
                st.success(
                    agent_recommendation
                )

        except Exception as prediction_error:
            st.error(
                f"Prediction failed: {prediction_error}"
            )


# =========================================================
# CURRENT RESEARCH ASSESSMENT
# =========================================================
st.header(
    "📊 Current Research Assessment"
)

if df.empty:

    st.warning(
        "No Tirumala final agent evidence CSV was found."
    )

    st.code(
        str(FINAL_AGENT_FILE),
        language="text",
    )

else:

    evidence_series, evidence_col = get_evidence_series(df)

    if evidence_series is not None:

        counts = evidence_series.value_counts()

        # Display the current research evidence categories.
        preferred_labels = [
            "Multiple spatial + temporal",
            "Multiple spatial",
            "InSAR + temporal",
            "InSAR monitoring",
            "Terrain + temporal",
            "Terrain",
            "Temporal-change",
            "No high spatial",
        ]

        metric_values = []

        for label in preferred_labels:
            metric_values.append(
                (
                    label,
                    int(
                        counts.get(
                            label,
                            0,
                        )
                    ),
                )
            )

        # Show the four principal categories first.
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "Multiple spatial + temporal",
                metric_values[0][1],
            )

        with c2:
            st.metric(
                "Multiple spatial",
                metric_values[1][1],
            )

        with c3:
            st.metric(
                "InSAR + temporal",
                metric_values[2][1],
            )

        with c4:
            st.metric(
                "No high spatial evidence",
                metric_values[7][1],
            )

        st.subheader(
            "Agent Evidence Distribution"
        )

        evidence_display = pd.Series(
            {
                label: value
                for label, value in metric_values
            }
        )

        st.bar_chart(
            evidence_display
        )

    else:

        st.info(
            "The final evidence CSV does not contain a recognized "
            "evidence-class column. The raw assessment is shown below."
        )


# =========================================================
# RAINFALL CONTEXT
# =========================================================
st.header(
    "🌧️ Rainfall Context"
)

# Use the research values currently integrated into the
# Tirumala Digital Twin.
rainfall_values = [
    ("Latest daily rainfall", "0.0 mm"),
    ("3-day rainfall", "0.2 mm"),
    ("7-day rainfall", "9.3 mm"),
    ("14-day rainfall", "11.5 mm"),
]

r1, r2, r3, r4 = st.columns(4)

with r1:
    st.metric(
        rainfall_values[0][0],
        rainfall_values[0][1],
    )

with r2:
    st.metric(
        rainfall_values[1][0],
        rainfall_values[1][1],
    )

with r3:
    st.metric(
        rainfall_values[2][0],
        rainfall_values[2][1],
    )

with r4:
    st.metric(
        rainfall_values[3][0],
        rainfall_values[3][1],
    )

st.caption(
    "Rainfall values represent IMERG rainfall context and "
    "should not be interpreted as an 80 m rainfall layer."
)


# =========================================================
# DIGITAL TWIN
# =========================================================
st.header(
    "🗺️ Digital Twin"
)

st.write(
    "Integrated spatial evidence, temporal InSAR change, "
    "historical GSI locations, and rainfall context."
)

if DIGITAL_TWIN_FILE.exists():

    try:
        html_content = DIGITAL_TWIN_FILE.read_text(
            encoding="utf-8"
        )

        if components is not None:
            components.html(
                html_content,
                height=700,
                scrolling=True,
            )
        else:
            st.warning(
                "Streamlit HTML component is unavailable."
            )

    except Exception as map_error:
        st.error(
            f"Digital Twin could not be displayed: {map_error}"
        )

else:

    st.warning(
        "Tirumala Digital Twin HTML file was not found."
    )

    st.code(
        str(DIGITAL_TWIN_FILE),
        language="text",
    )


# =========================================================
# INTELLIGENT AGENT
# =========================================================
st.header(
    "🤖 Intelligent Agent"
)

st.write(
    "Explainable recommendations generated from the "
    "current evidence-based Digital Twin assessment."
)

if not df.empty:

    # Build a dashboard-only view so the existing research CSV can be
    # displayed even though its evidence column is named
    # `final_agent_evidence` rather than `evidence_class`.
    agent_display = df.copy()
    evidence_series, evidence_col = get_evidence_series(agent_display)

    if evidence_series is not None:
        agent_display["evidence_class"] = evidence_series

        decisions = agent_display["evidence_class"].apply(
            agent_decision_from_evidence
        )
        agent_display["agent_action"] = decisions.apply(
            lambda value: value[0]
        )
        agent_display["agent_recommendation"] = decisions.apply(
            lambda value: value[1]
        )

    # Prefer the research coordinates/evidence plus transparent agent output.
    agent_columns = [
        "twin_id",
        "row",
        "col",
        "latitude",
        "longitude",
        "risk_score",
        "risk_category",
        "evidence_class",
        "agent_action",
        "agent_recommendation",
    ]

    available_agent_columns = [
        column
        for column in agent_columns
        if column in agent_display.columns
    ]

    if available_agent_columns:
        st.dataframe(
            agent_display[available_agent_columns].head(50),
            use_container_width=True,
            height=420,
        )
    else:
        st.dataframe(
            agent_display.head(50),
            use_container_width=True,
            height=420,
        )


# =========================================================
# U-NET MODEL INFORMATION
# =========================================================
st.header(
    "🧠 U-Net Model Information"
)

if model_loaded:

    st.success(
        "Checkpoint loaded successfully"
    )

    m1, m2, m3 = st.columns(3)

    with m1:
        st.metric(
            "Checkpoint Epoch",
            model_epoch,
        )

    with m2:
        if validation_dice is not None:
            st.metric(
                "Validation Dice",
                f"{safe_number(validation_dice):.4f}",
            )
        else:
            st.metric(
                "Validation Dice",
                "N/A",
            )

    with m3:
        if validation_iou is not None:
            st.metric(
                "Validation IoU",
                f"{safe_number(validation_iou):.4f}",
            )
        else:
            st.metric(
                "Validation IoU",
                "N/A",
            )

else:

    st.error(
        "The U-Net checkpoint could not be loaded."
    )

    st.code(
        model_error_message,
        language="text",
    )


# =========================================================
# LATEST U-NET AGENT REPORT
# =========================================================
st.header(
    "🧩 Latest U-Net Segmentation Agent Report"
)

if SEGMENTATION_AGENT_FILE.exists():

    try:
        segmentation_df = pd.read_csv(
            SEGMENTATION_AGENT_FILE
        )

        if not segmentation_df.empty:

            segmentation_row = (
                segmentation_df.iloc[0]
            )

            s1, s2, s3 = st.columns(3)

            with s1:
                st.metric(
                    "Predicted Landslide Area",
                    f"{safe_number(segmentation_row.get('predicted_landslide_percentage', 0)):.2f}%",
                )

            with s2:
                st.metric(
                    "Average Confidence",
                    f"{safe_number(segmentation_row.get('average_confidence', 0)) * 100:.2f}%",
                )

            with s3:
                st.metric(
                    "Agent Action",
                    str(
                        segmentation_row.get(
                            "agent_action",
                            "N/A",
                        )
                    ),
                )

            st.write(
                "**Source file:** "
                + str(
                    segmentation_row.get(
                        "source_file",
                        "N/A",
                    )
                )
            )

            st.write(
                "**Agent Recommendation:** "
                + str(
                    segmentation_row.get(
                        "agent_recommendation",
                        "N/A",
                    )
                )
            )

    except Exception as report_error:

        st.warning(
            f"Could not read the segmentation-agent report: "
            f"{report_error}"
        )

else:

    st.info(
        "Upload a valid 14-channel HDF5 image to generate "
        "the latest U-Net segmentation-agent report."
    )


# =========================================================
# DIGITAL TWIN DATA
# =========================================================
st.header(
    "📋 Digital Twin State"
)

if not df.empty:

    preferred_columns = [
        "twin_id",
        "row",
        "col",
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
        "insar_confidence",
        "evidence_class",
        "final_agent_evidence",
    ]

    twin_display = df.copy()
    evidence_series, _ = get_evidence_series(twin_display)
    if evidence_series is not None:
        twin_display["evidence_class"] = evidence_series

    available_columns = [
        column
        for column in preferred_columns
        if column in twin_display.columns
    ]

    if available_columns:
        st.dataframe(
            twin_display[
                available_columns
            ],
            use_container_width=True,
            height=450,
        )
    else:
        st.dataframe(
            df,
            use_container_width=True,
            height=450,
        )

else:

    st.info(
        "Digital Twin state data is not available."
    )


# =========================================================
# FOOTER
# =========================================================
st.divider()

st.caption(
    "Data sources: Sentinel-1 InSAR, Copernicus DEM, "
    "GPM IMERG rainfall, and historical GSI evidence."
)

st.caption(
    "Risk/evidence classes are relative evidence indicators "
    "and are not calibrated landslide probabilities."
)

st.caption(
    "The uploaded U-Net segmentation result is model evidence "
    "and should be cross-checked with independent remote-sensing "
    "and field evidence."
)
