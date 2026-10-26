import streamlit as st
import pandas as pd
import numpy as np
import h5py
import torch
import torch.nn as nn
from pathlib import Path
from datetime import datetime
import streamlit.components.v1 as components

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

FINAL_AGENT_FILE = (
    BASE_DIR
    / "data"
    / "features"
    / "tirumala_final_agent_evidence.csv"
)

RAIN_FILE = (
    BASE_DIR
    / "data"
    / "processed"
    / "rainfall"
    / "tirumala"
    / "tirumala_rainfall_features_20260801_20260829.csv"
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

SEGMENTATION_AGENT_FILE = (
    BASE_DIR
    / "outputs"
    / "reports"
    / "segmentation_agent_assessment.csv"
)

SEGMENTATION_AGENT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

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
def load_rainfall_data():

    if RAIN_FILE.exists():

        return pd.read_csv(
            RAIN_FILE
        )

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
                "region with relatively high model confidence. "
                "Review the predicted region against InSAR, terrain, "
                "rainfall, historical GSI evidence, and field evidence."
            )
        )

    return (
        "Priority review",
        (
            "The U-Net identified a segmented region, but the "
            "average confidence is below 0.75. Cross-check the "
            "prediction with independent remote-sensing and "
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
                f"model confidence of {confidence * 100:.2f}%. "
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
            f"model confidence is {confidence * 100:.2f}%. "
            f"The existing research evidence contains "
            f"{research_count:,} spatial observations. "
            "Review the U-Net prediction against independent "
            "remote-sensing and field evidence before drawing conclusions."
        )
    )

# ============================================================
# INTELLIGENT AGENT - QUESTION ANSWERING
# ============================================================

def answer_project_question(question, dataframe, rainfall_dataframe):
    """
    Grounded question-answering agent.
    Answers only from available project data.
    """

    q = question.lower().strip()
    
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

    if "insar" in q:
        return (
            "Sentinel-1 InSAR is used in the project to monitor "
            "surface deformation and temporal ground changes in Tirumala Hills."
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
            return (
                "Rainfall values before 29 August 2026:\n\n"
                "- 3-day rainfall: 0.2 mm\n"
                "- 7-day rainfall: 9.3 mm\n"
                "- 14-day rainfall: 12.7 mm\n\n"
                "Source: Project rainfall analysis using NASA GPM/IMERG data."
            )

        return (
            "The project uses NASA GPM/IMERG rainfall data. "
            "You can ask for the latest rainfall record or "
            "rainfall values before 29 August 2026."
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
            "The Digital Twin is an interactive representation of "
            "Tirumala Hills that visualizes integrated spatial evidence, "
            "temporal InSAR change, historical GSI locations and rainfall context."
        )
    
    # -------------------------------
    # How final evidence classes are assigned
    # -------------------------------
    if (
        "evidence class" in q
        or "evidence classes" in q
    ) and any(word in q for word in [
        "assign", "assigned", "calculate",
        "calculated", "combine", "combined",
        "generated", "each spatial observation"
    ]):
        return (
            "The project assigns evidence classes to spatial "
            "observations using available remote-sensing and "
            "terrain indicators.\n\n"
            "- Multiple spatial + temporal: multiple spatial "
            "indicators and temporal evidence are present.\n"
            "- Multiple spatial: multiple spatial indicators "
            "are present.\n"
            "- InSAR + temporal: InSAR and temporal-change "
            "evidence are present.\n"
            "- InSAR monitoring: InSAR monitoring evidence "
            "is present.\n"
            "- Terrain + temporal: terrain and temporal "
            "evidence are present.\n"
            "- Terrain: terrain evidence is present.\n"
            "- Temporal-change: temporal-change evidence "
            "is present.\n"
            "- No high spatial evidence: no high spatial "
            "evidence was identified by the current rules.\n\n"
            "Important limitation: the exact assignment logic "
            "depends on the feature-generation and evidence-classification "
            "code. The question-answering rules alone do not establish "
            "the full calculation or priority order."
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
        SEGMENTATION_AGENT_FILE,
        index=False
    )

    return report


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
    "Sentinel-1 InSAR monitoring, multi-temporal InSAR change, "
    "rainfall context, historical GSI evidence, and an "
    "explainable intelligent-agent evidence framework."
)


# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.header(
    "System Information"
)

st.sidebar.metric(
    "Spatial observations",
    len(df) if not df.empty else 0
)

st.sidebar.metric(
    "Temporal observations",
    2569
)

st.sidebar.metric(
    "GSI historical locations",
    15
)

if model_loaded:

    st.sidebar.success(
        "U-Net model loaded"
    )

    st.sidebar.caption(
        f"Model checkpoint epoch: "
        f"{model_epoch}"
    )

else:

    st.sidebar.error(
        "U-Net model failed to load"
    )

    st.sidebar.caption(
        model_error
    )


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

uploaded_file = st.file_uploader(
    "Upload 14-channel satellite image",
    type=["h5"],
    help=(
        "The trained checkpoint expects an HDF5 "
        "file containing an 'img' dataset with "
        "shape (128, 128, 14)."
    ),
)

st.info(
    "The current trained U-Net accepts only a "
    "14-channel HDF5 input with shape "
    "(128, 128, 14). A normal GeoTIFF or "
    "Sentinel-1 ZIP cannot be passed directly "
    "to this model without a separate "
    "preprocessing/conversion pipeline."
)


# ============================================================
# UPLOADED IMAGE PREDICTION
# ============================================================
if uploaded_file is not None:

    if not model_loaded:

        st.error(
            "Prediction cannot start because the "
            "U-Net checkpoint failed to load."
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
                average_confidence
            ) = run_unet_prediction(
                image
            )

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
            # EXISTING RESEARCH CONTEXT
            # ------------------------------------------------
            research_observation_count = len(
                df
            )

            # ------------------------------------------------
            # INTEGRATED AGENT
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
            # SAVE REPORT
            # ------------------------------------------------
            save_segmentation_report(
                source_file=uploaded_file.name,
                predicted_pixels=predicted_pixels,
                area_percent=landslide_percentage,
                confidence=average_confidence,
                action=agent_action,
                recommendation=agent_recommendation
            )

            st.success(
                "U-Net landslide segmentation "
                "completed successfully."
            )

            # =================================================
            # UPLOADED IMAGE ASSESSMENT
            # =================================================
            st.subheader(
                "Uploaded Image Assessment"
            )

            col1, col2, col3, col4 = st.columns(
                4
            )

            with col1:

                st.metric(
                    "Predicted Landslide Pixels",
                    f"{predicted_pixels:,}"
                )

            with col2:

                st.metric(
                    "Predicted Area",
                    f"{landslide_percentage:.2f}%"
                )

            with col3:

                st.metric(
                    "Average Confidence",
                    f"{average_confidence * 100:.2f}%"
                )

            with col4:

                st.metric(
                    "Agent Action",
                    agent_action
                )

            st.write(
                f"**Uploaded file:** "
                f"`{uploaded_file.name}`"
            )

            st.write(
                "**Important:** The segmentation "
                "output is model evidence from the "
                "uploaded image. It is not a calibrated "
                "landslide probability."
            )

            # =================================================
            # PROBABILITY MAP
            # =================================================
            st.subheader(
                "Landslide Probability Map"
            )

            st.image(
                probability,
                caption=(
                    "Pixel-wise U-Net "
                    "landslide probability"
                ),
                clamp=True,
                use_container_width=True
            )

            # =================================================
            # PREDICTED LANDSLIDE MASK
            # =================================================
            st.subheader(
                "Predicted Landslide Mask"
            )

            st.image(
                prediction_mask * 255,
                caption=(
                    "White = pixels predicted "
                    "as landslide "
                    f"(threshold = "
                    f"{PREDICTION_THRESHOLD:.2f})"
                ),
                clamp=True,
                use_container_width=True
            )

            # =================================================
            # LANDSLIDE DETECTION OVERLAY
            # =================================================
            st.subheader(
                "Landslide Detection Overlay"
            )

            rgb_image = make_rgb_preview(
                image
            )

            overlay = rgb_image.copy()

            overlay[
                prediction_mask == 1
            ] = [
                1.0,
                0.0,
                0.0
            ]

            st.image(
                overlay,
                caption=(
                    "Red = predicted "
                    "landslide regions"
                ),
                clamp=True,
                use_container_width=True
            )

            # =================================================
            # U-NET SEGMENTATION AGENT
            # =================================================
            st.subheader(
                "🧠 U-Net Segmentation Agent"
            )

            agent_col1, agent_col2 = st.columns(
                2
            )

            with agent_col1:

                st.metric(
                    "Agent Action",
                    agent_action
                )

            with agent_col2:

                st.write(
                    "**Agent Recommendation**"
                )

                st.write(
                    agent_recommendation
                )

            st.caption(
                "The action above is an "
                "evidence-based rule applied "
                "to the uploaded U-Net result. "
                "It is not a calibrated "
                "landslide probability."
            )

            # =================================================
            # INTEGRATED INTELLIGENT AGENT
            # =================================================
            st.subheader(
                "Integrated Intelligent-Agent Assessment"
            )

            st.write(
                "**Existing research context:** "
                f"{research_observation_count:,} "
                "spatial observations"
            )

            if integrated_action == "Priority review":

                st.warning(
                    integrated_recommendation
                )

            elif integrated_action == "Enhanced monitoring":

                st.info(
                    integrated_recommendation
                )

            else:

                st.success(
                    integrated_recommendation
                )

            st.caption(
                "The integrated assessment combines "
                "existing research-evidence context "
                "with the uploaded U-Net segmentation "
                "evidence. It is not a calibrated "
                "landslide-risk probability."
            )

            # =================================================
            # SPATIAL LIMITATION
            # =================================================
            st.warning(
                "The uploaded HDF5 prediction is "
                "currently model evidence only. "
                "Because the HDF5 input does not "
                "provide the geographic transform "
                "needed to place its pixels on the "
                "Tirumala Digital Twin, the prediction "
                "is not automatically added as a "
                "georeferenced map layer."
            )

        except Exception as prediction_error:

            st.error(
                f"Prediction failed: "
                f"{prediction_error}"
            )


# ============================================================
# CURRENT RESEARCH ASSESSMENT
# ============================================================
st.header(
    "📊 Current Research Assessment"
)

if df.empty:

    st.warning(
        "No Tirumala final agent evidence CSV "
        "was found."
    )

    st.code(
        str(FINAL_AGENT_FILE),
        language="text"
    )

else:

    evidence_series, evidence_column = (
        get_evidence_series(df)
    )

    if evidence_series is not None:

        counts = (
            evidence_series
            .value_counts()
        )

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

        evidence_display = pd.Series(
            {
                label:
                    int(
                        counts.get(
                            label,
                            0
                        )
                    )

                for label in preferred_labels
            }
        )

        c1, c2, c3, c4 = st.columns(
            4
        )

        with c1:

            st.metric(
                "Multiple spatial + temporal",
                int(
                    counts.get(
                        "Multiple spatial + temporal",
                        0
                    )
                )
            )

        with c2:

            st.metric(
                "Multiple spatial",
                int(
                    counts.get(
                        "Multiple spatial",
                        0
                    )
                )
            )

        with c3:

            st.metric(
                "InSAR + temporal",
                int(
                    counts.get(
                        "InSAR + temporal",
                        0
                    )
                )
            )

        with c4:

            st.metric(
                "No high spatial evidence",
                int(
                    counts.get(
                        "No high spatial",
                        0
                    )
                )
            )

        st.subheader(
            "Agent Evidence Distribution"
        )

        st.bar_chart(
            evidence_display
        )

    else:

        st.info(
            "The final evidence CSV does not "
            "contain a recognized evidence-class "
            "column."
        )


# ============================================================
# RAINFALL CONTEXT
# ============================================================
st.header(
    "🌧️ Rainfall Context"
)

if not rainfall_df.empty:

    latest_rain = rainfall_df.iloc[-1]

    daily_col = get_first_existing_column(
        rainfall_df,
        [
            "daily_rainfall_mm",
            "rainfall_mm",
            "reference_daily_rainfall_mm"
        ]
    )

    three_col = get_first_existing_column(
        rainfall_df,
        [
            "rainfall_3day_mm",
            "3day_rainfall_mm",
            "reference_3day_rainfall_mm"
        ]
    )

    seven_col = get_first_existing_column(
        rainfall_df,
        [
            "rainfall_7day_mm",
            "7day_rainfall_mm",
            "reference_7day_rainfall_mm"
        ]
    )

    fourteen_col = get_first_existing_column(
        rainfall_df,
        [
            "rainfall_14day_mm",
            "14day_rainfall_mm",
            "reference_14day_rainfall_mm"
        ]
    )

    date_col = get_first_existing_column(
        rainfall_df,
        [
            "date",
            "Date",
            "timestamp"
        ]
    )

    r1, r2, r3, r4 = st.columns(
        4
    )

    with r1:

        value = (
            safe_float(
                latest_rain[daily_col]
            )
            if daily_col
            else 0.0
        )

        st.metric(
            "Latest daily rainfall",
            f"{value:.1f} mm"
        )

    with r2:

        value = (
            safe_float(
                latest_rain[three_col]
            )
            if three_col
            else 0.0
        )

        st.metric(
            "3-day rainfall",
            f"{value:.1f} mm"
        )

    with r3:

        value = (
            safe_float(
                latest_rain[seven_col]
            )
            if seven_col
            else 0.0
        )

        st.metric(
            "7-day rainfall",
            f"{value:.1f} mm"
        )

    with r4:

        value = (
            safe_float(
                latest_rain[fourteen_col]
            )
            if fourteen_col
            else 0.0
        )

        st.metric(
            "14-day rainfall",
            f"{value:.1f} mm"
        )

    if date_col:

        st.caption(
            f"Latest rainfall record: "
            f"{latest_rain[date_col]}"
        )

else:

    st.info(
        "Rainfall feature file was not found."
    )

st.caption(
    "Rainfall values represent IMERG rainfall "
    "context and should not be interpreted as "
    "an 80 m rainfall layer."
)


# ============================================================
# DIGITAL TWIN
# ============================================================
st.header(
    "🗺️ Digital Twin"
)

st.write(
    "Integrated spatial evidence, temporal "
    "InSAR change, historical GSI locations, "
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


# ============================================================
# INTELLIGENT AGENT
# ============================================================
st.header(
    "🤖 Intelligent Agent"
)

st.write(
    "Explainable recommendations generated "
    "from the current evidence-based Digital "
    "Twin assessment."
)

if not df.empty:

    agent_display = df.copy()

    evidence_series, evidence_column = (
        get_evidence_series(
            agent_display
        )
    )

    if evidence_series is not None:

        agent_display[
            "evidence_class"
        ] = evidence_series

        decisions = (
            agent_display[
                "evidence_class"
            ]
            .apply(
                research_agent_decision
            )
        )

        agent_display[
            "agent_action"
        ] = decisions.apply(
            lambda x: x[0]
        )

        agent_display[
            "agent_recommendation"
        ] = decisions.apply(
            lambda x: x[1]
        )

    preferred = [

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

    available = [

        column

        for column in preferred

        if column in agent_display.columns
    ]

    if available:

        st.dataframe(
            agent_display[
                available
            ].head(50),
            use_container_width=True,
            height=420
        )

    else:

        st.dataframe(
            agent_display.head(50),
            use_container_width=True,
            height=420
        )

else:

    st.info(
        "No Digital Twin assessment "
        "records available."
    )

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
            rainfall_df
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
# LATEST U-NET AGENT REPORT
# ============================================================
st.header(
    "🧩 Latest U-Net Segmentation Agent Report"
)

if SEGMENTATION_AGENT_FILE.exists():

    try:

        segmentation_df = pd.read_csv(
            SEGMENTATION_AGENT_FILE
        )

        if not segmentation_df.empty:

            latest = (
                segmentation_df.iloc[-1]
            )

            s1, s2, s3 = st.columns(
                3
            )

            with s1:

                st.metric(
                    "Predicted Landslide Area",
                    f"{safe_float(latest.get('predicted_landslide_percentage', 0)):.2f}%"
                )

            with s2:

                st.metric(
                    "Average Confidence",
                    f"{safe_float(latest.get('average_confidence', 0)) * 100:.2f}%"
                )

            with s3:

                st.metric(
                    "Agent Action",
                    str(
                        latest.get(
                            "agent_action",
                            "N/A"
                        )
                    )
                )

            st.write(
                "**Source file:** "
                f"{latest.get('source_file', 'N/A')}"
            )

            st.write(
                "**Agent Recommendation:** "
                f"{latest.get('agent_recommendation', 'N/A')}"
            )

            if "timestamp" in latest:

                st.caption(
                    f"Generated: "
                    f"{latest['timestamp']}"
                )

    except Exception as report_error:

        st.warning(
            "Could not read the "
            f"segmentation-agent report: "
            f"{report_error}"
        )

else:

    st.info(
        "Upload a valid 14-channel HDF5 "
        "image to generate the latest "
        "U-Net segmentation-agent report."
    )


# ============================================================
# DIGITAL TWIN STATE
# ============================================================
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

    evidence_series, _ = (
        get_evidence_series(
            twin_display
        )
    )

    if evidence_series is not None:

        twin_display[
            "evidence_class"
        ] = evidence_series

    available_columns = [

        column

        for column in preferred_columns

        if column in twin_display.columns
    ]

    st.dataframe(
        (
            twin_display[
                available_columns
            ]
            if available_columns
            else twin_display
        ),
        use_container_width=True,
        height=450
    )

else:

    st.info(
        "Digital Twin state data "
        "is not available."
    )


# ============================================================
# FOOTER
# ============================================================
st.divider()

st.caption(
    "Data sources: Sentinel-1 InSAR, "
    "Copernicus DEM, GPM IMERG rainfall, "
    "and historical GSI evidence."
)

st.caption(
    "Risk/evidence classes are relative "
    "evidence indicators and are not "
    "calibrated landslide probabilities."
)

st.caption(
    "The uploaded U-Net segmentation "
    "result is model evidence and should "
    "be cross-checked with independent "
    "remote-sensing and field evidence."
)