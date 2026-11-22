"""
Tirumala Hills Landslide Digital Twin — Central Configuration

All project paths, study-area parameters, API endpoints, schedule intervals,
and risk-assessment thresholds are managed here. Values that need secrets
come from environment variables or a .env file.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    _ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
except ImportError:
    pass  # python-dotenv not installed; rely on system env vars


# ── Project Root ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ── Study Area ────────────────────────────────────────────────
@dataclass(frozen=True)
class StudyArea:
    """Tirumala Hills geographical extent."""
    name: str = "Tirumala Hills"
    state: str = "Andhra Pradesh"
    country: str = "India"
    # WGS-84 bounding box (west, south, east, north)
    bbox_west: float = 79.337
    bbox_south: float = 13.639
    bbox_east: float = 79.423
    bbox_north: float = 13.693
    # Centroid
    center_lon: float = 79.373845
    center_lat: float = 13.668008
    # UTM Zone 44N
    epsg_projected: int = 32644
    epsg_geographic: int = 4326
    # Grid specification (80 m)
    grid_resolution_m: float = 80.0
    grid_rows: int = 69
    grid_cols: int = 110

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return (self.bbox_west, self.bbox_south, self.bbox_east, self.bbox_north)

    @property
    def wkt_polygon(self) -> str:
        """WKT POLYGON for API queries."""
        w, s, e, n = self.bbox
        return (
            f"POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))"
        )


STUDY_AREA = StudyArea()


# ── File Paths ────────────────────────────────────────────────
@dataclass(frozen=True)
class ProjectPaths:
    root: Path = PROJECT_ROOT

    # Data directories
    data_raw: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw")
    data_processed: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed")
    data_features: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "features")

    # Specific raw subdirs
    raw_sentinel1: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw" / "sentinel1")
    raw_sentinel2: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw" / "sentinel2")
    raw_rainfall: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw" / "rainfall")
    raw_dem: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw" / "dem")
    raw_aoi: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw" / "aoi")
    raw_inventory: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw" / "inventory")

    # Processed subdirs
    processed_dinsar: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi")
    processed_rainfall: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "rainfall" / "tirumala")
    processed_sentinel2: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "sentinel2" / "tirumala")

    # Key raster files
    dem_tif: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_dem_80m_gsi_aoi.tif")
    slope_tif: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_slope_80m_gsi_aoi.tif")
    aspect_tif: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_aspect_80m_gsi_aoi.tif")
    los_tif: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_los_disp_80m_gsi_aoi.tif")
    corr_tif: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_corr_80m_gsi_aoi.tif")

    # Feature tables
    spatial_evidence_csv: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "features" / "tirumala_final_agent_evidence.csv")
    temporal_evidence_csv: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "features" / "tirumala_temporal_insar_features.csv")
    rainfall_features_csv: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed" / "rainfall" / "tirumala" / "tirumala_rainfall_features_20260801_20260829.csv")

    # AOI boundary
    aoi_geojson: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw" / "aoi" / "tirumala_hills_gsi_map_aoi.geojson")

    # Models
    models_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "models")
    unet_checkpoint: Path = field(default_factory=lambda: PROJECT_ROOT / "models" / "landslide_unet_14channel_best.pth")

    # Database
    database_file: Path = field(default_factory=lambda: PROJECT_ROOT / "database" / "monitoring.db")

    # Outputs
    outputs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "outputs")
    reports_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "outputs" / "reports")

    # Viewer
    viewer_cesium: Path = field(default_factory=lambda: PROJECT_ROOT / "viewer" / "cesium")
    viewer_textures: Path = field(default_factory=lambda: PROJECT_ROOT / "viewer" / "cesium" / "textures")
    viewer_data: Path = field(default_factory=lambda: PROJECT_ROOT / "viewer" / "cesium" / "data")

    # Dashboard
    dashboard_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "dashboard")

    # Logs
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")

    def ensure_dirs(self):
        """Create all required directories."""
        dirs = [
            self.data_raw, self.data_processed, self.data_features,
            self.raw_sentinel1, self.raw_sentinel2, self.raw_rainfall,
            self.raw_dem, self.raw_aoi, self.raw_inventory,
            self.processed_dinsar, self.processed_rainfall, self.processed_sentinel2,
            self.models_dir, self.outputs_dir, self.reports_dir,
            self.viewer_textures, self.viewer_data,
            self.logs_dir,
            self.database_file.parent,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


PATHS = ProjectPaths()


# ── API Credentials ───────────────────────────────────────────
@dataclass
class Credentials:
    """Loaded from environment / .env — never hardcoded."""
    cdse_username: str = field(default_factory=lambda: os.environ.get("CDSE_USERNAME", ""))
    cdse_password: str = field(default_factory=lambda: os.environ.get("CDSE_PASSWORD", ""))
    earthdata_username: str = field(default_factory=lambda: os.environ.get("EARTHDATA_USERNAME", ""))
    earthdata_password: str = field(default_factory=lambda: os.environ.get("EARTHDATA_PASSWORD", ""))
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    telegram_bot_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID", ""))
    smtp_host: str = field(default_factory=lambda: os.environ.get("SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = field(default_factory=lambda: int(os.environ.get("SMTP_PORT", "587")))
    smtp_username: str = field(default_factory=lambda: os.environ.get("SMTP_USERNAME", ""))
    smtp_password: str = field(default_factory=lambda: os.environ.get("SMTP_PASSWORD", ""))
    alert_email_to: str = field(default_factory=lambda: os.environ.get("ALERT_EMAIL_TO", ""))


CREDENTIALS = Credentials()


# ── Sentinel-1 Configuration ─────────────────────────────────
@dataclass(frozen=True)
class Sentinel1Config:
    collection: str = "SENTINEL-1"
    product_type: str = "SLC"
    sensor_mode: str = "IW"
    polarisation: str = "VV&VH"
    orbit_direction: str = "DESCENDING"
    # CDSE OData API
    odata_base: str = "https://catalogue.dataspace.copernicus.eu/odata/v1"
    download_base: str = "https://zipper.dataspace.copernicus.eu/odata/v1"
    token_url: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    # Processing
    grid_resolution_m: float = 80.0
    coherence_threshold: float = 0.50
    min_temporal_baseline_days: int = 6
    max_temporal_baseline_days: int = 36


SENTINEL1 = Sentinel1Config()


# ── Sentinel-2 Configuration ─────────────────────────────────
@dataclass(frozen=True)
class Sentinel2Config:
    collection: str = "SENTINEL-2"
    product_type: str = "S2MSI2A"  # Level-2A (atmospherically corrected)
    max_cloud_cover: float = 30.0
    odata_base: str = "https://catalogue.dataspace.copernicus.eu/odata/v1"
    # Band mapping for NDVI and RGB
    red_band: str = "B04"
    nir_band: str = "B08"
    rgb_bands: Tuple[str, ...] = ("B04", "B03", "B02")


SENTINEL2 = Sentinel2Config()


# ── Rainfall Configuration ────────────────────────────────────
@dataclass(frozen=True)
class RainfallConfig:
    product: str = "GPM_3IMERGDF"  # IMERG Final Daily
    version: str = "07C"
    base_url: str = "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGDF.07"
    variable: str = "precipitation"
    units: str = "mm/day"
    scale_factor: float = 0.1
    accumulation_windows: Tuple[int, ...] = (1, 3, 7, 14)
    # Data latency: IMERG Final has ~3.5 month latency
    # IMERG Late (near-real-time) has ~14 hour latency
    late_product: str = "GPM_3IMERGDL"
    late_base_url: str = "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGDL.07"


RAINFALL = RainfallConfig()


# ── Risk Assessment Thresholds ────────────────────────────────
@dataclass(frozen=True)
class RiskConfig:
    # Weight allocations (must sum to 1.0)
    weight_slope: float = 0.40
    weight_terrain: float = 0.25
    weight_insar: float = 0.20
    weight_temporal: float = 0.15
    # Category thresholds (0-100 score)
    threshold_low: float = 33.33
    threshold_high: float = 66.67
    # Indicator thresholds
    high_slope_deg: float = 25.0
    high_elevation_m: float = 500.0
    significant_los_mm: float = 15.0
    high_coherence: float = 0.65
    # Alert-triggering compound conditions
    alert_rainfall_3day_mm: float = 100.0
    alert_risk_score: float = 66.67
    alert_cluster_min_cells: int = 3
    alert_los_mm: float = 15.0
    alert_gsi_proximity_km: float = 0.5


RISK = RiskConfig()


# ── U-Net Model Configuration ────────────────────────────────
@dataclass(frozen=True)
class UNetConfig:
    input_channels: int = 14
    input_height: int = 128
    input_width: int = 128
    output_channels: int = 1
    threshold: float = 0.50
    batch_size: int = 2  # CPU-friendly
    # Channel specification (Landslide4Sense)
    # 0-11: Sentinel-2 optical bands (B01-B12 equivalents)
    # 12: Slope
    # 13: DEM
    optical_channels: int = 12
    slope_channel: int = 12
    dem_channel: int = 13
    # Validation metrics from Landslide4Sense benchmark
    benchmark_dice: float = 0.6561
    benchmark_iou: float = 0.5101


UNET = UNetConfig()


# ── Scheduler Configuration ───────────────────────────────────
@dataclass(frozen=True)
class SchedulerConfig:
    monitoring_interval_hours: int = field(
        default_factory=lambda: int(os.environ.get("MONITORING_INTERVAL_HOURS", "6"))
    )
    # Check intervals (in hours)
    sentinel1_check_hours: int = 12
    sentinel2_check_hours: int = 24
    rainfall_check_hours: int = 6
    # Pipeline trigger
    pipeline_check_hours: int = 1
    # Retry on failure
    max_retries: int = 3
    retry_backoff_minutes: int = 15
    # Timezone
    timezone: str = "Asia/Kolkata"


SCHEDULER = SchedulerConfig()


# ── InSAR Processing Configuration ───────────────────────────
@dataclass(frozen=True)
class InSARConfig:
    # Processing mode: 'hyp3' (cloud) or 'snap' (local)
    processing_mode: str = "hyp3"
    # HyP3 settings
    hyp3_api_url: str = "https://hyp3-api.asf.alaska.edu"
    hyp3_job_type: str = "INSAR_GAMMA"
    hyp3_dem: str = "copernicus"
    hyp3_looks: str = "20x4"
    hyp3_phase_filter: float = 0.6
    hyp3_resolution: int = 80
    # SNAP GPT settings (local mode)
    snap_gpt_path: str = "gpt"  # Assumes SNAP gpt is on PATH
    snap_max_memory_gb: int = 8
    # Quality thresholds
    min_coherence: float = 0.50
    wavelength_m: float = 0.05546  # C-band wavelength


INSAR = InSARConfig()


# ── Logging ───────────────────────────────────────────────────
import logging

def setup_logging(name: str = "landslide_twin", level: int = logging.INFO) -> logging.Logger:
    """Configure project-wide logging."""
    PATHS.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(level)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        ch.setFormatter(fmt)
        logger.addHandler(ch)
        # File handler
        fh = logging.FileHandler(PATHS.logs_dir / f"{name}.log", encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger
