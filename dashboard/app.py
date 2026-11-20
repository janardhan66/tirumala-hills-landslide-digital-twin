import streamlit as st
import hashlib
import pandas as pd
import numpy as np
import h5py
import torch
import torch.nn as nn
from pathlib import Path
from datetime import datetime
import streamlit.components.v1 as components
import sys

# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Tirumala Hills Landslide Monitoring",
    page_icon="🌍",
    layout="wide",
)

# ============================================================
# PROJECT PATHS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.digital_twin.terrain_3d import (
    TERRAIN_OVERLAYS,
    TerrainViewError,
    create_terrain_figure,
)

FINAL_AGENT_FILE = (
    BASE_DIR
    / "data"
    / "features"
    / "tirumala_final_agent_evidence.csv"
)
TEMPORAL_FEATURE_FILE = (
    BASE_DIR
    / "data"
    / "features"
    / "tirumala_temporal_insar_features.csv"
)

RAIN_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "rainfall"
    / "tirumala"
    / "tirumala_rainfall_features_20260801_20260829.csv"
)

GSI_VALIDATION_FILE = (
    BASE_DIR
    / "data"
    / "features"
    / "tirumala_gsi_validation_table.csv"
)

DIGITAL_TWIN_FILE = (
    BASE_DIR
    / "results"
    / "digital_twin"
    / "tirumala_final_digital_twin.html"
)

MODEL_FILE = (
    BASE_DIR
    / "models"
    / "landslide_unet_14channel_best.pth"
)

# Independent validation and reference-region assessment outputs
REFERENCE_ASSESSMENT_FILE = (
    BASE_DIR / "outputs" / "final_reference_region_assessment_v2"
    / "final_reference_region_comparison.csv"
)
MORAN_SUMMARY_FILE = (
    BASE_DIR / "outputs" / "moran_permutation_test_v1"
    / "moran_permutation_summary.csv"
)
REFERENCE_ROBUSTNESS_FILE = (
    BASE_DIR / "outputs" / "reference_region_robustness_v1"
    / "reference_region_robustness_summary.csv"
)
COOLR_SPATIAL_CHECK_FILE = (
    BASE_DIR / "outputs" / "coolr_tirumala_investigation_v2"
    / "coolr_event_aoi_spatial_check.csv"
)
COOLR_REPORT_FILE = (
    BASE_DIR / "outputs" / "coolr_historical_validation_report_v1"
    / "tirumala_coolr_historical_validation_report.txt"
)
REFITTED_PLANE_FILE = (
    BASE_DIR / "outputs" / "boundary_refitted_plane_analysis_v1"
    / "refitted_plane_summary.csv"
)

SEGMENTATION_AGENT_FILE = (
    BASE_DIR
    / "outputs"
    / "reports"
    / "segmentation_agent_assessment.csv"
)

SEGMENTATION_REPORT_PREFIX = "segmentation_agent_assessment_"

EXPECTED_SHAPE = (128, 128, 14)
PREDICTION_THRESHOLD = 0.50


# ============================================================
# U-NET MODEL
# ============================================================
class DoubleConv(nn.Module):

    def __init__(
        self,
        in_channels,
        out_channels
    ):
        super().__init__()

        self.block = nn.Sequential(

            nn.Conv2d(
                in_channels,
                out_channels,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(
                out_channels
            ),

            nn.ReLU(
                inplace=True
            ),

            nn.Conv2d(
                out_channels,
                out_channels,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(
                out_channels
            ),

            nn.ReLU(
                inplace=True
            ),
        )

    def forward(self, x):

        return self.block(x)


class UNet(nn.Module):

    def __init__(self):

        super().__init__()

        self.enc1 = DoubleConv(
            14,
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
            2
        )

        self.bottleneck = DoubleConv(
            128,
            256
        )

        self.up3 = nn.ConvTranspose2d(
            256,
            128,
            kernel_size=2,
            stride=2
        )

        self.dec3 = DoubleConv(
            256,
            128
        )

        self.up2 = nn.ConvTranspose2d(
            128,
            64,
            kernel_size=2,
            stride=2
        )

        self.dec2 = DoubleConv(
            128,
            64
        )

        self.up1 = nn.ConvTranspose2d(
            64,
            32,
            kernel_size=2,
            stride=2
        )

        self.dec1 = DoubleConv(
            64,
            32
        )

        self.output = nn.Conv2d(
            32,
            1,
            kernel_size=1
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

        d3 = self.dec3(
            torch.cat(
                [
                    self.up3(b),
                    e3
                ],
                dim=1
            )
        )

        d2 = self.dec2(
            torch.cat(
                [
                    self.up2(d3),
                    e2
                ],
                dim=1
            )
        )

        d1 = self.dec1(
            torch.cat(
                [
                    self.up1(d2),
                    e1
                ],
                dim=1
            )
        )

        return self.output(d1)


# ============================================================
# LOAD MODEL
# ============================================================
@st.cache_resource
def load_segmentation_model():

    if not MODEL_FILE.exists():

        raise FileNotFoundError(
            f"U-Net checkpoint not found:\n"
            f"{MODEL_FILE}"
        )

    device = torch.device(
        "cpu"
    )

    model = UNet().to(
        device
    )

    checkpoint = torch.load(
        MODEL_FILE,
        map_location=device
    )

    if (
        isinstance(checkpoint, dict)
        and "model_state_dict" in checkpoint
    ):

        state_dict = checkpoint[
            "model_state_dict"
        ]

    else:

        state_dict = checkpoint

    cleaned_state_dict = {}

    for key, value in state_dict.items():

        if key.startswith(
            "module."
        ):

            key = key[7:]

        cleaned_state_dict[
            key
        ] = value

    model.load_state_dict(
        cleaned_state_dict,
        strict=True
    )

    model.eval()

    if isinstance(
        checkpoint,
        dict
    ):

        epoch = checkpoint.get(
            "epoch",
            "N/A"
        )

        validation_dice = checkpoint.get(
            "validation_dice"
        )

        validation_iou = checkpoint.get(
            "validation_iou"
        )

    else:

        epoch = "N/A"
        validation_dice = None
        validation_iou = None

    return (
        model,
        device,
        epoch,
        validation_dice,
        validation_iou
    )


# ============================================================
# LOAD RESEARCH DATA
# ============================================================
@st.cache_data
def load_final_agent_data():

    if FINAL_AGENT_FILE.exists():

        return pd.read_csv(
            FINAL_AGENT_FILE
        )

    return pd.DataFrame()
@st.cache_data
def load_temporal_feature_data():
    """Load temporal InSAR feature records safely."""
    if not TEMPORAL_FEATURE_FILE.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(TEMPORAL_FEATURE_FILE)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.warning(
            f"Could not load temporal InSAR features: {exc}"
        )
        return pd.DataFrame()

@st.cache_data
def load_rainfall_data():

    if RAIN_FILE.exists():

        return pd.read_csv(
            RAIN_FILE
        )

    return pd.DataFrame()


@st.cache_data
def load_gsi_validation_data():
    if not GSI_VALIDATION_FILE.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(GSI_VALIDATION_FILE)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.warning(f"Could not load GSI validation locations: {exc}")
        return pd.DataFrame()


try:

    (
        segmentation_model,
        segmentation_device,
        model_epoch,
        validation_dice,
        validation_iou
    ) = load_segmentation_model()

    model_loaded = True
    model_error = None

except Exception as e:

    segmentation_model = None

    segmentation_device = torch.device(
        "cpu"
    )

    model_epoch = "N/A"

    validation_dice = None

    validation_iou = None

    model_loaded = False

    model_error = str(e)


df = load_final_agent_data()

rainfall_df = load_rainfall_data()
gsi_df = load_gsi_validation_data()


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def safe_float(
    value,
    default=0.0
):

    try:

        value = float(value)

        if (
            np.isnan(value)
            or np.isinf(value)
        ):

            return default

        return value

    except Exception:

        return default


def get_first_existing_column(
    dataframe,
    candidates
):

    for column in candidates:

        if column in dataframe.columns:

            return column

    return None


def get_evidence_column(
    dataframe
):

    return get_first_existing_column(
        dataframe,
        [
            "evidence_class",
            "final_agent_evidence",
            "agent_evidence",
            "final_evidence_class",
            "evidence",
            "evidence_category"
        ]
    )


def get_evidence_series(
    dataframe
):

    column = get_evidence_column(
        dataframe
    )

    if column is None:

        return None, None

    series = (
        dataframe[column]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    series = series.str.replace(
        r"\s+evidence$",
        "",
        regex=True
    )

    return series, column


# ============================================================
# EXISTING RESEARCH AGENT DECISION
# ============================================================
def research_agent_decision(
    label
):

    label = str(label)

    decisions = {

        "Multiple spatial + temporal": (
            "Enhanced monitoring",
            "Multiple spatial and temporal evidence is present. Cross-check the location with independent remote-sensing and field evidence."
        ),

        "Multiple spatial": (
            "Enhanced monitoring",
            "Multiple spatial evidence indicators are present. Continue monitoring and cross-check with temporal and field evidence."
        ),

        "InSAR + temporal": (
            "Enhanced monitoring",
            "InSAR monitoring and temporal-change evidence are both present. Review the location against independent evidence."
        ),

        "InSAR monitoring": (
            "InSAR monitoring",
            "InSAR monitoring evidence is present. Continue deformation monitoring and independent validation."
        ),

        "Terrain + temporal": (
            "Terrain and temporal review",
            "Terrain and temporal evidence are present. Review slope conditions and compare with deformation observations."
        ),

        "Terrain": (
            "Terrain review",
            "Terrain evidence is present. Review slope characteristics and compare with other remote-sensing evidence."
        ),

        "Temporal-change": (
            "Temporal-change review",
            "Temporal-change evidence is present. Review the observed change with independent InSAR and field evidence."
        ),
    }

    return decisions.get(
        label,
        (
            "Continue monitoring",
            "No high spatial evidence is identified by the current rule-based integration. This does not establish that the area is safe."
        )
    )


# ============================================================
# UPLOADED-IMAGE SCREENING BAND
# ============================================================
# These are provisional display bands based only on the percentage
# of pixels segmented by U-Net. They are NOT calibrated landslide-risk
# thresholds and must be validated against labelled independent data.
IMAGE_COVERAGE_LOW_MAX = 1.0
IMAGE_COVERAGE_MEDIUM_MAX = 5.0


def classify_uploaded_image_coverage(area_percent):
    """Describe predicted mask coverage; do not interpret as probability."""
    if area_percent < IMAGE_COVERAGE_LOW_MAX:
        return "Low", (
            f"Less than {IMAGE_COVERAGE_LOW_MAX:.1f}% of pixels were segmented."
        )
    if area_percent < IMAGE_COVERAGE_MEDIUM_MAX:
        return "Medium", (
            f"{IMAGE_COVERAGE_LOW_MAX:.1f}% to less than "
            f"{IMAGE_COVERAGE_MEDIUM_MAX:.1f}% of pixels were segmented."
        )
    return "High", (
        f"{IMAGE_COVERAGE_MEDIUM_MAX:.1f}% or more of pixels were segmented."
    )


# ============================================================
# U-NET SEGMENTATION AGENT
# ============================================================
def segmentation_agent_decision(
    area_percent,
    confidence,
    predicted_pixels
):

    if predicted_pixels == 0:

        return (
            "No segmentation evidence",
            (
                f"The U-Net did not identify pixels above the "
                f"{PREDICTION_THRESHOLD:.2f} prediction threshold. "
                "Continue monitoring with independent remote-sensing evidence."
            )
        )

    if confidence >= 0.75:

        return (
            "Enhanced monitoring",
            (
                "The uploaded image contains a non-zero segmented "
                "region whose mean predicted-positive model score is "
                "at least 0.75. This score is not calibrated confidence. "
                "Review the predicted region against InSAR, terrain, "
                "rainfall, historical GSI evidence, and field evidence."
            )
        )

    return (
        "Priority review",
        (
            "The U-Net identified a segmented region, but the "
            "mean predicted-positive model score is below 0.75. "
            "This score is not calibrated confidence. Cross-check "
            "the prediction with independent remote-sensing and "
            "field evidence before drawing conclusions."
        )
    )


# ============================================================
# INTEGRATED INTELLIGENT AGENT
# ============================================================
def integrated_agent_decision(
    predicted_pixels,
    area_percent,
    confidence,
    research_count
):

    if predicted_pixels == 0:

        return (
            "Continue monitoring",
            (
                f"The uploaded U-Net image contains no pixels above "
                f"the {PREDICTION_THRESHOLD:.2f} prediction threshold. "
                f"The existing research evidence contains "
                f"{research_count:,} spatial observations. "
                "Continue evaluating the area using InSAR, terrain, "
                "temporal, rainfall, historical GSI, and field evidence."
            )
        )

    if confidence >= 0.75:

        return (
            "Enhanced monitoring",
            (
                f"The uploaded U-Net image contains a segmented region "
                f"covering {area_percent:.2f}% of the image, with average "
                f"predicted-positive model score of {confidence * 100:.2f}%. "
                f"The existing research evidence contains "
                f"{research_count:,} spatial observations. "
                "Treat the U-Net result as additional segmentation "
                "evidence and cross-check the predicted region with "
                "InSAR deformation, temporal change, terrain, rainfall, "
                "historical GSI evidence, and field observations."
            )
        )

    return (
        "Priority review",
        (
            f"The uploaded U-Net image contains a segmented region "
            f"covering {area_percent:.2f}% of the image, but average "
            f"predicted-positive model score is "
            f"{confidence * 100:.2f}%. "
            f"The existing research evidence contains "
            f"{research_count:,} spatial observations. "
            "Review the U-Net prediction against independent "
            "remote-sensing and field evidence before drawing conclusions."
        )
    )

# ============================================================
# INTELLIGENT AGENT - QUESTION ANSWERING
# ============================================================

def answer_project_question(
    question,
    dataframe,
    rainfall_dataframe,
    gsi_dataframe=None,
    temporal_dataframe=None,
):
    """
    Grounded question-answering agent.
    Answers only from available project data.
    """

    q = question.lower().strip()

    def numeric_values(frame, column):
        if frame is None or frame.empty or column not in frame.columns:
            return pd.Series(dtype="float64")
        return pd.to_numeric(frame[column], errors="coerce").dropna()

    asks_limitations = any(
        word in q for word in ["limitation", "limitations", "caveat", "caveats"]
    )

    if (
        not asks_limitations
        and any(word in q for word in ["risk", "evidence", "landslide"])
        and any(word in q for word in ["current", "overall", "evidence", "risk"])
        and not any(
            topic in q
            for topic in [
                "insar",
                "sentinel-1",
                "sentinel 1",
                "terrain",
                "slope",
                "elevation",
                "rainfall",
                "gsi",
                "u-net",
                "unet",
                "segmentation",
                "digital twin",
                "spatial",
                "temporal",
            ]
        )
        and not dataframe.empty
    ):
        category_column = get_first_existing_column(
            dataframe,
            ["final_agent_evidence", "agent_evidence_category"],
        )
        category_counts = (
            dataframe[category_column]
            .fillna("Unknown")
            .astype(str)
            .value_counts()
            .head(5)
            if category_column
            else pd.Series(dtype="int64")
        )
        spatial_evidence = numeric_values(
            dataframe, "spatial_evidence_count"
        )
        temporal_flags = numeric_values(
            dataframe, "temporal_evidence_flag"
        )
        lines = [
            "Current Tirumala Hills evidence summary:",
            f"- Spatial records available: {len(dataframe):,}.",
        ]
        if not spatial_evidence.empty:
            lines.append(
                f"- Records with at least one high spatial indicator: "
                f"{int((spatial_evidence >= 1).sum()):,}."
            )
        if not temporal_flags.empty:
            lines.append(
                f"- Records flagged for temporal-change evidence: "
                f"{int((temporal_flags >= 1).sum()):,}."
            )
        if not category_counts.empty:
            lines.append("- Most common evidence categories:")
            lines.extend(
                f"  - {label}: {int(count):,}"
                for label, count in category_counts.items()
            )
        lines.extend(
            [
                "",
                "These are rule-based evidence categories, not calibrated "
                "landslide probabilities or confirmations. The evidence "
                "supports monitoring and review; it does not establish a "
                "reliable future-landslide prediction or operational warning.",
            ]
        )
        return "\n".join(lines)

    if (
        any(word in q for word in ["insar", "sentinel-1", "sentinel 1"])
        and any(
            word in q
            for word in ["explain", "evidence", "monitoring", "current", "overview"]
        )
        and not asks_limitations
    ):
        temporal_count = (
            len(temporal_dataframe)
            if temporal_dataframe is not None
            else 0
        )
        mean_abs_change = numeric_values(
            temporal_dataframe, "abs_los_change_m"
        ) * 1000.0
        mean_pair1_correlation = numeric_values(
            temporal_dataframe, "corr_05_17"
        )
        mean_pair2_correlation = numeric_values(
            temporal_dataframe, "corr_17_29"
        )
        lines = [
            "The project contains two descending Sentinel-1 InSAR pairs:",
            "- 5–17 August 2026.",
            "- 17–29 August 2026.",
            f"- The temporal feature table has {temporal_count:,} records.",
        ]
        if not mean_pair1_correlation.empty:
            lines.append(
                f"- Mean pair coherence in the temporal table: "
                f"{mean_pair1_correlation.mean():.3f} for the first pair and "
                f"{mean_pair2_correlation.mean():.3f} for the second pair."
            )
        if not mean_abs_change.empty:
            lines.append(
                f"- Mean absolute stored pair difference: "
                f"{mean_abs_change.mean():.2f} mm (descriptive only)."
            )
        lines.extend(
            [
                "",
                "Important interpretation: the pair products use independently "
                "selected phase-reference points approximately 89 km apart. "
                "Their direct subtraction is not established as physically "
                "valid displacement. Treat the stored difference as an "
                "unharmonized exploratory value, not confirmed movement. "
                "LOS is a one-direction projection, not full 3D motion; the "
                "dataset alone does not confirm a landslide.",
            ]
        )
        return "\n".join(lines)

    if (
        any(word in q for word in ["terrain", "slope", "elevation"])
        and any(word in q for word in ["what", "explain", "evidence", "summary"])
        and not asks_limitations
    ):
        slopes = numeric_values(dataframe, "slope_deg")
        elevations = numeric_values(dataframe, "elevation_m")
        lines = ["Terrain and slope are supporting spatial evidence:"]
        if not slopes.empty:
            lines.append(
                f"- Spatial records with slope values: {len(slopes):,}; "
                f"mean slope {slopes.mean():.2f}° "
                f"(range {slopes.min():.2f}–{slopes.max():.2f}°)."
            )
        if not elevations.empty:
            lines.append(
                f"- Mean elevation: {elevations.mean():.1f} m "
                f"(range {elevations.min():.1f}–{elevations.max():.1f} m)."
            )
        lines.append(
            "The dashboard combines terrain categories with other evidence. "
            "Slope or elevation alone does not predict or confirm a landslide."
        )
        return "\n".join(lines)

    if (
        "rainfall" in q
        and any(word in q for word in ["what", "explain", "context", "summary", "current"])
        and not any(
            word in q
            for word in ["latest", "3-day", "3 day", "7-day", "7 day", "14-day", "14 day"]
        )
        and not asks_limitations
    ):
        if rainfall_dataframe.empty:
            return "The rainfall feature dataset is currently unavailable."
        date_column = get_first_existing_column(
            rainfall_dataframe, ["date", "Date", "timestamp"]
        )
        daily = numeric_values(rainfall_dataframe, "rainfall_mean_mm")
        message = [
            "Rainfall is included as study-area-level temporal context, "
            "not as a pixel-specific spatial predictor."
        ]
        if date_column and not daily.empty:
            dates = pd.to_datetime(
                rainfall_dataframe[date_column], errors="coerce"
            )
            valid_dates = dates.dropna()
            message.append(
                f"- Available daily records: {len(valid_dates):,} "
                f"({valid_dates.min():%d %b %Y} to {valid_dates.max():%d %b %Y})."
            )
            message.append(
                f"- Mean daily rainfall over valid records: "
                f"{daily.mean():.2f} mm."
            )
            for column, label in [
                ("rainfall_3day_mm", "3-day"),
                ("rainfall_7day_mm", "7-day"),
                ("rainfall_14day_mm", "14-day"),
            ]:
                values = numeric_values(rainfall_dataframe, column)
                if not values.empty:
                    message.append(
                        f"- Most recent available {label} accumulation: "
                        f"{values.iloc[-1]:.2f} mm."
                    )
        message.append(
            "Rainfall provides context for interpreting monitoring evidence; "
            "it does not independently confirm a landslide."
        )
        return "\n".join(message)

    if (
        any(word in q for word in ["gsi", "historical location", "historical inventory"])
        and any(word in q for word in ["what", "explain", "evidence", "location", "where"])
        and not asks_limitations
    ):
        if gsi_dataframe is None or gsi_dataframe.empty:
            return "The GSI historical-location table is currently unavailable."
        approximate_count = (
            int(
                gsi_dataframe.get(
                    "coordinate_quality",
                    pd.Series(index=gsi_dataframe.index, dtype="object"),
                )
                .astype(str)
                .str.contains("approximate|map-derived", case=False, regex=True)
                .sum()
            )
        )
        lines = [
            f"The project contains {len(gsi_dataframe):,} GSI historical-location "
            "records in its validation table.",
        ]
        if approximate_count:
            lines.append(
                f"- {approximate_count:,} are marked as approximate/map-derived "
                "coordinates."
            )
        lines.append(
            "These locations provide historical context, not surveyed GPS "
            "ground truth. Proximity to a mapped point is not model accuracy."
        )
        return "\n".join(lines)

    if (
        any(word in q for word in ["spatial", "temporal", "observations", "matched"])
        and any(word in q for word in ["how many", "count", "records", "observations", "matched"])
        and not asks_limitations
    ):
        spatial_count = len(dataframe) if dataframe is not None else 0
        temporal_count = len(temporal_dataframe) if temporal_dataframe is not None else 0
        matched_count = 0
        if (
            dataframe is not None
            and not dataframe.empty
            and "temporal_available" in dataframe.columns
        ):
            matched_count = int(
                dataframe["temporal_available"]
                .fillna(False)
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["true", "1", "yes"])
                .sum()
            )
        return (
            f"The current datasets contain {spatial_count:,} spatial records and "
            f"{temporal_count:,} temporal records. "
            f"{matched_count:,} spatial records are marked as having matched "
            f"temporal evidence; {spatial_count - matched_count:,} are unmatched. "
            "These counts describe records, not separate landslides. Missing "
            "temporal evidence is unavailable evidence, not proof of no movement."
        )

    if (
        any(word in q for word in ["u-net", "unet", "segmentation"])
        and any(word in q for word in ["what", "explain", "result", "score", "prediction"])
        and not any(
            word in q
            for word in ["dice", "iou", "intersection over union", "threshold", "input", "hdf5"]
        )
        and not asks_limitations
    ):
        report_files = []
        if SEGMENTATION_AGENT_FILE.exists():
            report_files.append(SEGMENTATION_AGENT_FILE)
        report_files.extend(
            SEGMENTATION_AGENT_FILE.parent.glob(
                f"{SEGMENTATION_REPORT_PREFIX}*.csv"
            )
        )
        latest = None
        if report_files:
            latest_path = max(report_files, key=lambda path: path.stat().st_mtime)
            try:
                saved_report = pd.read_csv(latest_path)
                if not saved_report.empty:
                    latest = saved_report.iloc[-1]
            except (OSError, ValueError, pd.errors.ParserError):
                latest = None
        response = [
            "The 14-channel U-Net produces pixel-level sigmoid scores and a "
            f"binary segmentation at threshold {PREDICTION_THRESHOLD:.2f}. "
            "The score is not calibrated landslide probability or accuracy."
        ]
        if latest is not None:
            response.append(
                f"- Latest saved example: {latest.get('source_file', 'unknown file')}, "
                f"{safe_float(latest.get('predicted_landslide_pixels')):,} predicted "
                f"pixels ({safe_float(latest.get('predicted_landslide_percentage')):.2f}% "
                f"of the patch), mean predicted-positive score "
                f"{safe_float(latest.get('average_confidence')) * 100:.2f}%."
            )
        if validation_dice is not None and validation_iou is not None:
            response.append(
                f"- Checkpoint validation metrics: Dice "
                f"{safe_float(validation_dice):.4f}, IoU "
                f"{safe_float(validation_iou):.4f}; these are validation-set "
                "overlap metrics, not Tirumala-specific ground-truth validation."
            )
        response.append(
            "The input must be an HDF5 file with an 'img' dataset of the "
            "expected 128×128×14 shape. Predictions are not automatically "
            "georeferenced or added to the Digital Twin map."
        )
        return "\n".join(response)

    if (
        "digital twin" in q
        and any(word in q for word in ["what", "explain", "integration", "integrate", "map"])
        and not any(word in q for word in ["u-net", "unet", "segmentation"])
        and not asks_limitations
    ):
        return (
            "The Tirumala dashboard keeps its Leaflet-based 2D map as the default "
            "and offers an optional experimental Plotly 3D terrain view based "
            "on the local DEM. The 3D view can be colored by elevation, slope, "
            "Pair 2 correlation, or Pair 2 LOS displacement. Rainfall is "
            "contextual information, and uploaded U-Net masks are not "
            "georeferenced or automatically integrated as map layers."
        )

    if (
        any(word in q for word in ["agent", "recommendation", "recommend"])
        and any(word in q for word in ["what", "explain", "how", "recommend"])
        and not asks_limitations
    ):
        return (
            "The Intelligent Agent is a transparent, rule-based evidence "
            "integration component. It maps the available terrain, InSAR and "
            "temporal evidence classes to review or monitoring recommendations. "
            "Rainfall and GSI records provide context; they do not make the "
            "recommendation a calibrated probability. Actions are prompts for "
            "human review, not operational warnings or guaranteed predictions."
        )

    if (
    "positive" in q
    and "negative" in q
    and ("los" in q or "line-of-sight" in q)
):
        return """
    In our Tirumala Hills project, Sentinel-1 InSAR measures
    ground displacement along the satellite's Line-of-Sight (LOS).

    - Positive LOS displacement indicates movement towards the satellite.
    - Negative LOS displacement indicates movement away from the satellite.

    Positive does not automatically mean upward movement.
    Negative does not automatically mean downward movement.

    LOS displacement is a projection of ground movement along
    the radar viewing direction. A single Sentinel-1 viewing
    geometry cannot independently separate vertical and
    horizontal ground movement.

    Therefore, our project reports LOS displacement rather
    than independently validated 3D ground movement.
    """
    if (
    "spatial_evidence_count" in q
    or "final_evidence_class" in q
    or (
        "evidence class" in q
        and "temporal" in q
    )
):
        return """
    In our Tirumala Hills Digital Twin, spatial_evidence_count and
    final_evidence_class represent two different evidence summaries.

    1. spatial_evidence_count:
    It is the sum of two binary indicators:
    - terrain_high_evidence
    - insar_high_evidence

    Its value ranges from 0 to 2:
    - 0: Neither indicator is high.
    - 1: Exactly one indicator is high.
    - 2: Both indicators are high.

    2. final_evidence_class:
    This is a descriptive evidence category based on the original
    spatial evidence category and the availability and value of
    temporal_evidence_flag.

    Temporal evidence helps refine the final evidence category.
    Missing temporal records must be treated as unavailable evidence,
    not automatically as negative evidence.
    
    Positive LOS displacement means movement towards the satellite,
while negative LOS displacement means movement away from the
satellite. These signs describe movement along the radar
line-of-sight direction, not necessarily upward or downward
vertical movement.

    Neither spatial_evidence_count nor final_evidence_class is a
    calibrated landslide probability. They are descriptive,
    rule-based evidence indicators, not guaranteed predictions.
    """
    if (
    ("2650" in q or "2569" in q or "spatial" in q)
    and ("temporal" in q or "matched" in q or "unmatched" in q)
):
        return """
    Our project contains 2,650 spatial observations and 2,569
    temporal observations.

    These counts differ because spatial and temporal observations
    are generated from different evidence datasets.

    The spatial and temporal datasets are matched using their
    row and col coordinates.

    Out of 2,650 spatial observations:
    - 2,293 have matching temporal records.
    - 357 do not have matching temporal records.

    The 357 observations represent missing temporal evidence,
    not confirmed absence of landslide activity.

    Missing temporal evidence must not be interpreted as zero
    movement or negative landslide evidence.

    The 2,569 temporal observations represent the separate
    temporal dataset count. The 357 unmatched records refer
    to spatial observations without matching temporal records.
    """
    if (
    ("1052" in q or "0.9100" in q or "91%" in q)
    and ("unet" in q or "prediction" in q or "model" in q)
        ):
            return """
        The U-Net prediction example identified 1,052 landslide pixels out of
        16,384 total pixels in the uploaded image.

        This represents approximately 6.42% of the image classified as
        landslide by the model.

        The average model output score was 0.9100. This is the reported
        average model output score, not a calibrated 91% probability that
        a real landslide exists.

        The model uses a sigmoid output and a 0.5 threshold to classify
        pixels. A score at or above the threshold is classified as a
        landslide pixel; a score below it is classified as non-landslide.

        These predictions are model outputs, not confirmed landslides.
        Their reliability depends on training data, validation performance,
        input quality and independent field validation.

        The current segmentation mask is not georeferenced or integrated
        into the Digital Twin map.
        """
    # Step 15.42: U-Net prediction pipeline
       # Step 15.43: Explain U-Net Dice score and IoU
    if (
        ("dice" in q or "iou" in q or "intersection over union" in q)
        and ("unet" in q or "segmentation" in q or "landslide" in q)
    ):
        return """
        Dice score and Intersection over Union (IoU) are evaluation
        metrics used to measure the overlap between predicted and
        ground-truth landslide segmentation masks.

        1. Dice score:
        Measures the overlap between predicted landslide pixels
        and actual ground-truth landslide pixels.
        Its range is 0 to 1. A higher value indicates better overlap.

        2. Intersection over Union (IoU):
        Measures the intersection between predicted and
        ground-truth landslide regions divided by their union.
        Its range is 0 to 1. A higher value indicates better overlap.

        Our trained U-Net achieved:
        - Validation Dice score: 0.6561
        - Validation IoU: 0.5101
        - Epoch: 3

        These values indicate that the model achieved partial
        agreement between predicted and ground-truth segmentation
        regions on the validation dataset.

        However, these metrics do not guarantee reliable real-world
        landslide detection in Tirumala Hills because:

        - Validation performance depends on the dataset used.
        - The validation dataset may not represent local Tirumala
        terrain and satellite conditions.
        - Independent field validation is not established.
        - The segmentation mask is not yet georeferenced and
        integrated into the Digital Twin map.
        - Performance must be evaluated across additional locations
        and independent datasets.

        Therefore, Dice and IoU measure segmentation overlap,
        not guaranteed real-world landslide detection accuracy.
        """
    if (
        ("sigmoid" in q or "threshold" in q or "prediction process" in q
        or "prediction pipeline" in q or "checkpoint" in q)
        and ("unet" in q or "u-net" in q or "segmentation" in q)
    ):
        return """
        The U-Net prediction process in our project follows these steps:

        1. Upload:
        The user uploads an HDF5 (.h5) file containing an "img"
        dataset with expected shape (128, 128, 14).

        2. Data loading:
        The dashboard reads the "img" dataset using HDF5
        and converts the image into a PyTorch tensor.

        3. Model loading:
        The trained 14-channel U-Net architecture is initialized
        and its trained weights are loaded from
        models/landslide_unet_14channel_best.pth.

        4. Prediction:
        The input tensor is passed through the U-Net model
        to generate pixel-wise logits.

        5. Sigmoid activation:
        torch.sigmoid(logits) converts the logits into
        output scores between 0 and 1.

        6. Thresholding:
        A threshold of 0.5 is applied. Pixels with scores
        greater than or equal to 0.5 are classified as
        landslide pixels; the remaining pixels are classified
        as non-landslide pixels.

        7. Output:
        The dashboard generates a binary landslide
        segmentation mask and visualizes the prediction.

        The output is a segmentation result, not a calibrated
        landslide probability or an independently validated
        real-world landslide prediction.
        """
    # Step 15.41: U-Net input requirements
    if (
        ("input" in q or "hdf5" in q or "geotiff" in q
        or "geoTIFF" in q or "zip file" in q)
        and ("14-channel" in q or "unet" in q or "u-net" in q)
    ):
        return """
        Our project uses a 14-channel U-Net model for landslide
        segmentation.

        Input requirements:

        1. File format: HDF5 file with .h5 extension.
        2. Dataset key: The HDF5 file must contain a dataset named "img".
        3. Expected input shape: (128, 128, 14).
        4. The 14 channels represent the model input features.

        A normal Sentinel-1 GeoTIFF or ZIP file cannot be uploaded
        directly because it does not automatically satisfy the
        expected HDF5 structure and 14-channel input shape.

        Preprocessing or conversion is necessary to prepare the
        satellite data in the format expected by the trained model.

        The dashboard reads the "img" dataset, converts it into
        a tensor, and passes it to the U-Net model for prediction.
        """
    # Step 15.39: Atmospheric effects and phase-unwrapping limitations
    if (
        ("atmospher" in q or "phase-unwrapping" in q
        or "phase unwrapping" in q)
        and ("insar" in q or "displacement" in q)
    ):
        return """
        Atmospheric disturbances can introduce additional phase delays
        in Sentinel-1 radar observations. These delays may appear as
        apparent displacement and can affect the accuracy of small
        InSAR LOS displacement measurements.

        Phase-unwrapping errors occur when the wrapped interferometric
        phase is incorrectly converted into continuous phase values.
        Such errors can introduce incorrect displacement estimates
        or spatial inconsistencies.

        In our current Tirumala Hills project, atmospheric effects
        have not been fully corrected and these errors have not been
        independently validated through field measurements.

        Therefore, small LOS displacement values must be interpreted
        cautiously. They may contain contributions from actual ground
        movement, atmospheric effects, processing errors, or noise.

        InSAR displacement is preliminary monitoring evidence,
        not independent confirmation of landslide movement.

        Further atmospheric correction, phase-quality assessment,
        additional acquisition dates, and independent GNSS/GPS
        field validation are needed.
        """

    # Step 15.37: Explain rainfall accumulation windows
    if (
        "3-day" in q or "3 day" in q
    ) and (
        "7-day" in q or "7 day" in q
    ) and (
        "14-day" in q or "14 day" in q
    ) and not any(
        term in q
        for term in [
            "latest",
            "most recent",
            "value",
            "amount",
            "how much",
            "29 august 2026",
            "2026-08-29",
        ]
    ):
        return """
        The project uses NASA GPM/IMERG accumulated rainfall features
        over three different time windows:

        1. 3-day rainfall:
        Represents recent rainfall over the preceding three days.
        It helps understand short-term rainfall conditions.

        2. 7-day rainfall:
        Represents accumulated rainfall over the preceding seven days.
        It provides a broader view of rainfall during the recent week.

        3. 14-day rainfall:
        Represents accumulated rainfall over the preceding fourteen days.
        It helps understand rainfall conditions over a longer period.

        These different windows provide short-term and longer-duration
        rainfall context for interpreting landslide monitoring evidence.

        Rainfall can help identify conditions that may contribute to
        slope instability, but rainfall alone does not confirm a landslide.

        In this project, rainfall is supporting monitoring context.
        It does not directly contribute to spatial_evidence_count
        or final_evidence_class.
        """
    if (
    "moran" in q
    and ("region 1" in q or "region1" in q)
    and ("positive" in q or "spatial autocorrelation" in q or "unstable" in q)
    ):
        return """
        In our Region 1 reference-region assessment, significant positive
        Moran's I indicates positive spatial autocorrelation in the
        InSAR residuals. This means nearby observations tend to have
        similar residual values, indicating spatial structure rather
        than a completely random spatial pattern.

        Region 1 results:
        - Pair 1: Moran's I = +0.29516, Holm-adjusted p = 0.0004.
        - Pair 2: Moran's I = +0.80012, Holm-adjusted p = 0.0004.

        Does this prove instability?
        No. Significant positive spatial autocorrelation does not
        independently prove that Region 1 is unstable or contaminated
        by deformation.

        Difference:
        - Spatial autocorrelation describes the spatial pattern of
        residual values.
        - Reference-region stability concerns whether the selected
        reference area is genuinely stable and suitable for measuring
        relative ground displacement.

        A spatially structured residual pattern may warrant further
        investigation, but it cannot independently establish the
        physical stability or instability of the reference region.

        Therefore, Region 1 remains a stronger provisional reference
        candidate than Region 3, but it is not a confirmed stable
        reference region.

        Independent GNSS/GPS measurements, additional consistent
        InSAR observations, and further validation are required.
        """
    if (
    "reference point" in q
    and "reference region" in q
):
        return """
        An InSAR reference point is a selected pixel or location
        used as the relative displacement reference for an InSAR
        measurement. Displacement values are interpreted relative
        to this selected reference.

        An InSAR reference region is a group of candidate pixels
        assessed to determine whether an area may be suitable as
        a stable reference for displacement measurements.

        Why did we assess Region 1 and Region 3?

        Relying only on a single reference point does not establish
        that the surrounding area is stable. Assessing candidate
        regions allows us to compare multiple characteristics:

        - Area and spatial extent.
        - Mean terrain slope.
        - Distance from historical GSI locations.
        - InSAR correlation quality.
        - Residual spatial autocorrelation using Moran's I.

        Region 1 was identified as a stronger provisional candidate
        than Region 3 based on its larger area, gentler slope,
        greater GSI separation and correlation assessment.

        Scientific importance:
        Region-based assessment provides broader spatial evidence
        when evaluating the suitability of an InSAR reference area.

        Limitations:
        These metrics do not independently prove physical stability.
        Region 1 is not a confirmed stable reference region.
        Independent GNSS/GPS measurements and additional consistent
        InSAR observations are required.

        Therefore, reference-point selection and reference-region
        assessment are related but different parts of InSAR analysis.
        """
    if (
    ("region 1" in q or "region 1" in q)
    and "region 3" in q
    and ("reference" in q or "moran" in q or "stable" in q)
   ):
        return """
        Region 1 is considered a stronger provisional InSAR reference
        candidate than Region 3 based on several assessment metrics.

        1. Slope and area:
        Region 1 covers 91.52 ha with a mean slope of 2.524 degrees.
        Region 3 covers 19.84 ha with a mean slope of 3.386 degrees.
        Region 1 has a larger area and gentler terrain.

        2. GSI distance:
        Region 1 has a minimum distance of approximately 374.7 m
        from GSI historical locations.
        Region 3 has a minimum distance of approximately 249.8 m.
        Region 1 has greater separation.

        3. Correlation quality:
        Region 1 mean correlation:
        Pair 1 = 0.888102; Pair 2 = 0.856940.

        Region 3 mean correlation:
        Pair 1 = 0.859717; Pair 2 = 0.859421.

        Region 1 has better correlation in Pair 1, while
        Region 3 is marginally better in Pair 2.

        4. Moran's I:
        Region 1 Pair 1: +0.29516, significant.
        Region 1 Pair 2: +0.80012, significant.

        Region 3 Pair 1: -0.11756, not significant.
        Region 3 Pair 2: +0.18428, not significant.

        Significant positive spatial autocorrelation in Region 1
        indicates spatial structure in the residuals. It does not
        prove instability or stability.

        Conclusion:
        Region 1 is the stronger provisional reference candidate,
        but neither Region 1 nor Region 3 is confirmed stable.
        Independent GNSS/GPS observations and additional consistent
        InSAR measurements are required for validation.
        """
    if (
    ("two" in q or "2" in q or "pairs" in q)
    and ("insar" in q or "sentinel" in q)
    and ("limitation" in q or "limited" in q or "monitoring" in q)
    ):
        return ("""
        Our Tirumala Hills Digital Twin uses two Sentinel-1 InSAR pairs:

        1. Temporal coverage:
        Pair 1: 5–17 August 2026.
        Pair 2: 17–29 August 2026.
        These provide only three unique acquisition dates.
        This is insufficient to establish a robust long-term displacement
        trend or seasonal ground-movement pattern.

        2. Different reference points:
        The two pairs use reference points approximately 89 km apart.
        InSAR displacement is relative to its selected reference point.
        Therefore, values from the two pairs cannot be directly subtracted
        to represent temporal ground movement without a consistent
        reference framework and additional processing.

        3. LOS interpretation:
        InSAR measures displacement projected along the satellite
        Line of Sight (LOS), not complete 3D ground movement.
        A single viewing geometry cannot independently separate
        vertical and horizontal displacement components.

        Therefore, the two pairs provide preliminary deformation-monitoring
        evidence, not definitive proof of landslide movement.
        More consistent reference processing, additional acquisition dates,
        ascending and descending observations, and independent field
        validation are needed.
        """)
    if (
    "insar" in q
    and "displacement" in q
    and "correlation" in q
    and "residual" in q
):
        return """
        Our Tirumala Hills project uses three different InSAR concepts.

        1. InSAR displacement:
        Measures relative ground displacement projected along the
        satellite Line of Sight (LOS). It is used for deformation
        monitoring. It does not independently provide complete 3D
        ground movement.

        2. InSAR correlation:
        Measures radar correspondence between acquisitions and
        indicates measurement quality.
        In our implementation, insar_quality_acceptable is 1
        when correlation >= 0.5 and 0 otherwise.
        Low correlation produces a quality warning in agent_explanation.
        It does not automatically change the original spatial
        evidence category.

        3. InSAR residuals:
        Represent differences between observed values and the fitted
        reference-model or plane values in the reference-region
        assessment. They are used to examine spatial patterns and
        evaluate candidate reference regions.
        Moran's I is used to assess spatial autocorrelation in
        these residuals.

        These concepts must not be confused:
        - Displacement describes measured relative movement.
        - Correlation describes radar measurement quality.
        - Residuals describe deviations from the fitted reference model.

        High correlation does not prove stability.
        Spatially structured residuals do not prove instability.
        Independent validation is required to establish physical
        reference-region stability.
        """
    
        # Specific question: InSAR displacement vs correlation vs slope
    if (
        "displacement" in q
        and "correlation" in q
        and ("slope" in q or "terrain" in q)
    ):
        return (
            "InSAR displacement, InSAR correlation and terrain slope "
            "are three different variables in the project.\n\n"

            "1. InSAR displacement: Represents ground movement "
            "projected along the Sentinel-1 satellite's Line of Sight "
            "(LOS). It helps identify possible surface deformation.\n\n"

            "2. InSAR correlation: Indicates how well radar observations "
            "correspond between acquisitions. It helps assess the "
            "quality and reliability of displacement measurements. "
            "Our project uses a correlation threshold of 0.5 for "
            "insar_quality_acceptable.\n\n"

            "3. Terrain slope: Calculated from DEM elevation data. "
            "It describes the steepness of the terrain and contributes "
            "to the terrain evidence component.\n\n"

            "In summary, displacement describes possible ground movement, "
            "correlation describes measurement quality, and slope "
            "describes terrain steepness. The Intelligent Agent "
            "interprets available terrain, InSAR and temporal evidence "
            "for landslide monitoring. None of these variables alone "
            "confirms a landslide."
        )
    # Specific question: Real-time monitoring and temporal coverage
    if (
        ("real-time" in q or "realtime" in q)
        and (
            "temporal coverage" in q
            or "acquisition frequency" in q
            or "data acquisition" in q
            or "monitoring" in q
        )
    ):
        return (
            "The Tirumala Hills Landslide Digital Twin is a research "
            "prototype, not a continuous real-time monitoring or "
            "warning system.\n\n"

            "1. Sentinel-1 InSAR: The project uses two acquisition "
            "pairs: 5-17 August 2026 and 17-29 August 2026. "
            "These provide three unique acquisition dates: "
            "5, 17 and 29 August 2026.\n\n"

            "2. Rainfall: NASA GPM/IMERG rainfall features cover "
            "1-29 August 2026.\n\n"

            "3. Temporal coverage limitation: The available InSAR "
            "observations cover a limited period and do not provide "
            "continuous ground movement measurements. The project "
            "does not demonstrate automatic real-time satellite "
            "data updates or continuous monitoring.\n\n"

            "4. Other limitations: InSAR requires quality assessment, "
            "U-Net predictions are not integrated into the mapped "
            "Digital Twin evidence layers, and the Intelligent Agent "
            "uses rule-based evidence categories rather than calibrated "
            "landslide-risk probabilities.\n\n"

            "Therefore, the current system supports research-based "
            "monitoring and expert interpretation, not real-time "
            "landslide prediction or operational warnings."
        )
        # Specific question: Intelligent Agent decision-making
    if (
        "intelligent agent" in q
        and ("recommendation" in q or "monitoring" in q)
        and (
            "machine learning" in q
            or "predefined rules" in q
            or "how does" in q
            or "generated" in q
        )
    ):
        return (
            "The Intelligent Agent uses predefined, explainable "
            "rule-based evidence integration. Its monitoring "
            "recommendations are not generated by a separate "
            "machine-learning model.\n\n"

            "The Agent interprets available evidence, including:\n"
            "1. Terrain evidence derived from DEM and slope.\n"
            "2. InSAR displacement and correlation quality.\n"
            "3. Temporal evidence from available observations.\n"
            "4. Historical GSI locations as supporting context.\n\n"

            "Based on the applicable evidence rules, it generates "
            "monitoring actions and recommendations such as normal "
            "monitoring, enhanced monitoring and expert review.\n\n"

            "These are rule-based monitoring recommendations, not "
            "calibrated landslide-risk probabilities or guaranteed "
            "predictions. The exact conditions for each action depend "
            "on the implemented decision rules."
        )
        # Specific question: 75th percentile temporal threshold
    if (
        "75th percentile" in q
        or (
            "percentile" in q
            and ("temporal" in q or "threshold" in q)
        )
    ):
        return (
            "The project uses the 75th percentile of absolute "
            "temporal LOS change as an exploratory, data-dependent "
            "threshold.\n\n"

            "1. Calculation: The temporal evidence script converts "
            "absolute temporal LOS change from metres to millimetres "
            "by multiplying abs_los_change_m by 1000.\n\n"

            "2. Threshold: It calculates the 75th percentile of "
            "the absolute temporal change distribution.\n\n"

            "3. Classification: Observations with absolute temporal "
            "change greater than or equal to the threshold receive "
            "temporal_evidence_flag = 1 and are labelled Elevated "
            "temporal-change evidence. Other available observations "
            "receive flag = 0 and are labelled Lower temporal-change "
            "evidence.\n\n"

            "4. Scientific calibration: This threshold is not a "
            "scientifically calibrated landslide threshold. It is "
            "relative to the available dataset.\n\n"

            "5. Limitations: The threshold depends on the dataset "
            "distribution and may change with different observations "
            "or time periods. A positive temporal flag indicates "
            "relatively elevated change, not proof of a landslide.\n\n"

            "Therefore, the 75th percentile is an exploratory "
            "classification threshold for monitoring evidence, "
            "not a validated landslide detection threshold."
        )
    # Specific question: rainfall contribution to evidence classification
    if (
        "rainfall" in q
        and (
            "spatial_evidence_count" in q
            or "spatial evidence count" in q
            or "final_evidence_class" in q
            or "final evidence class" in q
        )
    ):
        return (
            "No. Rainfall does not directly contribute to "
            "spatial_evidence_count or final_evidence_class.\n\n"
            "1. spatial_evidence_count is calculated from the "
            "two spatial indicators: terrain_high_evidence and "
            "insar_high_evidence.\n\n"
            "2. final_evidence_class is assigned using the "
            "spatial evidence category and the availability "
            "and value of temporal_evidence_flag.\n\n"
            "3. NASA GPM/IMERG rainfall features provide "
            "additional rainfall context for monitoring and "
            "interpreting conditions in the study area. They "
            "are not directly used to calculate these two "
            "evidence classification fields.\n\n"
            "Rainfall information is contextual evidence, "
            "not proof of a landslide."
        )

    

    
    # Specific question: spatial evidence count vs final evidence class
    if (
    (
        "spatial_evidence_count" in q
        or ("spatial" in q and "evidence count" in q)
    )
    and (
        "final_evidence_class" in q
        or ("final" in q and "evidence class" in q)
    )
):
        return (
            "The difference is:\n\n"
            "1. spatial_evidence_count: Counts two binary spatial "
            "indicators, terrain_high_evidence and insar_high_evidence. "
            "It ranges from 0 to 2 and does not include temporal evidence.\n\n"
            "2. final_evidence_class: A descriptive category assigned "
            "using the original spatial evidence category and the "
            "availability and value of temporal_evidence_flag. "
            "Examples include 'Multiple spatial + temporal evidence', "
            "'InSAR + temporal evidence', and 'Terrain evidence'.\n\n"
            "In short, spatial_evidence_count is a numeric count of "
            "high spatial indicators, whereas final_evidence_class "
            "describes the combined monitoring evidence.\n\n"
            "Neither is a calibrated landslide probability or proof "
            "that a landslide occurred."
        )
        # Specific question: observations with both spatial and temporal evidence
    if (
        "spatial" in q
        and "temporal" in q
        and any(word in q for word in ["how many", "count", "number"])
        and any(word in q for word in ["both", "combined", "together"])
    ):
        return (
            "Based on tirumala_final_agent_evidence.csv:\n\n"
            "- Multiple spatial + temporal evidence: 238 observations.\n"
            "- InSAR + temporal evidence: 186 observations.\n"
            "- Terrain + temporal evidence: 34 observations.\n\n"
            "Total: 458 observations have positive temporal-change "
            "evidence combined with a spatial evidence category.\n\n"
            "The 238 observations specifically have both high terrain "
            "and high InSAR indicators, along with positive temporal "
            "evidence. The other two categories combine temporal evidence "
            "with only one high spatial indicator.\n\n"
            "These are exploratory monitoring indicators, not calibrated "
            "landslide probabilities. Observations with unavailable "
            "temporal data are not automatically treated as negative evidence."
        )
    

        # Specific question: unavailable temporal observations
    if (
        "357" in q
        and ("unavailable" in q or "missing" in q)
        and ("why" in q or "classified" in q or "final" in q)
    ):
        return (
            "The project has 2,650 spatial observations and 2,569 "
            "temporal observations. After merging on row and col "
            "coordinates, 357 spatial observations have no matching "
            "temporal record.\n\n"
            "The current code identifies these records as temporally "
            "unavailable, but it does not establish the underlying "
            "reason for every unmatched record.\n\n"
            "In the final dataset, unavailable temporal evidence does "
            "not independently trigger a temporal evidence category. "
            "The classification follows the available spatial evidence "
            "and the existing classification rules. Missing temporal "
            "data must not be interpreted as confirmed negative evidence."
        )
        # Specific question: Multiple spatial + temporal evidence
    if (
        "multiple spatial" in q
        and "temporal" in q
        and any(word in q for word in ["condition", "classified", "cause", "when"])
    ):
        return (
            "An observation is classified as 'Multiple spatial + temporal "
            "evidence' when all three conditions are satisfied:\n\n"
            "1. Its original spatial category is 'Terrain + InSAR evidence'.\n"
            "2. A matching temporal record is available after merging "
            "on row and col coordinates.\n"
            "3. Its temporal_evidence_flag equals 1.\n\n"
            "The temporal flag indicates elevated temporal-change evidence "
            "according to the dataset's exploratory 75th-percentile "
            "threshold. It does not prove that a landslide occurred. "
            "Missing temporal records do not qualify for this category."
        )
    # Specific question: spatial and temporal record counts
    if (
        any(word in q for word in [
            "how many", "count", "number", "counts"
        ])
        and any(word in q for word in [
            "spatial", "temporal", "observations", "records"
        ])
        and any(word in q for word in [
            "available", "unavailable", "final"
        ])
    ):
        return (
            "According to the latest successful run of "
            "create_final_agent_evidence.py:\n\n"
            "- Final spatial observations: 2,650\n"
            "- Temporal records available: 2,293\n"
            "- Temporal records unavailable: 357\n\n"
            "The available and unavailable counts sum to the "
            "2,650 final spatial observations. Temporal records "
            "are matched using row and col coordinates. These counts "
            "describe dataset records, not confirmed landslides."
        )
    
    # Specific question: spatial evidence count distribution
    if (
        "spatial" in q
        and any(phrase in q for phrase in [
            "how many", "distribution", "count of", "counts"
        ])
        and any(value in q for value in [
            "0", "1", "2", "evidence count"
        ])
    ):
        return (
            "Spatial evidence count distribution from "
            "tirumala_agent_evidence.csv:\n\n"
            "- Evidence count 0: 1,357 observations (51.21%).\n"
            "- Evidence count 1: 820 observations (30.94%).\n"
            "- Evidence count 2: 473 observations (17.85%).\n\n"
            "Total: 2,650 observations.\n\n"
            "The count is the sum of two binary indicators: "
            "terrain_high_evidence and insar_high_evidence. "
            "A count of 0 means neither indicator is high; "
            "a count of 1 means exactly one is high; and a "
            "count of 2 means both are high. These are "
            "rule-based indicators, not calibrated landslide probabilities."
        )
    

        # Specific question: combining spatial and temporal evidence
    if (
        "spatial" in q
        and "temporal" in q
        and any(word in q for word in [
            "how", "combine", "combined", "integrate",
            "integration", "evidence", "assign", "rule", "rules"
        ])
    ):
        return (
            "Spatial and temporal evidence are combined in "
            "create_final_agent_evidence.py.\n\n"
            "1. The script reads the spatial and temporal CSV files.\n"
            "2. It matches observations using their row and col "
            "coordinates.\n"
            "3. It checks whether temporal evidence is available "
            "and whether temporal_evidence_flag equals 1.\n"
            "4. It combines that temporal flag with the original "
            "spatial category to assign the final evidence class.\n\n"
            "Examples:\n"
            "- Terrain + InSAR evidence with a positive available "
            "temporal flag becomes Multiple spatial + temporal evidence.\n"
            "- InSAR monitoring evidence with a positive available "
            "temporal flag becomes InSAR + temporal evidence.\n"
            "- Terrain evidence with a positive available temporal "
            "flag becomes Terrain + temporal evidence.\n"
            "- If no positive available temporal flag is present, "
            "the resulting class depends on the original spatial "
            "category and the classification rules.\n\n"
            "Missing temporal records are marked unavailable; they "
            "are not automatically treated as confirmed negative evidence. "
            "These categories are monitoring indicators, not calibrated "
            "landslide probabilities."
        )
    
    # Specific question: final evidence-class distribution
    if (
        any(phrase in q for phrase in [
            "distribution", "how many", "counts", "count of"
        ])
        and any(phrase in q for phrase in [
            "final evidence classes", "evidence classes",
            "evidence categories", "final categories"
        ])
    ):
        return (
            "Final evidence-class distribution from the latest "
            "successful create_final_agent_evidence.py run:\n\n"
            "- No high spatial evidence: 1,237\n"
            "- Terrain evidence: 376\n"
            "- Multiple spatial + temporal evidence: 238\n"
            "- Multiple spatial evidence: 235\n"
            "- InSAR monitoring evidence: 224\n"
            "- InSAR + temporal evidence: 186\n"
            "- Temporal-change evidence: 120\n"
            "- Terrain + temporal evidence: 34\n\n"
            "Total: 2,650 observations. These are rule-based "
            "monitoring categories, not counts of confirmed landslides."
        )

    
    # Specific question: project limitations and deployment improvements
    if (
        any(word in q for word in [
            "limitation", "limitations", "improvements",
            "improve", "deployment", "real-world",
            "real world"
        ])
        and any(word in q for word in [
            "digital twin", "project", "landslide"
        ])
    ):
        return (
            "The Tirumala Hills Landslide Digital Twin is a research "
            "prototype, not a fully operational real-time landslide "
            "prediction or warning system.\n\n"
            "Major limitations:\n"
            "1. U-Net predictions generate a segmentation mask but are "
            "not automatically georeferenced and displayed as a layer "
            "on the Digital Twin map.\n"
            "2. The 15 historical GSI reference locations are approximate "
            "map-derived locations, not exact surveyed coordinates.\n"
            "3. InSAR LOS displacement measurements require quality "
            "assessment and cannot independently confirm a landslide.\n"
            "4. Evidence classes are rule-based monitoring indicators, "
            "not calibrated landslide-risk probabilities.\n"
            "5. The recorded U-Net validation Dice score is 0.6561 and "
            "IoU is 0.5101 at epoch 3; these metrics alone do not "
            "establish real-world prediction reliability.\n"
            "6. Independent field validation and demonstrated future "
            "landslide prediction accuracy have not been established "
            "by the current prototype evidence.\n\n"
            "Improvements needed before deployment:\n"
            "- Georeference and align U-Net masks with the map.\n"
            "- Validate predictions against reliable independent "
            "landslide inventories and field observations.\n"
            "- Evaluate model performance across multiple locations "
            "and time periods.\n"
            "- Improve data-quality checks and document uncertainty.\n"
            "- Establish reliable data updates, monitoring, alert "
            "thresholds, and expert review procedures.\n"
            "- Conduct operational and safety validation before "
            "issuing real-world warnings.\n\n"
            "Until these improvements are validated, the system should "
            "support research and expert review rather than serve as "
            "an independent landslide warning system."
        )

    
    # Specific question: historical GSI reference locations
    if (
        "gsi" in q
        and any(word in q for word in [
            "historical", "locations", "used", "limitations",
            "limitation", "reference"
        ])
    ):
        return (
            "The project contains 15 approximate historical GSI "
            "reference locations. They provide historical spatial "
            "context for examining the Tirumala Hills study area "
            "alongside terrain, InSAR, and other project evidence.\n\n"
            "These locations are approximate map-derived reference "
            "points. They should not be treated as exact surveyed "
            "coordinates or as proof that a landslide is occurring "
            "at that location now.\n\n"
            "The reference locations support contextual analysis, "
            "but their spatial correspondence with model outputs "
            "does not independently establish predictive accuracy. "
            "Independent validation and field evidence are needed."
        )

        # Specific question: rainfall versus spatial evidence count
    
    # Specific question: temporal dataset details
    if (
        "temporal" in q
        and any(word in q for word in [
            "dataset", "observations", "observation",
            "temporal_evidence_flag", "flag", "contain"
        ])
    ):
        
        return (
            "The project contains 2,569 temporal observations. "
            "The temporal evidence-generation script reads "
            "tirumala_temporal_insar_features.csv and calculates "
            "absolute temporal LOS change in millimetres by multiplying "
            "abs_los_change_m by 1000.\n\n"
            "It calculates the 75th percentile of absolute temporal "
            "change as a data-dependent threshold. If a record's "
            "absolute temporal change is greater than or equal to "
            "this threshold, temporal_evidence_flag is set to 1 and "
            "the record is labelled Elevated temporal-change evidence. "
            "Otherwise, the flag is 0 and the record is labelled "
            "Lower temporal-change evidence.\n\n"
            "The threshold is exploratory and relative to this dataset; "
            "it is not a calibrated landslide threshold. A flag of 1 "
            "indicates relatively elevated temporal change, not proof "
            "of a landslide.\n\n"
            "The final evidence script joins spatial and temporal "
            "records using row and col coordinates. Missing temporal "
            "records are marked unavailable and do not independently "
            "trigger a temporal evidence category."
        )

    # Specific question: temporal evidence unavailable
    if (
        "temporal" in q
        and any(word in q for word in [
            "unavailable", "missing", "not available", "no record"
        ])
    ):
        return (
            "When temporal evidence is unavailable, the project marks "
            "the temporal record as unavailable. It does not automatically "
            "treat the missing record as confirmed negative evidence.\n\n"
            "The final evidence class is assigned using the original "
            "spatial category and any positive, available temporal flag. "
            "If no positive available temporal flag exists, the original "
            "spatial category determines the applicable fallback class.\n\n"
            "Missing temporal data means information is unavailable; "
            "it is not proof that temporal change did not occur."
        )
    
    # Specific question: U-Net vs Intelligent Agent integration
    if (
        "u-net" in q or "unet" in q
    ) and (
        "intelligent agent" in q
        or "combined" in q
        or "difference" in q
    ):
        return (
            "The U-Net segmentation model and the Intelligent "
            "Agent are two separate components of the project.\n\n"
            "1. U-Net segmentation model: A 14-channel deep-learning "
            "model that accepts a 128x128x14 HDF5 image and produces "
            "a pixel-level landslide segmentation mask.\n\n"
            "2. Intelligent Agent: A rule-based evidence interpretation "
            "component that analyses terrain, InSAR and temporal "
            "observations and assigns descriptive evidence categories.\n\n"
            "The U-Net segmentation output is not currently integrated "
            "into the Intelligent Agent's final evidence classification "
            "or the Digital Twin's mapped evidence layers. Both are "
            "separate components in the current implementation.\n\n"
            "The U-Net mask is not georeferenced or spatially integrated "
            "with the Digital Twin map."
        )
        # Specific question: U-Net Dice and IoU limitations
    if (
        ("dice" in q or "iou" in q or "intersection over union" in q)
        and ("tirumala" in q or "prove" in q or "accurate" in q
             or "indicate" in q or "model" in q)
    ):
        return (
            "The U-Net model was evaluated using Dice and IoU metrics.\n\n"
            "1. Dice score: Measures the overlap between the predicted "
            "landslide segmentation mask and the ground-truth mask. "
            "A higher score indicates better overlap.\n\n"
            "2. IoU (Intersection over Union): Measures the intersection "
            "of the predicted and ground-truth masks divided by their union. "
            "A higher score indicates better segmentation performance.\n\n"
            "Our reported validation results are Dice = 0.6561 and "
            "IoU = 0.5101, with the best checkpoint at epoch 3.\n\n"
            "These metrics do not prove that the model accurately detects "
            "landslides in Tirumala Hills. They measure performance on "
            "the validation dataset. Independent ground-truth labels and "
            "site-specific validation are required to establish real-world "
            "performance in Tirumala Hills."
        )
    # Specific question: interpret U-Net segmentation results
    if (
        any(word in q for word in ["interpret", "meaning", "understand"])
        and any(word in q for word in ["u-net", "unet", "segmentation"])
    ):
        return (
            "The project uses a 14-channel U-Net for pixel-level "
            "landslide segmentation. It accepts a 128x128x14 HDF5 "
            "input and produces a predicted landslide mask.\n\n"
            "In the recorded example, 1,052 of 16,384 pixels were "
            "predicted as landslide pixels, equivalent to approximately "
            "6.42% of the image pixels.\n\n"
            "The mean model output over those predicted pixels was "
            "approximately 0.91. This is a model output score, not a "
            "calibrated probability of a real-world landslide.\n\n"
            "The saved checkpoint reports a validation Dice score of "
            "0.6561 and an IoU of 0.5101 at epoch 3. These metrics "
            "describe validation segmentation performance; they do not "
            "prove that a new prediction is correct.\n\n"
            "The predicted mask is not automatically georeferenced "
            "onto the Digital Twin map. Interpret it as model-generated "
            "segmentation evidence that requires further verification, "
            "not as confirmation of a landslide."
        )

    
    # Compare the U-Net segmentation agent and integrated agent
    if (
        ("difference" in q or "compare" in q or "distinguish" in q)
        and ("u-net" in q or "unet" in q or "segmentation" in q)
        and ("integrated" in q or "integration" in q)
    ):
        return (
            "The U-Net segmentation agent uses a 14-channel image "
            "with shape 128x128x14 to predict pixel-level landslide "
            "regions and generate a segmentation mask.\n\n"
            "The integrated agent combines the U-Net segmentation "
            "assessment with existing spatial-observation context "
            "to produce a broader recommendation.\n\n"
            "Important limitation: the current integration uses "
            "spatial-observation counts as context. It does not "
            "perform true pixel-level spatial fusion between the "
            "U-Net mask and the Digital Twin map."
        )


    spatial_count = len(dataframe) if not dataframe.empty else 0

    # -------------------------------
    # Dataset / observation questions
    # -------------------------------
    if "how many" in q and "spatial" in q:
        return (
            f"The Digital Twin contains {spatial_count:,} spatial observations."
        )

    if "how many" in q and "temporal" in q:
        return (
            "The project contains 2,569 temporal observations."
        )

    if "gsi" in q and ("how many" in q or "locations" in q):
        return (
            "The project contains 15 approximate historical GSI reference locations."
        )
    
    # -------------------------------
    # Combined InSAR + limitations questions
    # -------------------------------
    if (
        "insar" in q
        and any(word in q for word in [
            "limitation", "limitations", "weakness",
            "weaknesses", "drawback", "drawbacks"
        ])
    ):
        return (
            "**1. Role of Sentinel-1 InSAR**\n\n"
            "Sentinel-1 InSAR is used to monitor surface "
            "deformation and temporal ground changes in "
            "Tirumala Hills.\n\n"
            "**2. Main project limitations**\n\n"
            "- The Digital Twin is a research prototype, "
            "not a fully operational real-time system.\n"
            "- U-Net predictions are not automatically "
            "georeferenced onto the Digital Twin map.\n"
            "- The 15 historical GSI reference locations "
            "are approximate map-derived locations.\n"
            "- Evidence classes are exploratory indicators, "
            "not calibrated landslide-risk probabilities.\n"
            "- Spatial correspondence alone does not prove "
            "predictive accuracy; independent validation "
            "and field evidence are needed."
        )

        # Specific question: Sentinel-1 acquisition pairs and reference points
        # Specific question: Sentinel-1 acquisition pairs and reference points
    if (
        any(term in q for term in [
            "insar",
            "sentinel-1",
            "sentinel 1",
            "los displacement",
            "reference point",
            "reference points"
        ])
        and any(word in q for word in [
            "pair",
            "acquisition",
            "reference point",
            "reference points",
            "subtract",
            "direct comparison",
            "compare",
            "dates"
        ])
    ):
        return (
            "The project uses two Sentinel-1 InSAR pairs:\n\n"
            "1. Pair 1: 5–17 August 2026.\n"
            "2. Pair 2: 17–29 August 2026.\n\n"
            "The two pairs have different reference points, "
            "approximately 89 km apart.\n\n"
            "InSAR LOS displacement is measured relative to a "
            "selected reference point. Therefore, each pair has "
            "a different relative reference level.\n\n"
            "Directly subtracting Pair 1 LOS values from Pair 2 "
            "LOS values does not automatically represent actual "
            "ground movement between the observation periods.\n\n"
            "A consistent reference framework and additional "
            "processing are required before interpreting the "
            "difference as temporal displacement.\n\n"
            "The project has only three unique acquisition dates: "
            "5, 17 and 29 August 2026. This is insufficient for "
            "a robust long-term InSAR time series."
        )
        # Specific question: LOS versus 3D ground movement
    if (
        any(term in q for term in [
            "insar", "sentinel-1", "sentinel 1", "los"
        ])
        and any(term in q for term in [
            "3d", "three-dimensional", "horizontal",
            "vertical", "ground movement", "ground motion"
        ])
    ):
        return (
            "LOS displacement and actual 3D ground movement are different.\n\n"
            "1. LOS displacement: Sentinel-1 InSAR measures ground "
            "movement projected along the satellite's line-of-sight direction.\n\n"
            "2. Vertical movement: A single viewing geometry cannot "
            "independently isolate vertical displacement from horizontal movement.\n\n"
            "3. Horizontal movement: A single viewing geometry cannot "
            "separately determine the east-west and north-south components.\n\n"
            "4. 3D ground movement: Estimating separate movement components "
            "requires additional independent viewing geometries or "
            "measurements, such as suitable ascending and descending "
            "InSAR observations, together with appropriate assumptions.\n\n"
            "The current project reports LOS displacement, not independently "
            "validated three-dimensional ground movement. Therefore, its "
            "LOS values should not be interpreted as complete 3D movement."
        )  
        # Specific question: InSAR correlation quality and reliability
    if (
        "correlation" in q
        and any(word in q for word in [
            "quality", "reliability", "reliable",
            "displacement", "evidence", "classification",
            "class", "low", "affect", "impact"
        ])
    ):
        return (
            "InSAR correlation quality indicates how well the "
            "radar observations correspond between acquisitions. "
            "It helps assess the reliability of the InSAR measurements.\n\n"
            "1. High correlation: Indicates better radar-signal "
            "consistency and generally provides more reliable "
            "InSAR measurement conditions.\n\n"
            "2. Low correlation: Indicates poorer correspondence "
            "between observations. Displacement measurements in "
            "such areas should be interpreted cautiously because "
            "their reliability may be reduced.\n\n"
            "3. Project implementation: The evidence-generation "
            "script sets insar_quality_acceptable to 1 when "
            "correlation >= 0.5 and to 0 otherwise. Low correlation "
            "is recorded as a quality warning in agent_explanation.\n\n"
            "4. Evidence classification: Low correlation does not "
            "automatically change the original spatial evidence "
            "category in the current implementation.\n\n"
            "Therefore, correlation quality is an important "
            "reliability indicator, but the current classification "
            "rules do not automatically exclude low-quality InSAR "
            "evidence. Independent validation is still required."
        )


    # Specific question: interpret InSAR displacement
    if (
        "insar" in q
        and any(word in q for word in [
            "displacement", "values", "confirm", "mean"
        ])
    ):
        return (
            "The project's multi-temporal InSAR analysis reports a mean "
            "absolute line-of-sight (LOS) change of approximately 6.44 mm "
            "and a maximum absolute LOS change of approximately 25.27 mm.\n\n"
            "LOS change describes displacement measured along the "
            "satellite's viewing direction between observation dates. "
            "It does not directly represent full three-dimensional "
            "ground movement.\n\n"
            "These measurements alone cannot confirm a landslide. "
            "They should be interpreted alongside InSAR correlation "
            "quality, terrain evidence, temporal observations, rainfall "
            "context, and independent verification.\n\n"
            "The InSAR measurements are monitoring evidence, not "
            "definitive proof of a landslide."
        )

    
    
    # -------------------------------
    # InSAR questions
    # -------------------------------
    if "insar" in q and (
        "mean" in q or "average" in q
    ) and (
        "maximum" in q or "max" in q
    ):
        return (
            "Multi-temporal InSAR results:\n\n"
            "- Mean absolute LOS change: approximately 6.44 mm\n"
            "- Maximum absolute LOS change: approximately 25.27 mm"
        )

    if "insar" in q and (
        "mean" in q or "average" in q
    ):
        return (
            "The mean absolute LOS change from the "
            "multi-temporal InSAR analysis is approximately 6.44 mm."
        )

    if "insar" in q and (
        "maximum" in q or "max" in q
    ):
        return (
            "The maximum absolute LOS change observed in the "
            "multi-temporal analysis is approximately 25.27 mm."
        )
        # Specific question: low InSAR correlation
    if "correlation" in q and any(word in q for word in [
        "evidence class", "evidence category",
        "change", "affect", "impact"
    ]):
        return (
            "No. In the current evidence-generation rules, low InSAR "
            "correlation does not automatically change the original "
            "spatial evidence category.\n\n"
            "The script sets insar_quality_acceptable to 1 when "
            "correlation >= 0.5 and to 0 otherwise. Low correlation "
            "is recorded as a quality warning in agent_explanation.\n\n"
            "The original category is based on terrain_high_evidence "
            "and insar_high_evidence. Therefore, interpret low-quality "
            "InSAR evidence cautiously. The current script does not "
            "automatically exclude it from the category."
        )
    

    
    # Specific question: high rainfall with low spatial evidence
    if (
        "rainfall" in q
        and any(word in q for word in [
            "high", "heavy", "increased", "increase"
        ])
        and any(word in q for word in [
            "low spatial", "spatial evidence is low",
            "low evidence", "spatial evidence"
        ])
    ):
        return (
            "High rainfall does not automatically increase the "
            "project's spatial evidence count or confirm a landslide.\n\n"
            "The spatial evidence count is calculated from two indicators: "
            "terrain_high_evidence and insar_high_evidence. Each contributes "
            "either 0 or 1, so the count ranges from 0 to 2.\n\n"
            "Rainfall from NASA GPM/IMERG provides contextual information. "
            "If rainfall is high while spatial evidence is low, the agent "
            "should report the rainfall context separately and avoid "
            "claiming that a landslide has been confirmed.\n\n"
            "This is a rule-based monitoring prototype, not a calibrated "
            "landslide probability or an operational warning system."
        )

    
    # -------------------------------
    # Rainfall questions
    # -------------------------------
    if "rainfall" in q:
        if rainfall_dataframe.empty:
            return "The rainfall feature dataset is currently unavailable."

        date_col = get_first_existing_column(
            rainfall_dataframe,
            ["date", "Date", "timestamp"]
        )

        three_col = get_first_existing_column(
            rainfall_dataframe,
            [
                "rainfall_3day_mm",
                "3day_rainfall_mm",
                "reference_3day_rainfall_mm"
            ]
        )

        seven_col = get_first_existing_column(
            rainfall_dataframe,
            [
                "rainfall_7day_mm",
                "7day_rainfall_mm",
                "reference_7day_rainfall_mm"
            ]
        )

        fourteen_col = get_first_existing_column(
            rainfall_dataframe,
            [
                "rainfall_14day_mm",
                "14day_rainfall_mm",
                "reference_14day_rainfall_mm"
            ]
        )

        if (
            "latest" in q
            or "most recent" in q
        ):
            if not date_col:
                return (
                    "I could not find a recognized date column "
                    "in the rainfall dataset."
                )

            rainfall_data = rainfall_dataframe.copy()
            rainfall_data[date_col] = pd.to_datetime(
                rainfall_data[date_col],
                errors="coerce"
            )
            rainfall_data = rainfall_data.dropna(
                subset=[date_col]
            )

            if rainfall_data.empty:
                return "No valid rainfall record dates were found."

            latest = rainfall_data.loc[
                rainfall_data[date_col].idxmax()
            ]

            answer = (
                f"Latest rainfall record date: "
                f"{latest[date_col].strftime('%d %B %Y')}\n\n"
            )

            for label, column in [
                ("3-day rainfall", three_col),
                ("7-day rainfall", seven_col),
                ("14-day rainfall", fourteen_col)
            ]:
                if column:
                    value = pd.to_numeric(
                        pd.Series([latest[column]]),
                        errors="coerce"
                    ).iloc[0]

                    if pd.notna(value):
                        answer += f"- {label}: {value:.1f} mm\n"
                    else:
                        answer += f"- {label}: unavailable\n"
                else:
                    answer += f"- {label}: column not found\n"

            return answer

        if (
            "29 august 2026" in q
            or "2026-08-29" in q
        ) and any(word in q for word in [
            "3-day", "3 day", "7-day", "7 day",
            "14-day", "14 day"
        ]):
            if not date_col:
                return (
                    "I could not find a recognized date column "
                    "in the rainfall dataset."
                )

            rainfall_data = rainfall_dataframe.copy()
            rainfall_data[date_col] = pd.to_datetime(
                rainfall_data[date_col],
                errors="coerce"
            )
            rainfall_data = rainfall_data.loc[
                rainfall_data[date_col].dt.normalize()
                == pd.Timestamp("2026-08-29")
            ]
            if rainfall_data.empty:
                return (
                    "No rainfall record is available for "
                    "29 August 2026."
                )

            target_record = rainfall_data.iloc[-1]
            answer = "Rainfall accumulations ending 29 August 2026:\n\n"
            for label, column in [
                ("3-day rainfall", three_col),
                ("7-day rainfall", seven_col),
                ("14-day rainfall", fourteen_col),
            ]:
                if column:
                    value = pd.to_numeric(
                        pd.Series([target_record[column]]),
                        errors="coerce"
                    ).iloc[0]
                    answer += (
                        f"- {label}: {value:.1f} mm\n"
                        if pd.notna(value)
                        else f"- {label}: unavailable\n"
                    )
                else:
                    answer += f"- {label}: column not found\n"
            return answer

        return (
            "The project uses NASA GPM/IMERG rainfall data. "
            "You can ask for the latest rainfall record or "
            "rainfall values before 29 August 2026."
        )


        # Specific question: final evidence classification and probability
    if (
        any(term in q for term in ["terrain", "spatial"])
        and "insar" in q
        and "temporal" in q
        and any(term in q for term in [
            "final evidence class",
            "evidence class",
            "classification",
            "combine",
            "combined"
        ])
    ):
        return (
            "The project combines terrain, InSAR and temporal "
            "evidence using rule-based classification.\n\n"

            "1. Terrain evidence: Derived from terrain-related "
            "features, including DEM and slope indicators.\n\n"

            "2. InSAR evidence: Uses Sentinel-1 deformation-related "
            "features and the insar_high_evidence indicator.\n\n"

            "3. Spatial evidence: The original spatial category "
            "is determined using terrain_high_evidence and "
            "insar_high_evidence.\n\n"

            "4. Temporal evidence: The temporal dataset is matched "
            "to spatial observations using row and col coordinates. "
            "A temporal_evidence_flag of 1 indicates elevated "
            "temporal-change evidence according to the exploratory "
            "75th-percentile threshold.\n\n"

            "5. Final evidence class: The classification script "
            "combines the original spatial category with the "
            "availability and value of temporal_evidence_flag. "
            "Examples include Multiple spatial + temporal evidence, "
            "InSAR + temporal evidence, and Terrain + temporal evidence.\n\n"

            "Does this represent landslide probability? No. These "
            "are rule-based monitoring evidence categories, not "
            "calibrated landslide probabilities. They do not prove "
            "that a landslide has occurred or will occur."
        )
    # -------------------------------
    # Terrain questions
    # -------------------------------
    if "terrain" in q or "slope" in q or "elevation" in q:
        return (
            "Terrain and slope assessment in the Tirumala Hills project:\n\n"
            "1. DEM/elevation data provides the terrain-height information.\n\n"
            "2. Slope is calculated from the elevation data to describe "
            "how steep the terrain is.\n\n"
            "3. Terrain evidence is combined with other available "
            "evidence, including Sentinel-1 InSAR deformation, temporal "
            "change, rainfall context and historical GSI locations.\n\n"
            "4. The Intelligent Agent uses evidence categories to suggest "
            "monitoring or further review.\n\n"
            "Limitation: terrain and slope are supporting indicators. "
            "They do not independently confirm that a landslide will occur."
        )
    
    # -------------------------------
    # U-Net and Digital Twin integration
    # -------------------------------
    if (
        ("digital twin" in q or "map" in q)
        and any(word in q for word in [
            "automatically", "update", "integrate",
            "integration", "georeferenced", "georeference"
        ])
        and any(word in q for word in [
            "u-net", "unet", "prediction",
            "segmentation", "mask"
        ])
    ):
        return (
            "No. The current U-Net prediction does not "
            "automatically update the Digital Twin map. "
            "The model generates a segmentation mask from "
            "the uploaded 14-channel HDF5 image, but the "
            "prediction is not automatically georeferenced "
            "or added as a map layer. To implement this, "
            "we would need geographic metadata, spatial "
            "alignment, and a map-layer update workflow."
        )

    # -------------------------------
    # U-Net questions
    # -------------------------------
    if "u-net" in q or "unet" in q or "segmentation" in q:
        return (
            "The project uses a 14-channel U-Net model for pixel-level "
            "landslide segmentation. The model accepts a 128×128×14 "
            "HDF5 input and produces a landslide segmentation mask."
        )

    # -------------------------------
    # Digital Twin questions
    # -------------------------------
    if "digital twin" in q:
        return (
            "The Digital Twin keeps the existing 2D Leaflet map and offers an "
            "optional experimental 3D view of the local elevation surface. "
            "The 3D terrain can be colored by slope or selected Pair 2 InSAR "
            "layers. These are visualization layers, not a validated landslide "
            "prediction or full 3D ground-motion measurement."
        )
    
    
    # -------------------------------
    # How final evidence classes are assigned
    # -------------------------------
    if (
        "evidence class" in q
        or "evidence classes" in q
        or "evidence category" in q
        or "evidence categories" in q
    ) and any(word in q for word in [
        "assign", "assigned", "calculate",
        "calculated", "combine", "combined",
        "generated", "each spatial observation",
        "classification", "classify", "logic",
        "rule", "rules", "how", "explain"
    ]):
        return (
            "How the final evidence classes are assigned:\n\n"
            "Step 1 — Original spatial evidence:\n"
            "The create_agent_evidence.py script creates two binary "
            "indicators:\n"
            "- Terrain high evidence = 1 when terrain_class is High; "
            "otherwise 0.\n"
            "- InSAR high evidence = 1 when insar_monitoring_class "
            "is High; otherwise 0.\n\n"
            "The spatial evidence count is the sum of these two "
            "indicators, so it can be 0, 1, or 2. The original "
            "spatial category is assigned as follows:\n"
            "- Terrain + InSAR evidence: both indicators are 1.\n"
            "- Terrain evidence: only terrain is 1.\n"
            "- InSAR monitoring evidence: only InSAR is 1.\n"
            "- No high spatial evidence: both indicators are 0.\n\n"
            "Step 2 — Add temporal evidence:\n"
            "The create_final_agent_evidence.py script merges the "
            "spatial and temporal datasets using matching row and "
            "col coordinates. It checks whether temporal evidence "
            "is available and whether temporal_evidence_flag equals 1.\n\n"
            "The final categories are assigned using these rules:\n"
            "- Terrain + InSAR evidence with a positive temporal "
            "flag becomes Multiple spatial + temporal evidence.\n"
            "- Terrain + InSAR evidence without a positive available "
            "temporal flag remains Multiple spatial evidence.\n"
            "- InSAR monitoring evidence with a positive temporal "
            "flag becomes InSAR + temporal evidence; otherwise it "
            "remains InSAR monitoring evidence.\n"
            "- Terrain evidence with a positive temporal flag becomes "
            "Terrain + temporal evidence; otherwise it remains "
            "Terrain evidence.\n"
            "- Any other original spatial category with a positive "
            "available temporal flag becomes Temporal-change evidence.\n"
            "- Otherwise, it becomes No high spatial evidence.\n\n"
            "Step 3 — Measurement quality:\n"
            "The original spatial script marks InSAR correlation "
            "of at least 0.5 as acceptable. It records low correlation "
            "as a quality warning in the explanation. This quality "
            "flag does not itself change the original evidence category.\n\n"
            "Important limitations:\n"
            "- These are rule-based evidence categories, not calibrated "
            "landslide probabilities.\n"
            "- Rainfall is retained as contextual information and is "
            "not included in the original spatial evidence count.\n"
            "- Missing temporal records are marked unavailable. They "
            "are not automatically treated as confirmed negative "
            "temporal evidence.\n"
            "- The categories support monitoring and expert review; "
            "they do not independently confirm a landslide."
        )


    # -------------------------------
    # Evidence classes and agent decisions
    # -------------------------------
    if (
        "evidence class" in q
        or "evidence classes" in q
        or (
            "monitoring action" in q
            and "decide" in q
        )
    ):
        return (
            "The Intelligent Agent uses rule-based evidence "
            "integration to assign monitoring recommendations "
            "based on the available evidence class.\n\n"

            "**1. Multiple spatial + temporal**\n"
            "Action: Enhanced monitoring. Multiple spatial and "
            "temporal indicators are present.\n\n"

            "**2. Multiple spatial**\n"
            "Action: Enhanced monitoring. Multiple spatial "
            "indicators are present.\n\n"

            "**3. InSAR + temporal**\n"
            "Action: Enhanced monitoring. InSAR and temporal-change "
            "evidence are both present.\n\n"

            "**4. InSAR monitoring**\n"
            "Action: InSAR monitoring. Continue deformation "
            "monitoring and independent validation.\n\n"

            "**5. Terrain + temporal**\n"
            "Action: Terrain and temporal review. Compare slope "
            "conditions with deformation observations.\n\n"

            "**6. Terrain**\n"
            "Action: Terrain review. Examine slope characteristics "
            "alongside other remote-sensing evidence.\n\n"

            "**7. Temporal-change**\n"
            "Action: Temporal-change review. Compare observed "
            "changes with independent InSAR and field evidence.\n\n"

            "**8. No high spatial evidence**\n"
            "Action: Continue monitoring. The absence of high "
            "spatial evidence does not establish that an area is safe.\n\n"

            "**Limitation:** These are explainable, rule-based "
            "monitoring recommendations, not calibrated landslide-risk "
            "probabilities."
        )
        # Specific question: Susceptibility vs hazard vs evidence map
    if (
        "susceptibility" in q
        and "hazard" in q
        and ("evidence map" in q or "intelligent agent" in q)
    ):
        return (
            "These three maps represent different concepts.\n\n"
            "1. Landslide susceptibility map: Shows the relative "
            "spatial likelihood of landslide occurrence based on "
            "conditioning factors such as slope and terrain. It "
            "describes where landslides may occur, not when.\n\n"
            "2. Landslide hazard map: Represents the likelihood "
            "of landslides occurring in a particular area within "
            "a specified time period and may also consider magnitude "
            "or intensity.\n\n"
            "3. Current Intelligent Agent Evidence map: Displays "
            "evidence categories derived from available terrain, "
            "InSAR and temporal observations. It supports evidence "
            "interpretation and monitoring.\n\n"
            "Our current Intelligent Agent Evidence map is not a "
            "calibrated landslide susceptibility map or a "
            "time-dependent landslide hazard map. It displays "
            "monitoring evidence, not a scientifically validated "
            "probability of future landslide occurrence."
        )
    # -------------------------------
    # Agent questions
    # -------------------------------
    if "agent" in q or "recommendation" in q:
        return (
            "The Intelligent Agent uses explainable rule-based evidence "
            "integration to interpret the available landslide evidence "
            "and provide monitoring recommendations."
        )
    
    # -------------------------------
    # Project limitations
    # -------------------------------
    if any(word in q for word in [
        "limitation", "limitations", "weakness",
        "weaknesses", "drawback", "drawbacks",
        "challenge", "challenges"
    ]):
        return (
            "The main limitations of this project are:\n\n"
            "1. The Digital Twin is a research prototype, "
            "not a fully operational real-time monitoring system.\n\n"
            "2. U-Net predictions are not automatically "
            "georeferenced or added to the Digital Twin map.\n\n"
            "3. The 15 historical GSI reference locations "
            "are approximate map-derived locations.\n\n"
            "4. Evidence classes are exploratory indicators, "
            "not calibrated landslide-risk probabilities.\n\n"
            "5. Spatial correspondence with historical locations "
            "does not, by itself, establish predictive accuracy. "
            "Independent validation and field evidence are needed."
        )


    # -------------------------------
    # Project questions
    # -------------------------------
    if "project" in q or "objective" in q or "purpose" in q:
        return (
            "The project aims to develop a remote-sensing-enabled framework "
            "for landslide monitoring and risk assessment in Tirumala Hills "
            "using InSAR, terrain, rainfall, historical GSI evidence, "
            "U-Net segmentation and an Intelligent Agent."
        )

    # -------------------------------
    # Dataset questions
    # -------------------------------
    if "dataset" in q or "data" in q:
        return (
            "The project uses Sentinel-1 SAR/InSAR, DEM/elevation, "
            "GSI historical landslide evidence, NASA GPM/IMERG rainfall "
            "and Landslide4Sense data for U-Net segmentation."
        )

    # -------------------------------
    
    # Specific question: spatial observations
    if (
        "spatial" in q
        and any(word in q for word in [
            "observation", "observations", "2650", "2,650"
        ])
    ):
        return (
            "The project contains 2,650 spatial observations in its "
            "final agent evidence dataset. Each observation represents "
            "a spatial record used in the study area's evidence assessment.\n\n"
            "The evidence-generation workflow derives terrain and InSAR "
            "indicators for these records. Terrain high evidence is based "
            "on terrain_class == 'High', and InSAR high evidence is based "
            "on insar_monitoring_class == 'High'. Their binary indicators "
            "are added to produce a spatial evidence count from 0 to 2.\n\n"
            "The spatial category describes which of these indicators "
            "are present. The final workflow can combine the original "
            "spatial category with available temporal evidence by matching "
            "records using row and col coordinates.\n\n"
            "The 2,650 observations are spatial records, not 2,650 "
            "separate landslides. The resulting evidence classes are "
            "rule-based monitoring indicators, not calibrated landslide "
            "probabilities."
        )

    # -------------------------------
    # Default response
    # -------------------------------
    return (
        "I could not find a direct answer to that question "
        "in the currently available project evidence. "
        "Please try asking about project limitations, "
        "InSAR, terrain, rainfall, GSI locations, U-Net "
        "segmentation, Digital Twin integration, or "
        "spatial and temporal observations."
    )

# ============================================================
# HDF5 READER
# ============================================================
def read_h5_image(
    uploaded_file
):

    uploaded_file.seek(
        0
    )

    with h5py.File(
        uploaded_file,
        "r"
    ) as h5_file:

        if "img" not in h5_file:

            raise ValueError(
                "Invalid HDF5 file: required "
                "'img' dataset was not found."
            )

        if not isinstance(h5_file["img"], h5py.Dataset):
            raise ValueError(
                "Invalid HDF5 file: 'img' must be a dataset, not a group."
            )

        image = np.asarray(
            h5_file["img"][:],
            dtype=np.float32
        )

    if image.shape != EXPECTED_SHAPE:

        raise ValueError(
            f"Invalid image shape: {image.shape}. "
            f"The trained U-Net expects exactly "
            f"{EXPECTED_SHAPE}."
        )

    if not np.isfinite(
        image
    ).all():

        raise ValueError(
            "The uploaded image contains "
            "NaN or infinite values."
        )

    return image


# ============================================================
# U-NET PREDICTION
# ============================================================
def run_unet_prediction(
    image
):

    image_tensor = (
        torch.from_numpy(image)
        .permute(
            2,
            0,
            1
        )
        .unsqueeze(
            0
        )
        .to(
            segmentation_device
        )
    )

    with torch.no_grad():

        logits = segmentation_model(
            image_tensor
        )

        probability = (
            torch.sigmoid(
                logits
            )[0, 0]
            .cpu()
            .numpy()
        )

    prediction_mask = (
        probability
        >= PREDICTION_THRESHOLD
    ).astype(
        np.uint8
    )

    predicted_pixels = int(
        prediction_mask.sum()
    )

    total_pixels = int(
        prediction_mask.size
    )

    area_percent = (
        predicted_pixels
        / total_pixels
        * 100.0
    )

    if predicted_pixels > 0:

        confidence = float(
            probability[
                prediction_mask == 1
            ].mean()
        )

    else:

        confidence = 0.0

    return (
        probability,
        prediction_mask,
        predicted_pixels,
        area_percent,
        confidence
    )
def create_risk_classification_map(probability_map):
    import numpy as np

    risk_map = np.zeros(
        (*probability_map.shape, 3),
        dtype=np.uint8
    )

    low = (probability_map >= 0.50) & (probability_map < 0.65)
    medium = (probability_map >= 0.65) & (probability_map < 0.80)
    high = probability_map >= 0.80

    risk_map[low] = [34, 197, 94]       # Green
    risk_map[medium] = [250, 204, 21]   # Yellow
    risk_map[high] = [239, 68, 68]     # Red

    return risk_map

# ============================================================
# RGB PREVIEW
# ============================================================
def make_rgb_preview(
    image
):

    rgb = image[
        :,
        :,
        [3, 2, 1]
    ].copy()

    rgb_min = rgb.min(
        axis=(0, 1),
        keepdims=True
    )

    rgb_max = rgb.max(
        axis=(0, 1),
        keepdims=True
    )

    rgb = (
        (rgb - rgb_min)
        /
        (
            rgb_max
            - rgb_min
            + 1e-8
        )
    )

    return np.clip(
        rgb,
        0,
        1
    )


# ============================================================
# SAVE SEGMENTATION REPORT
# ============================================================
def save_segmentation_report(
    source_file,
    predicted_pixels,
    area_percent,
    confidence,
    action,
    recommendation
):

    report_directory = SEGMENTATION_AGENT_FILE.parent
    report_directory.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    report_path = report_directory / (
        f"{SEGMENTATION_REPORT_PREFIX}{timestamp}.csv"
    )
    suffix = 1
    while report_path.exists():
        report_path = report_directory / (
            f"{SEGMENTATION_REPORT_PREFIX}{timestamp}_{suffix}.csv"
        )
        suffix += 1

    report = pd.DataFrame(
        [
            {
                "timestamp":
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),

                "source_file":
                    source_file,

                "predicted_landslide_pixels":
                    int(predicted_pixels),

                "predicted_landslide_percentage":
                    float(area_percent),

                "average_confidence":
                    float(confidence),

                "prediction_threshold":
                    PREDICTION_THRESHOLD,

                "agent_action":
                    action,

                "agent_recommendation":
                    recommendation,
            }
        ]
    )

    report.to_csv(
        report_path,
        index=False
    )

    return report_path


# ============================================================
# TITLE
# ============================================================
st.title(
    "🌍 Tirumala Hills Landslide Monitoring"
)

st.subheader(
    "Remote Sensing-Enabled Digital Twin and Intelligent Agent"
)

st.write(
    "**Study Area:** Tirumala Hills, "
    "Tirupati, Andhra Pradesh"
)

st.write(
    "This research prototype integrates terrain evidence, "
    "Sentinel-1 InSAR monitoring, exploratory InSAR pair differences, "
    "rainfall context, historical GSI evidence, and an "
    "explainable intelligent-agent evidence framework."
)


# ============================================================
# SIDEBAR
# ============================================================

# ============================================================
# SYSTEM INFORMATION
# ============================================================

st.sidebar.header("System Information")

# Load temporal data BEFORE using it.
temporal_features = load_temporal_feature_data()

spatial_count = len(df) if not df.empty else 0

temporal_count = (
    len(temporal_features)
    if not temporal_features.empty
    else 0
)


st.sidebar.metric(
    "Spatial observations",
    f"{spatial_count:,}"
)

st.sidebar.metric(
    "Pair-difference records",
    f"{temporal_count:,}" if not temporal_features.empty else "N/A"
)

# Count spatial records with matched temporal evidence.
if (
    not df.empty
    and "temporal_available" in df.columns
):
    temporal_flags = (
        df["temporal_available"]
        .fillna(False)
        .astype(bool)
    )

    matched_count = int(temporal_flags.sum())
    unmatched_count = spatial_count - matched_count

    matched_percentage = (
        matched_count / spatial_count * 100
        if spatial_count > 0 else 0
    )

    unmatched_percentage = (
        unmatched_count / spatial_count * 100
        if spatial_count > 0 else 0
    )

    st.sidebar.metric(
        "Matched temporal observations",
        f"{matched_count:,}",
        help="Spatial records with matching temporal InSAR evidence."
    )

    st.sidebar.caption(
        f"{matched_percentage:.2f}% of spatial observations"
    )

    st.sidebar.metric(
        "Unmatched temporal observations",
        f"{unmatched_count:,}",
        help="Spatial records without matching temporal InSAR evidence."
    )

    st.sidebar.caption(
        f"{unmatched_percentage:.2f}% of spatial observations"
    )
else:
    st.sidebar.info(
        "Temporal matching information is unavailable."
    )

st.sidebar.caption(
    "Spatial observations are records in the final agent evidence "
    "dataset. Temporal feature records belong to a separate dataset. "
    "Matched and unmatched counts describe spatial records, not "
    "confirmed landslides."
)
# ============================================================

# ============================================================
# SATELLITE DATA INPUT
# ============================================================
st.header(
    "📡 Satellite Data Input"
)

st.write(
    "Upload a Landslide4Sense-compatible "
    "14-channel HDF5 (.h5) satellite image "
    "for U-Net landslide segmentation."
)

uploaded_files = st.file_uploader(
    "Upload multiple 14-channel satellite images",
    type=["h5", "hdf5"],
    accept_multiple_files=True,
    help=(
        "Upload 1 to 10 HDF5 files (.h5 or .hdf5). Each file must "
        "contain an 'img' dataset with shape (128, 128, 14)."
    ),
)

if len(uploaded_files) > 10:
    st.error("Please upload a maximum of 10 HDF5 images.")
    uploaded_files = []

st.info(
    "The current trained U-Net accepts only a "
    "14-channel HDF5 input with shape "
    "(128, 128, 14). A normal GeoTIFF or "
    "Sentinel-1 ZIP cannot be passed directly "
    "to this model without a separate "
    "preprocessing/conversion pipeline."
)


# Holds only the prediction generated during this Streamlit run.
# Historical CSV reports are displayed separately and are not treated as current input.

# ============================================================
# MULTI-IMAGE UPLOADED IMAGE PREDICTION
# ============================================================

uploaded_image_assessments = []

if uploaded_files:

    if not model_loaded:
        st.error(
            "Prediction cannot start because the "
            "U-Net checkpoint failed to load."
        )

    else:
        research_observation_count = len(df)

        for image_index, uploaded_file in enumerate(uploaded_files):

            st.divider()

            st.subheader(
                f"Image {image_index + 1}: {uploaded_file.name}"
            )

            try:
                # ------------------------------------------------
                # READ HDF5 IMAGE AND RUN EXISTING U-NET
                # ------------------------------------------------
                image = read_h5_image(uploaded_file)
                (
                    probability,
                    prediction_mask,
                    predicted_pixels,
                    landslide_percentage,
                    average_confidence
                ) = run_unet_prediction(image)


                # Generate LOW / MEDIUM / HIGH risk map
                risk_class_map = create_risk_classification_map(
                    probability
                )

                st.subheader("Landslide Risk Classification Map")

                st.image(
                    risk_class_map,
                    caption=(
                        "Green: LOW | Yellow: MEDIUM | "
                        "Red: HIGH | Black: No detected landslide"
                    ),
                    width="stretch"
                )

                st.write("### U-Net Agent Decision")
                # ------------------------------------------------
                # U-NET AGENT DECISION
                # ------------------------------------------------
                (
                    agent_action,
                    agent_recommendation
                ) = segmentation_agent_decision(
                    landslide_percentage,
                    average_confidence,
                    predicted_pixels
                )

                # ------------------------------------------------
                # INTEGRATED AGENT DECISION
                # ------------------------------------------------
                (
                    integrated_action,
                    integrated_recommendation
                ) = integrated_agent_decision(
                    predicted_pixels,
                    landslide_percentage,
                    average_confidence,
                    research_observation_count
                )

                # ------------------------------------------------
                # IMAGE-SPECIFIC SCREENING BAND
                # ------------------------------------------------
                image_band, image_band_basis = (
                    classify_uploaded_image_coverage(
                        landslide_percentage
                    )
                )

                current_assessment = {
                    "filename": uploaded_file.name,
                    "predicted_pixels": int(predicted_pixels),
                    "coverage_percent": float(landslide_percentage),
                    "mean_positive_score": float(average_confidence),
                    "screening_band": image_band,
                    "agent_action": agent_action,
                }

                uploaded_image_assessments.append(
                    current_assessment
                )

                # ------------------------------------------------
                # SAVE A SEPARATE REPORT FOR EACH IMAGE
                # ------------------------------------------------
                upload_signature = hashlib.sha256(
                    uploaded_file.name.encode("utf-8")
                    + uploaded_file.getvalue()
                ).hexdigest()

                saved_upload_signatures = (
                    st.session_state.setdefault(
                        "saved_upload_signatures", {}
                    )
                )

                if upload_signature not in saved_upload_signatures:

                    saved_report_path = save_segmentation_report(
                        source_file=uploaded_file.name,
                        predicted_pixels=predicted_pixels,
                        area_percent=landslide_percentage,
                        confidence=average_confidence,
                        action=agent_action,
                        recommendation=agent_recommendation
                    )

                    saved_upload_signatures[upload_signature] = (
                        str(saved_report_path)
                    )

                else:
                    saved_report_path = Path(
                        saved_upload_signatures[upload_signature]
                    )

                    if not saved_report_path.exists():
                        saved_report_path = save_segmentation_report(
                            source_file=uploaded_file.name,
                            predicted_pixels=predicted_pixels,
                            area_percent=landslide_percentage,
                            confidence=average_confidence,
                            action=agent_action,
                            recommendation=agent_recommendation
                        )

                        saved_upload_signatures[upload_signature] = (
                            str(saved_report_path)
                        )

                # ------------------------------------------------
                # IMAGE ASSESSMENT METRICS
                # ------------------------------------------------
                st.success(
                    "U-Net landslide segmentation completed."
                )

                col1, col2, col3, col4 = st.columns(4)

                col1.metric(
                    "Predicted Landslide Pixels",
                    f"{predicted_pixels:,}"
                )

                col2.metric(
                    "Predicted Area",
                    f"{landslide_percentage:.2f}%"
                )

                col3.metric(
                    "Mean Positive Model Score",
                    f"{average_confidence * 100:.2f}%"
                )

                col4.metric(
                    "Agent Action",
                    agent_action
                )

                # ------------------------------------------------
                # PREDICTED LANDSLIDE MASK
                # ------------------------------------------------
                st.markdown("#### Predicted Landslide Mask")

                st.image(
                    prediction_mask * 255,
                    caption=(
                        "White = pixels predicted as landslide "
                        f"(threshold = {PREDICTION_THRESHOLD:.2f})"
                    ),
                    clamp=True,
                    use_container_width=True
                )

                # ------------------------------------------------
                # LANDSLIDE DETECTION OVERLAY
                # ------------------------------------------------
                st.markdown("#### Landslide Detection Overlay")

                rgb_image = make_rgb_preview(image)
                overlay = rgb_image.copy()

                overlay[prediction_mask == 1] = [
                    1.0, 0.0, 0.0
                ]

                st.image(
                    overlay,
                    caption="Red = predicted landslide regions",
                    clamp=True,
                    use_container_width=True
                )
            except Exception as exc:
                st.error(
                    f"Could not process {uploaded_file.name}: {exc}"
                )




# ============================================================
# LANDSLIDE RISK ASSESSMENT (DATA-DRIVEN RELATIVE EVIDENCE INDEX)
# ============================================================
from src.risk_assessment import build_spatial_risk

risk_df, risk_summary = build_spatial_risk(df)

if risk_summary["score"] is None:
    st.warning(
        "Risk assessment is unavailable: the spatial evidence table does not "
        "contain usable slope, terrain, InSAR, or temporal indicator columns. "
        "No default score is substituted."
    )
else:
    st.subheader("Spatial Risk Assessment")
    st.markdown("### Risk Category Distribution")

    category_order = ["Low", "Medium", "High"]
    category_counts = (
        risk_df["risk_category"]
        .value_counts()
        .reindex(category_order, fill_value=0)
    )
    total_observations = int(category_counts.sum())
    count_cols = st.columns(3)

    count_cols[0].metric(
        "🟢 LOW Risk", f"{int(category_counts['Low']):,}",
        f"{category_counts['Low'] / total_observations * 100:.1f}%" if total_observations else "0%"
    )
    count_cols[1].metric(
        "🟡 MEDIUM Risk", f"{int(category_counts['Medium']):,}",
        f"{category_counts['Medium'] / total_observations * 100:.1f}%" if total_observations else "0%"
    )
    count_cols[2].metric(
        "🔴 HIGH Risk", f"{int(category_counts['High']):,}",
        f"{category_counts['High'] / total_observations * 100:.1f}%" if total_observations else "0%"
    )

    st.markdown("#### Observation Distribution")
    chart_df = pd.DataFrame({
        "Risk Category": category_order,
        "Observations": [int(category_counts[label]) for label in category_order]
    }).set_index("Risk Category")
    st.bar_chart(chart_df, use_container_width=True)
    coordinate_columns = {"latitude", "longitude"}
    if coordinate_columns.issubset(risk_df.columns):
        map_data = risk_df.copy()
        map_data["latitude"] = pd.to_numeric(map_data["latitude"], errors="coerce")
        map_data["longitude"] = pd.to_numeric(map_data["longitude"], errors="coerce")
        map_data = map_data.dropna(subset=["latitude", "longitude", "risk_score"])
        if not map_data.empty:
            try:
                import pydeck as pdk
                color_lookup = {
                    "Low": [34, 197, 94, 190],
                    "Medium": [234, 179, 8, 210],
                    "High": [239, 68, 68, 220],
                }
                map_data["marker_color"] = map_data["risk_category"].map(color_lookup)
                layer = pdk.Layer(
                    "ScatterplotLayer", data=map_data,
                    get_position="[longitude, latitude]",
                    get_fill_color="marker_color", get_radius=45,
                    pickable=True, auto_highlight=True,
                )
                view = pdk.ViewState(
                    latitude=float(map_data["latitude"].mean()),
                    longitude=float(map_data["longitude"].mean()),
                    zoom=11, pitch=0,
                )
                st.pydeck_chart(pdk.Deck(
                    layers=[layer], initial_view_state=view,
                    tooltip={"text": "Risk: {risk_category}\\nScore: {risk_score}\\nEvidence coverage: {risk_evidence_coverage}%"},
                ), use_container_width=True)
                st.caption("Map points are coloured by relative evidence category, not validated hazard zones.")
            except Exception as map_error:
                st.info(f"Spatial map could not be rendered; showing the location table instead. ({map_error})")
        else:
            st.info("Latitude/longitude columns exist, but no valid coordinate rows are available.")
    # Coordinate warning, detailed spatial-risk table, and methodology footer
    # are intentionally omitted from the dashboard display.


# ============================================================
# DIGITAL TWIN
# ============================================================
st.header(
    "🗺️ Digital Twin"
)

st.write(
    "Integrated spatial evidence, exploratory "
    "InSAR pair-difference evidence, historical GSI locations, "
    "and rainfall context."
)

if DIGITAL_TWIN_FILE.exists():

    try:

        html_content = (
            DIGITAL_TWIN_FILE
            .read_text(
                encoding="utf-8"
            )
        )

        components.html(
            html_content,
            height=650,
            scrolling=True
        )

    except Exception as map_error:

        st.error(
            f"Could not display the "
            f"Digital Twin: {map_error}"
        )

else:

    st.warning(
        "Tirumala Digital Twin HTML file "
        "was not found."
    )

    st.code(
        str(DIGITAL_TWIN_FILE),
        language="text"
    )

show_3d_terrain = st.checkbox(
    "Show experimental 3D terrain view",
    help=(
        "Displays the local 80 m terrain DEM with an optional aligned "
        "evidence overlay. The existing 2D map remains available above."
    ),
)

if show_3d_terrain:
    st.caption(
        "Experimental 3D view using the local GSI-AOI DEM (EPSG:32644). "
        "Height exaggeration is visual only; LOS values and pair differences "
        "are not validated landslide movement."
    )
    overlay_column, exaggeration_column = st.columns(2)
    with overlay_column:
        selected_terrain_overlay = st.selectbox(
            "Color terrain by",
            TERRAIN_OVERLAYS,
        )
    with exaggeration_column:
        terrain_vertical_exaggeration = st.slider(
            "Vertical exaggeration",
            min_value=1.0,
            max_value=10.0,
            value=3.0,
            step=0.5,
        )

    try:
        terrain_figure = create_terrain_figure(
            BASE_DIR,
            selected_terrain_overlay,
            terrain_vertical_exaggeration,
        )
        st.plotly_chart(
            terrain_figure,
            width="stretch",
            config={"displaylogo": False, "responsive": True},
        )
    except TerrainViewError as terrain_error:
        st.error(f"Could not display the experimental 3D terrain: {terrain_error}")


# Intelligent Agent evidence table removed from dashboard display.

# ============================================================
# INTELLIGENT AGENT - QUESTION ANSWERING INTERFACE
# ============================================================

st.header("💬 Ask the Intelligent Agent")

st.write(
    "Ask questions about the Tirumala Hills Digital Twin, "
    "remote-sensing evidence, U-Net results, rainfall, InSAR "
    "and project observations."
)

question = st.text_input(
    "Enter your question:",
    placeholder="Example: How many spatial observations are available?"
)

if st.button("Ask Agent"):
    if question.strip():

        answer = answer_project_question(
            question,
            df,
            rainfall_df,
            gsi_df,
            temporal_features,
        )

        st.success("🤖 Agent Answer")
        st.write(answer)

    else:
        st.warning("Please enter a question.")

# ============================================================
# U-NET MODEL INFORMATION
# ============================================================
st.header(
    "🧠 U-Net Model Information"
)

if model_loaded:

    st.success(
        "Checkpoint loaded successfully"
    )

    m1, m2, m3 = st.columns(
        3
    )

    with m1:

        st.metric(
            "Checkpoint Epoch",
            model_epoch
        )

    with m2:

        if validation_dice is not None:

            st.metric(
                "Validation Dice",
                f"{safe_float(validation_dice):.4f}"
            )

        else:

            st.metric(
                "Validation Dice",
                "N/A"
            )

    with m3:

        if validation_iou is not None:

            st.metric(
                "Validation IoU",
                f"{safe_float(validation_iou):.4f}"
            )

        else:

            st.metric(
                "Validation IoU",
                "N/A"
            )

else:

    st.error(
        "The U-Net checkpoint could not be loaded."
    )

    st.code(
        model_error,
        language="text"
    )


# ============================================================
# U-NET PREDICTION HISTORY AND LATEST REPORT
# ============================================================
st.header(
    "🧩 U-Net Prediction History & Latest Report"
)
st.caption(
    "Saved upload results are shown here as history. This section may contain "
    "previous uploads even when no file is currently selected above."
)

segmentation_report_files = list(
    SEGMENTATION_AGENT_FILE.parent.glob(
        f"{SEGMENTATION_REPORT_PREFIX}*.csv"
    )
)
if SEGMENTATION_AGENT_FILE.exists():
    segmentation_report_files.append(SEGMENTATION_AGENT_FILE)

# Build a comparison table from all individually saved prediction reports.
if segmentation_report_files:
    history_frames = []
    for report_file in segmentation_report_files:
        try:
            report_part = pd.read_csv(report_file)
            if not report_part.empty:
                history_frames.append(report_part)
        except (OSError, ValueError, pd.errors.ParserError):
            continue

    if history_frames:
        history_df = pd.concat(history_frames, ignore_index=True)
        if "timestamp" in history_df.columns:
            history_df["timestamp"] = pd.to_datetime(
                history_df["timestamp"], errors="coerce"
            )
            history_df = history_df.sort_values(
                "timestamp", ascending=False, na_position="last"
            )

        if "predicted_landslide_percentage" in history_df.columns:
            history_df["screening_level"] = history_df[
                "predicted_landslide_percentage"
            ].apply(
                lambda value: classify_uploaded_image_coverage(
                    safe_float(value)
                )[0]
            )

        history_columns = {
            "timestamp": "Assessment time",
            "source_file": "Uploaded image",
            "predicted_landslide_pixels": "Predicted pixels",
            "predicted_landslide_percentage": "Segmented coverage (%)",
            "average_confidence": "Mean predicted-positive score",
            "screening_level": "Coverage band",
            "agent_action": "Agent action",
        }
        visible_columns = [
            column for column in history_columns if column in history_df.columns
        ]
        comparison_df = history_df[visible_columns].rename(
            columns=history_columns
        ).copy()
        if "Assessment time" in comparison_df.columns:
            comparison_df["Assessment time"] = comparison_df[
                "Assessment time"
            ].dt.strftime("%Y-%m-%d %H:%M:%S")
        if "Mean predicted-positive score" in comparison_df.columns:
            comparison_df["Mean predicted-positive score"] = (
                pd.to_numeric(
                    comparison_df["Mean predicted-positive score"],
                    errors="coerce"
                ) * 100
            ).round(2)
        if "Segmented coverage (%)" in comparison_df.columns:
            comparison_df["Segmented coverage (%)"] = pd.to_numeric(
                comparison_df["Segmented coverage (%)"], errors="coerce"
            ).round(2)

        st.subheader("Uploaded Image Comparison")
        st.caption(
            f"{len(comparison_df):,} saved assessment(s). New uploads are "
            "compared using their own U-Net segmentation outputs."
        )
        st.dataframe(
            comparison_df,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No readable prediction history is available yet.")
