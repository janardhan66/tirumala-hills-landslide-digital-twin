# TECHNOLOGY ARCHITECTURE SPECIFICATION
## Automated Continuous Landslide Monitoring and 3D Digital Twin for Tirumala Hills

**Document Version:** 1.0  
**Project Study Area:** Tirumala Hills, Tirupati District, Andhra Pradesh, India  
**Target Environment:** Local Windows Laptop (Python Virtual Environment, Zero Paid Cloud Dependencies)  

---

## 1. System Architecture Overview

### Verified implementation status

The implemented research prototype has a verified one-cycle live InSAR workflow:
ASF HyP3 job `3889d809-88a3-4a93-89a5-258821932737` succeeded, was downloaded,
validated, clipped and aligned to EPSG:32644 at 80 m, stored in SQLite and
exported to the CesiumJS viewer for 21 November 2026. This does not prove
fully repeated, unattended multi-temporal monitoring.

The system is structured as a multi-tiered, modular geospatial intelligence and digital twin platform:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                            TIER 1: DATA SOURCES                              │
│  Copernicus Data Space (S-1 / S-2)  │  NASA GES DISC (IMERG) │  Copernicus DEM│
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ HTTPS / REST / OData
                                       v
┌──────────────────────────────────────────────────────────────────────────────┐
│                    TIER 2: AUTOMATION & INGESTION ENGINE                     │
│  APScheduler Daemon  │  Duplicate Checker  │  Data Validator & Catalog       │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ Raw Products (.SAFE, .tif, .zip)
                                       v
┌──────────────────────────────────────────────────────────────────────────────┐
│                 TIER 3: PREPROCESSING & FEATURE EXTRACTION                   │
│  DInSAR Phase Unwrapping & Quality Mask (80m)  │  Horn's Topographic Slope    │
│  IMERG Rolling Accumulations (1d, 3d, 7d, 14d) │  GSI Historical Proximity    │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ Aligned GeoTIFFs / UTM 44N (EPSG:32644)
                                       v
┌──────────────────────────────────────────────────────────────────────────────┐
│                    TIER 4: AI/ML & RISK ASSESSMENT CORE                      │
│  PyTorch 14-Channel U-Net Segmentation  │  Weighted Relative Evidence Engine │
│  Intelligent Decision-Support Agent     │  Multi-Temporal Trend Comparator   │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ Model Outputs, Risk Classes, Alerts
                                       v
┌──────────────────────────────────────────────────────────────────────────────┐
│                     TIER 5: STORAGE & HISTORICAL DATABASE                    │
│  SQLite / SpatiaLite Database (monitoring.db)                                │
│  Tables: acquisitions, rainfall, evidence_grid, risk_history, alerts, logs   │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ GeoJSON, CZML, PNG Overlays, SQLite queries
                                       v
┌──────────────────────────────────────────────────────────────────────────────┐
│                    TIER 6: USER INTERFACES & DIGITAL TWIN                    │
│  CesiumJS 3D Globe Viewer  │  Plotly 3D Terrain  │  Streamlit Multi-Tab App │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Technology Stack

| Layer | Technologies Selected | Technical Justification |
| :--- | :--- | :--- |
| **Data Ingestion** | Python `requests`, `urllib3`, CDSE OData API, NASA GES DISC | Lightweight, scriptable, no heavy external SDK requirements. |
| **Geospatial Processing** | `rasterio`, `geopandas`, `shapely`, `pyproj` | Industry-standard Python spatial libraries; high performance, GDAL bindings. |
| **InSAR Analysis** | ASF HyP3 REST API / ESA SNAP `gpt` (laptop-friendly sub-swaths) | Avoids 32+ GB RAM local crashes while ensuring rigorous phase unwrapping. |
| **Deep Learning** | `PyTorch 2.x`, `torchvision`, `h5py` | Direct execution of existing 14-channel U-Net checkpoint (`.pth`). |
| **Machine Learning** | `scikit-learn`, `scipy`, `numpy`, `pandas` | Proven statistical tools for Moran's I autocorrelation and risk weighting. |
| **Automation** | `APScheduler 3.x` | In-process Python scheduler; cross-platform (Windows compatible), zero daemon hassle. |
| **Database** | `SQLite 3` with JSON1 & Spatial extensions | Self-contained, single-file (`monitoring.db`), zero server installation, laptop-safe. |
| **3D Digital Twin** | `CesiumJS` (WebGL) + `Plotly.js` (Surface Mesh) | Realistic 3D globe with genuine terrain elevation, camera control, and layer toggles. |
| **2D GIS Map** | `Folium` / `Leaflet.js` | Interactive web map with Esri satellite basemaps and custom CSS legends. |
| **Dashboard UI** | `Streamlit 1.x / 2.0` | Rapid, reactive Python web UI; existing canonical frontend. |

---

## 3. Coordinate Systems & Geodetic Standards

To prevent spatial misalignment between satellite measurements, terrain models, and web displays, the architecture strictly enforces standard coordinate transformations:

```text
                  Raw Satellite / Web Viewers (EPSG:4326)
                  WGS 84 Latitude / Longitude in Degrees
                                    ▲
                                    │ pyproj Transformer
                                    │ (always_xy=True)
                                    ▼
                Analytical Processing & InSAR (EPSG:32644)
                WGS 84 / UTM Zone 44N in Metric Units (Meters)
```

1. **Analytical Grid (EPSG:32644):**
   - Resolution: Exactly $80.0\text{ m} \times 80.0\text{ m}$ cell size.
   - Spatial Grid Origin: Left: $319,720.0\text{ m}$, Top: $1,514,360.0\text{ m}$.
   - Matrix Extent: 69 Rows $\times$ 110 Columns (7,590 cells total; 2,650 valid study area cells).
   - Used for: Slope calculation, InSAR phase unwrapping, Euclidean distance to GSI points, cell-by-cell joins.

2. **Display & Web Visualization (EPSG:4326):**
   - Geodetic Datum: WGS 84.
   - Used for: Leaflet 2D tiles, CesiumJS 3D globe coordinates, GeoJSON layer boundaries, popup tooltips.

---

## 4. Relational Database Schema Design (`database/monitoring.db`)

The storage tier uses a relational schema designed to retain full historical records:

```sql
-- 1. Satellite Product Catalog
CREATE TABLE acquisitions (
    acquisition_id TEXT PRIMARY KEY,
    satellite TEXT NOT NULL,           -- 'Sentinel-1', 'Sentinel-2'
    sensor_mode TEXT NOT NULL,         -- 'IW', 'MSI'
    orbit_direction TEXT,              -- 'DESCENDING', 'ASCENDING'
    acquisition_date TEXT NOT NULL,    -- 'YYYY-MM-DD'
    start_time TEXT,
    polarisation TEXT,                 -- 'VV+VH'
    download_status TEXT NOT NULL,     -- 'DOWNLOADED', 'PROCESSED', 'FAILED'
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Daily Rainfall Context
CREATE TABLE rainfall_records (
    record_date TEXT PRIMARY KEY,      -- 'YYYY-MM-DD'
    daily_mean_mm REAL NOT NULL,
    daily_max_mm REAL,
    rolling_3day_mm REAL NOT NULL,
    rolling_7day_mm REAL NOT NULL,
    rolling_14day_mm REAL NOT NULL,
    source_product TEXT DEFAULT 'NASA GPM IMERG V07C',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Spatial Evidence Grid (Current State & History)
CREATE TABLE spatial_evidence_grid (
    cell_id TEXT PRIMARY KEY,          -- 'R{row}_C{col}'
    row_idx INTEGER NOT NULL,
    col_idx INTEGER NOT NULL,
    utm_easting REAL NOT NULL,
    utm_northing REAL NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    elevation_m REAL NOT NULL,
    slope_deg REAL NOT NULL,
    latest_los_disp_m REAL,
    latest_coherence REAL,
    dist_to_gsi_km REAL,
    risk_score REAL NOT NULL,          -- 0.0 to 100.0
    risk_category TEXT NOT NULL,       -- 'Low', 'Medium', 'High'
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Multi-Temporal InSAR Observations History
CREATE TABLE temporal_insar_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cell_id TEXT NOT NULL,
    pair_id TEXT NOT NULL,             -- e.g. 'PAIR_20260817_20260829'
    acquisition_date_1 TEXT NOT NULL,
    acquisition_date_2 TEXT NOT NULL,
    los_displacement_m REAL,
    coherence REAL,
    differential_change_m REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(cell_id) REFERENCES spatial_evidence_grid(cell_id)
);

-- 5. Intelligent Decision-Support Alerts
CREATE TABLE alerts (
    alert_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trigger_rule TEXT NOT NULL,
    affected_cells_count INTEGER NOT NULL,
    center_latitude REAL NOT NULL,
    center_longitude REAL NOT NULL,
    max_risk_score REAL NOT NULL,
    summary_text TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    verification_status TEXT DEFAULT 'PENDING' -- 'PENDING', 'VERIFIED', 'FALSE_ALARM'
);

-- 6. Background Automation Execution Logs
CREATE TABLE pipeline_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_name TEXT NOT NULL,
    status TEXT NOT NULL,              -- 'SUCCESS', 'WARNING', 'ERROR'
    duration_seconds REAL,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. 3D Digital Twin Architecture: CesiumJS Integration

The primary 3D Digital Twin frontend uses **CesiumJS** running in a local web view, embedded seamlessly into Streamlit via `st.components.v1.iframe`:

```text
┌────────────────────────────────────────────────────────┐
│                   CESIUMJS 3D VIEWER                   │
│                                                        │
│  [ Satellite Imagery Base ]  (Esri World Imagery)      │
│            ▲                                           │
│            │ draped over                               │
│  [ Real 3D Terrain Model ]   (DEM Elevation Mesh)      │
│            ▲                                           │
│            │ superimposed with                         │
│  [ Dynamic Spatial Layers ]  (CZML / GeoJSON / PNG)    │
│    • InSAR LOS Fringe Overlay                          │
│    • Coherence Quality Mask                            │
│    • Slope Distribution Colormap                       │
│    • GSI Historical Landslide Pins                     │
│    • Real-Time Risk Hazard Polygons                    │
│                                                        │
│  [ Interactive HUD Controls ]                          │
│    • Timeline scrubber (time-series playback)          │
│    • Camera fly-to viewpoints                          │
│    • Layer visibility & opacity sliders                │
│    • On-click Raycast Coordinate & Feature Inspector   │
└────────────────────────────────────────────────────────┘
```

### Key Interactive Inspector Features:
When a user clicks any location on the 3D mountain surface:
- Cesium ray-casts screen coordinates to Cartesian3 ($X, Y, Z$).
- Converts coordinates to WGS84 (Latitude, Longitude, Height).
- Queries local SQLite grid for nearest spatial cell.
- Displays an interactive HUD Card:
  - **Location:** Lat/Lon & Elevation ($z\text{ meters}$).
  - **Terrain:** Slope angle ($^\circ$).
  - **InSAR Evidence:** Line-of-sight displacement & coherence.
  - **Rainfall:** 3-day and 7-day antecedent precipitation.
  - **Risk Classification:** Relative evidence category (`Low`, `Medium`, `High`).

---

## 6. Automation & Scheduling Architecture

The automation subsystem operates as an in-process or detached Python service (`automation/scheduler.py`):

```text
                     ┌───────────────────────┐
                     │   APScheduler Daemon  │
                     └──────────┬────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          v (Every 6h)          v (Daily at 06:00Z)   v (On New Data Event)
   [ Sentinel-1 Check ]   [ NASA IMERG Check ]   [ Processing Pipeline ]
          │                     │                     │
          v                     v                     v
   Query CDSE API        Query GES DISC         Execute Pipeline:
   (Filter Tirumala)     (Download V07C)        1. Clip & Align Rasters
          │                     │               2. Compute Slope & Features
          v                     v               3. Run U-Net Patch Inference
   If New Product:       If New Data:           4. Update Evidence Scores
   Download SLC          Append Timeseries      5. Store in Database
   Trigger Pipeline      Trigger Pipeline       6. Check Alert Rules
                                                7. Refresh 3D Overlays
```

---

## 7. Laptop Resource Optimization Guidelines

Because the application runs on a standard development laptop, the following safeguards are implemented:

1. **Memory Ceiling ($< 4\text{ GB}$ Peak RAM):**
   - Spatial clipping is performed at the earliest possible stage: satellite scenes ($> 1\text{ GB}$) are immediately cropped to the $110 \times 69$ Tirumala grid.
   - Rasterio chunked window reading (`Window(col_off, row_off, width, height)`) is used for all raster I/O.
   - PyTorch inference runs with `torch.no_grad()` and batch size 1 or 2 on CPU.
2. **Disk Space Economy:**
   - Temporary intermediate SAR raw files are purged or compressed after feature extraction.
   - Overlays are exported as indexed, compressed 8-bit RGBA PNGs ($< 100\text{ KB}$ each) rather than uncompressed multi-megabyte GeoTIFFs.
3. **Graceful Degradation:**
   - If internet access is unavailable or satellite APIs are down, the system continues running offline, clearly signaling `Data: Offline Cached Mode` in the dashboard telemetry panel.
