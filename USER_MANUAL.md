# Tirumala Hills Landslide Digital Twin — User & Operations Manual
## Continuous Monitoring, 3D Geospatial Digital Twin, AI Inference & Automated Risk Assessment

**Study Area:** Tirumala Hills, Tirupati District, Andhra Pradesh, India  
**Geographic Bounds:** $13.639^\circ\text{N}$ to $13.693^\circ\text{N}$, $79.337^\circ\text{E}$ to $79.423^\circ\text{E}$  
**Projected Coordinate System:** WGS 84 / UTM Zone 44N (EPSG:32644)  
**Analytical Resolution:** 80 m ($69 \times 110$ grid nodes, 2,650 validated AOI cells)

> **Verification status (2026-11-22):** This manual describes code paths, not a
> production-readiness guarantee. Live downloads and the complete
> dataset-to-viewer workflow have not been operationally verified. See the
> verified implementation and remaining-work reports before enabling automation.

---

## 1. System Overview & Architecture

The research prototype contains components for monitoring and evidence review, including:
- **Satellite InSAR:** Sentinel-1 descending orbit interferometry (ASF HyP3 cloud processing & SNAP graph generator)
- **Optical Remote Sensing:** Copernicus Sentinel-2 MSI L2A with cloud masking and NDVI calculation
- **Meteorological Tracking:** NASA GPM IMERG Final Daily (V07C) precipitation with 1d, 3d, 7d, 14d rolling sums
- **Topographic Modeling:** Copernicus GLO-30 DEM, Horn's finite-difference slope gradient, and terrain aspect
- **Historical Hazards:** 15 digitized GSI landslide hazard locations from published survey reports
- **Deep Learning:** 14-channel PyTorch U-Net segmentation benchmark model with Tirumala patch synthesis
- **Evidence Assessment:** Multi-criteria weighted risk index (Slope 40%, Terrain 25%, InSAR 20%, Temporal 15%)
- **Relational Storage:** SQLite database (`database/monitoring.db`) with complete audit trails
- **3D Digital Twin:** Standalone WebGL CesiumJS globe with raycasting inspector and Plotly analytical mesh
- **Automation Daemon:** Python APScheduler running background satellite searches and pipeline orchestration

---

## 2. Windows Environment Setup

### 2.1 Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Windows 10/11 64-bit
- Google Chrome or Edge for the WebGL 3D Digital Twin

### 2.2 Configure Credentials (`.env`)
Create `.env` from `.env.example` only when it does not already exist:
```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```
Edit `.env` with your free credentials:
```ini
# Copernicus Data Space Ecosystem (CDSE)
CDSE_USERNAME=your_email@example.com
CDSE_PASSWORD=your_password

# NASA Earthdata Login (for IMERG & ASF HyP3)
EARTHDATA_USERNAME=your_earthdata_username
EARTHDATA_PASSWORD=your_earthdata_password

# Gemini project question-answering agent (optional)
GEMINI_API_KEY=your_gemini_api_key

# Default recurring monitoring interval
MONITORING_INTERVAL_HOURS=6
```
Telegram and SMTP credentials are optional. Never commit `.env` or paste
credentials into logs or reports. Missing credentials block only their
corresponding integrations.

---

## 3. Quick Start — Launching the System

Do not initialize or reseed the existing SQLite database as part of normal
startup; it contains existing project records.

### Start the 3D CesiumJS Server
Serves the 3D Digital Twin viewer locally on port 8088:
```powershell
.\venv\Scripts\python.exe scripts\serve_3d_viewer.py
```
> Access in browser: [http://localhost:8088](http://localhost:8088)

### Launch the Streamlit Dashboard
Launches the six-tab dashboard on port 8501:
```powershell
.\venv\Scripts\python.exe -m streamlit run dashboard\app.py --server.port 8501
```
> Access in browser: [http://localhost:8501](http://localhost:8501)

---

## 4. Dashboard Views (6 Tabs)

1. **📊 1. Overview:**
   - Study area extent, spatial grid counts (4,083 total, 2,650 AOI validated).
   - Displays local project evidence and the project Q&A assistant.
   - Data freshness depends on the background scheduler and successful feeds.

2. **🏔️ 2. 3D Digital Twin:**
   - **CesiumJS 3D WebGL Globe:** Real terrain relief, Esri World Imagery basemap, georeferenced raster overlays, 15 GSI pins, and on-click raycasting inspection.
   - **Plotly 3D Surface Mesh:** Interactive analytical mesh with vertical exaggeration slider (1.0x–10.0x) and overlay switcher (Elevation, Slope, LOS Displacement, Coherence).
   - **2D Leaflet GIS Map:** Folium GIS map with layer toggles and legends.

3. **🛰️ 3. Continuous Monitoring:**
   - Sentinel-1 & Sentinel-2 acquisition catalog with orbit, polarisation, and status.
   - InSAR baseline pairs with perpendicular baseline, temporal baseline, and coherence.
   - Interactive NASA GPM IMERG precipitation chart with 1d, 3d, 7d, and 14d antecedent rolling curves.
   - Download queue, last discovery times, observation freshness, and retry control.

4. **⚠️ 4. Risk Assessment:**
   - Multi-criteria weighted evidence methodology:
     $$\text{Risk Score} = 0.40 \times \text{Slope} + 0.25 \times \text{Terrain} + 0.20 \times \text{InSAR} + 0.15 \times \text{Temporal}$$
   - Category distribution (Low $< 33.33$, Medium $33.33–66.67$, High $\ge 66.67$).
   - Historical observation epochs and transition matrices (e.g., Low $\to$ Medium).

5. **⚙️ 5. Automation Status:**
   - Scheduler liveness, next run, current pipeline stage, and execution history.
   - Manual pipeline trigger, viewer export, and failed-download retry controls.

6. **🚨 6. Alerts & Reports:**
   - Active decision-support alerts with severity badges (🔴 CRITICAL, 🟡 WARNING, 🔵 INFO).
   - Triggering indicators summary (rainfall accumulation, steep slopes, InSAR anomalies).
   - Human verification workflow: Operator buttons to mark alerts as "Verified" or "False Alarm".
   - Official disclaimer: Decision-support notifications requiring field verification.

---

## 5. Automation Daemon & Background Scheduling

### Running the APScheduler Daemon
The single background scheduler starts one end-to-end pipeline cycle at daemon
startup and then repeats at `MONITORING_INTERVAL_HOURS` (default: 6):
```powershell
.\venv\Scripts\python.exe automation\scheduler.py start
```

The laptop must remain powered on and connected to the internet. Closing the
Streamlit tab does not stop the scheduler. Pipeline stages with unavailable
credentials or processing dependencies report blocked/warning status; this
does not establish an end-to-end successful run.

Register a task to start at the current user's sign-in (only changes Windows
Task Scheduler when explicitly run):
```powershell
.\scripts\register_windows_task.ps1 -PythonPath "$PWD\venv\Scripts\python.exe"
```
The user must sign in after boot; this is not configured as a Windows service
that runs before login.

### Checking Scheduler & System Telemetry
```powershell
.\venv\Scripts\python.exe automation\scheduler.py status
```

### Manual Job Triggering
```powershell
# Manually trigger a pipeline run
.\venv\Scripts\python.exe automation\scheduler.py trigger --job pipeline

# Manually trigger a satellite search
.\venv\Scripts\python.exe automation\scheduler.py trigger --job sentinel1_check

# Manually trigger rainfall ingestion
.\venv\Scripts\python.exe automation\scheduler.py trigger --job rainfall_check
```

---

## 6. Command-Line Processing Scripts

Every component is modular and can be run independently:

| Script | Purpose | Command Example |
| :--- | :--- | :--- |
| `scripts/download_sentinel1.py` | Search & download Sentinel-1 SLC | `python scripts/download_sentinel1.py --dry-run` |
| `scripts/download_sentinel2.py` | Search & download Sentinel-2 L2A | `python scripts/download_sentinel2.py --dry-run` |
| `scripts/download_rainfall.py` | Ingest NASA IMERG rainfall | `python scripts/download_rainfall.py --dry-run` |
| `scripts/process_insar.py` | InSAR processing (HyP3 / SNAP) | `python scripts/process_insar.py --check-status` |
| `scripts/preprocess_data.py` | Clip & reproject rasters | `python scripts/preprocess_data.py --input <tif> --output <tif>` |
| `scripts/extract_features.py` | Extract spatial grid features | `python scripts/extract_features.py` |
| `scripts/run_unet.py` | Batch U-Net patch inference | `python scripts/run_unet.py --threshold 0.50` |
| `scripts/calculate_risk.py` | Compute multi-criteria risk | `python scripts/calculate_risk.py` |
| `scripts/generate_alerts.py` | Evaluate alert trigger rules | `python scripts/generate_alerts.py` |
| `scripts/update_database.py` | Sync SQLite & export 3D lookups | `python scripts/update_database.py --export-cesium` |
| `automation/pipeline.py` | Run master pipeline | `python automation/pipeline.py --stage feature_extraction` |

Sentinel-1/2 `--dry-run` commands query the remote catalog but do not download or
register discovered products; CDSE credentials and network access are still
needed for those searches. The IMERG `--dry-run` command does not query NASA; it
only checks local state. Configure credentials in `.env` before real retrieval.
Live retrieval has not yet been verified.

---

## 7. Verification & Testing

Run the offline regression tests that do not access remote services or mutate
the production database:
```powershell
.\venv\Scripts\python.exe -m pytest -q tests\test_data_ingestion.py tests\test_insar_pipeline.py tests\test_risk_engine.py tests\test_preprocess_data.py tests\test_end_to_end.py::TestDatabaseAndCatalog::test_catalog_duplicate_detection tests\test_end_to_end.py::TestMasterPipelineDryRun tests\test_layer_exporter.py tests\test_temporal_registry.py tests\test_unet_pipeline.py tests\test_scheduler.py tests\test_digital_twin_3d.py tests\test_cesium_builder.py
```

Remote catalog/download tests, live credential checks, notification delivery,
SNAP/HyP3 InSAR execution, and a real product-to-viewer run require separate
credentials/data/dependencies and are not demonstrated by this offline suite.
The existing `tests\test_automated_monitoring_workflow.py` accesses live APIs
and the project database; inspect its effects and configure credentials before
running it.

---

## 8. Scientific Caveats & Research Standards

1. **Exploratory InSAR Differences:**  
   Because independent interferograms use reference points separated by tens of kilometers, differential displacement ($\Delta\text{LOS}$) contains residual orbital and atmospheric phase ramps. They are exploratory indicators, not millimeter-precision ground truth.
2. **U-Net Domain Transfer:**  
   The U-Net model was trained on the Landslide4Sense benchmark dataset. Predictions on Tirumala patches represent automated screening assistance and must never replace field verification by qualified engineering geologists.
3. **Decision-Support Alerts:**  
   Alerts generated by this system are decision-support notifications intended to prioritize monitoring and field reconnaissance. They do not constitute official disaster declarations.
