# FUTURE IMPLEMENTATION PLAN: AUTOMATED CONTINUOUS MONITORING & 3D DIGITAL TWIN

**Document Version:** 1.0  
**Project Study Area:** Tirumala Hills, Andhra Pradesh, India  
**Execution Target:** Windows Laptop Environment (Python virtual environment)  

---

## 1. Roadmap Overview & Phased Execution

To build an automated, scientifically valid, laptop-friendly landslide monitoring system and realistic 3D Digital Twin, the implementation follows a 12-phase engineering plan:

```text
Phase 1: Repository Audit & Checkpoint (Completed)
   │
Phase 2: Full Geospatial 3D Terrain Construction (CesiumJS / 3D Tiles)
   │
Phase 3: Multi-Layer Satellite & GIS Evidence Integration in 3D
   │
Phase 4: Multi-Temporal Historical Timeline & Observation Scrubbing
   │
Phase 5: Automated Satellite (CDSE) & Rainfall (GPM/IMERG) Ingestion
   │
Phase 6: Automated Preprocessing & Valid InSAR Processing Workflow
   │
Phase 7: U-Net Model Input Synthesis, Validation & Inference Automation
   │
Phase 8: Automated Evidence-Based Risk Scoring & History Comparison
   │
Phase 9: Background Scheduler Daemon (APScheduler) & Pipeline Orchestration
   │
Phase 10: Local Spatial Database (SQLite/SpatiaLite) & Multi-Tab Dashboard
   │
Phase 11: Intelligent Decision-Support Alert System & Verification Logs
   │
Phase 12: End-to-End System Testing, Validation & Final Documentation
```

---

## 2. Detailed Phase Specifications

---

### Phase 1: Existing Repository Audit & Checkpoint
* **Objective:** Audit every component, catalog files, classify working vs incomplete code, and preserve working baseline.
* **Status:** **COMPLETED**
* **Artifacts Created:**
  - `backup/pre-master-implementation-phase1` Git branch
  - `PROJECT_AUDIT.md`
  - `EXISTING_IMPLEMENTATION.md`
  - `FUTURE_IMPLEMENTATION_PLAN.md`
  - `TECHNOLOGY_ARCHITECTURE.md`
* **Verification:** Repository clean, tests pass, baseline committed.

---

### Phase 2: Full Geospatial 3D Terrain Construction (CesiumJS)
* **Objective:** Construct a realistic, geospatially accurate 3D geographical digital twin of the entire Tirumala study area using real DEM data, replacing decorative representations with real terrain geometry.
* **Technical Details:**
  1. Load `tirumala_dem_80m_gsi_aoi.tif` (or higher-resolution Copernicus 30 m DEM if available).
  2. Convert DEM into 3D mesh / quantized-mesh terrain tiles or high-density glTF / 3D Tileset optimized for CesiumJS.
  3. Set up a standalone, self-hosted CesiumJS viewer application (`viewer/cesium/index.html`) using open-source CesiumJS (no Cesium Ion token hard dependencies).
  4. Implement accurate camera framing targeting Tirumala Hills centroid ($13.6768^\circ\text{N}, 79.3738^\circ\text{E}$, altitude $3,500\text{ m}$, pitch $-45^\circ$).
  5. Include full interactive navigation (orbital tilt, pan, zoom, compass, coordinate and elevation readouts).
* **Files to Create / Modify:**
  - `src/digital_twin/cesium_builder.py`: Pipeline to convert DEM raster to Cesium-ready terrain / glTF models.
  - `viewer/cesium/index.html`: CesiumJS viewer frontend with layer control and telemetry HUD.
  - `viewer/cesium/app.js`: Interactive camera, layer management, and click inspection logic.
  - `tests/test_cesium_builder.py`: Unit tests for DEM-to-mesh conversion.
* **Verification:** CesiumJS renders 3D elevation surface with genuine mountain relief matching known heights ($192\text{ m}–884\text{ m}$).

---

### Phase 3: Multi-Layer Satellite & GIS Evidence Integration in 3D
* **Objective:** Geographically register and overlay all existing and future project layers onto the 3D terrain model.
* **Layers to Support:**
  1. High-resolution satellite basemap (Esri World Imagery / Sentinel-2 RGB composite).
  2. Study-area polygon boundary (WGS84 GeoJSON).
  3. Digital Elevation colormap layer.
  4. Topographic Slope colormap layer ($0^\circ–50^\circ$).
  5. Sentinel-1 Line-of-Sight (LOS) displacement raster overlay.
  6. Sentinel-1 InSAR coherence ($\gamma$) raster overlay.
  7. Historical GSI landslide point markers (billboards with popup inspection cards).
  8. Spatial risk assessment zones (Low / Medium / High color-coded polygons).
* **Technical Details:**
  - Export raster overlays as georeferenced PNGs with matching geographic bounding coordinates `[west, south, east, north]`.
  - Export vector layers as clean GeoJSON / CZML entities.
  - Create layer visibility control checkboxes and transparency sliders in CesiumJS.
* **Files to Create / Modify:**
  - `src/digital_twin/layer_exporter.py`: Automates GeoTIFF $\to$ georeferenced RGBA PNG and GeoJSON conversion.
  - `viewer/cesium/layers.json`: Layer metadata registry.
  - `tests/test_layer_alignment.py`: Validates layer CRS and bounding-box alignment.
* **Verification:** When layers are toggled in 3D, InSAR fringes and GSI points align perfectly with hill topography and road contours.

---

### Phase 4: Multi-Temporal Historical Timeline & Observation Scrubbing
* **Objective:** Enable time-based observation selection and historical change analysis in the 3D Digital Twin and dashboard.
* **Technical Details:**
  1. Build an observation registry indexing each Sentinel-1 pair, IMERG rainfall period, and model evaluation date.
  2. Implement a CesiumJS Timeline and Streamlit date scrubber.
  3. Implement temporal differential comparison ($t_2 - t_1$) to highlight newly developing deformation or persistent displacement anomalies.
* **Files to Create / Modify:**
  - `src/features/temporal_registry.py`: Indexes temporal acquisition epochs.
  - `viewer/cesium/timeline.js`: Cesium animation and clock integration.
  - `tests/test_temporal_registry.py`: Validates chronological sorting and difference calculations.
* **Verification:** Moving the timeline slider dynamically updates the 3D overlays from Pair 1 to Pair 2, highlighting spatial change.

---

### Phase 5: Automated Satellite (CDSE) & Rainfall (GPM/IMERG) Ingestion
* **Objective:** Develop an automated data crawler that searches for new Sentinel-1, Sentinel-2, and NASA IMERG observations without manual downloads or duplicate files.
* **Technical Details:**
  1. **Copernicus Data Space Ecosystem (CDSE) Client:**
     - Query OData / STAC API using Tirumala bounding polygon:
       `POLYGON((79.337 13.639, 79.423 13.639, 79.423 13.693, 79.337 13.693, 79.337 13.639))`
     - Filter: `Collection: SENTINEL-1`, `ProductType: SLC`, `SensorMode: IW`, `Polarisation: VV+VH`, descending pass.
     - Check local catalog database before downloading to prevent duplicate downloads.
     - Store OAuth credentials in `.env` (`CDSE_USERNAME`, `CDSE_PASSWORD` / Access Token).
  2. **NASA GPM IMERG Client:**
     - Connect to NASA Earthdata GES DISC / GIBS API for IMERG V07C daily precipitation.
     - Download only new daily GeoTIFFs, clip to Tirumala AOI, and append to `tirumala_rainfall_features.csv`.
* **Files to Create / Modify:**
  - `scripts/download_sentinel1.py`: CDSE OData search and download client with resume and hash validation.
  - `scripts/download_rainfall.py`: NASA Earthdata IMERG daily harvester.
  - `src/data/catalog.py`: SQLite-backed catalog tracking product ID, acquisition timestamp, processing status, and local file paths.
  - `tests/test_data_ingestion.py`: Unit tests for API query parsing, bbox formatting, and duplicate rejection.
* **Verification:** Crawler identifies newly available passes, skips existing August 2026 products, and logs metadata.

---

### Phase 6: Automated Preprocessing & Valid InSAR Processing Workflow
* **Objective:** Establish a laptop-friendly, scientifically sound InSAR processing pipeline for newly retrieved Sentinel-1 SLC pairs.
* **Technical Details:**
  1. **Laptop Resource Constraint Handling:** Processing full Sentinel-1 SLC scenes locally requires 32+ GB RAM. We provide two robust operational modes:
     - **Mode A (Cloud-API / ASF HyP3):** Automated Python client (`hyp3_sdk`) submitting pair jobs for on-demand cloud interferogram processing, downloading clipped 80 m geocoded products directly.
     - **Mode B (Local Sub-swath / SNAP GPT):** Local sub-swath splitting and debursting focused strictly on the Tirumala AOI ($110 \times 69$ grid) using ESA SNAP Graph Processing Tool (`gpt`), keeping RAM usage $<8\text{ GB}$.
  2. **DInSAR Processing Chain:**
     - Orbit file application (Precise Orbit Ephemerides).
     - Co-registration using DEM-assisted back-geocoding.
     - Interferogram formation and topographic phase subtraction.
     - Multilooking ($20 \times 4$), Goldstein phase filtering, and coherence estimation.
     - Phase unwrapping via SNAPHU / MCF.
     - Quality masking: reject pixels with coherence $\gamma < 0.50$.
     - Range/Azimuth to Line-of-Sight (LOS) displacement conversion ($d_{\text{LOS}} = -\frac{\lambda}{4\pi}\Delta\phi$).
* **Files to Create / Modify:**
  - `scripts/process_insar.py`: Orchestrates InSAR generation and quality masking.
  - `src/preprocessing/insar_pipeline.py`: Modular interferometry processing wrapper.
  - `tests/test_insar_pipeline.py`: Validates raster alignment, CRS, and sanity thresholds on output displacement.
* **Verification:** Produces aligned, geocoded 80 m GeoTIFFs matching the canonical EPSG:32644 grid.

---

### Phase 7: U-Net Model Input Synthesis, Validation & Inference Automation
* **Objective:** Enable automated execution of the 14-channel U-Net model on incoming data while respecting Landslide4Sense input specifications.
* **Technical Details:**
  1. **Input Synthesis Adapter:**
     - Landslide4Sense expects `(128, 128, 14)` patches (Channels 0-11: Sentinel-2 optical bands; Channel 12: Slope; Channel 13: DEM).
     - Build an automated patch builder (`src/models/tirumala_patch_builder.py`) that extracts overlapping $128 \times 128$ patches across Tirumala from aligned Sentinel-2, DEM, and Slope rasters.
     - Apply proper normalization ($\text{float32}$, replacement of NaNs with zero).
  2. **Inference Pipeline:**
     - Execute `landslide_unet_14channel_best.pth` on generated patches.
     - Apply Sigmoid and threshold ($0.50$) to create binary segmentation masks.
     - Stitch patch predictions back into a seamless georeferenced hazard mask covering the study area.
     - Log prediction metadata (mean confidence, positive pixel percentage, timestamp).
* **Files to Create / Modify:**
  - `src/models/tirumala_patch_builder.py`: Synthesizes 14-channel HDF5/tensor patches from local GIS layers.
  - `scripts/run_unet.py`: Batch inference engine with geographic stitching.
  - `tests/test_unet_pipeline.py`: Validates input tensor dimensions, checkpoint loading, and inference determinism.
* **Verification:** Verified end-to-end inference on Tirumala patches without shape or dtype errors.

---

### Phase 8: Automated Evidence-Based Risk Scoring & History Comparison
* **Objective:** Automatically compute multi-criteria relative risk scores upon receipt of new observations and record historical deltas.
* **Technical Details:**
  1. Trigger `src/risk_assessment.py` when new InSAR, rainfall, or U-Net outputs are produced.
  2. Calculate updated risk scores and categories (`Low`, `Medium`, `High`) for all 2,650 grid cells.
  3. Compute temporal transition matrix: count pixels transitioning from Low $\to$ Medium, Medium $\to$ High, or vice versa.
  4. Flag persistent high-evidence hot-spots (cells exhibiting high indicators across multiple consecutive cycles).
* **Files to Create / Modify:**
  - `scripts/calculate_risk.py`: Batch risk evaluator generating updated CSV and database rows.
  - `src/features/risk_engine.py`: History comparison and trend evaluation module.
  - `tests/test_risk_engine.py`: Validates weight sums, category thresholds, and delta tracking.
* **Verification:** Risk engine updates evidence tables, correctly categorizing and logging score distributions.

---

### Phase 9: Background Scheduler Daemon & Pipeline Orchestration
* **Objective:** Implement a reliable, autonomous background runner executing data checks, processing, and model evaluation without user intervention.
* **Technical Details:**
  1. Use **APScheduler** (`BackgroundScheduler`) running as a lightweight Python process.
  2. Configurable job intervals:
     - Satellite Check Job: Runs every 6 or 12 hours (reflecting actual satellite orbital revisit periods).
     - Rainfall Check Job: Runs once daily at 06:00 UTC (matching IMERG product latency).
     - Model & Evidence Pipeline Job: Triggered immediately when new data arrives.
  3. Execution state persistence in SQLite (records job start time, duration, status, error tracebacks).
  4. Failure tolerance: if one data source fails (e.g. CDSE network timeout), the scheduler logs the error, continues other tasks, and retries with exponential backoff.
* **Files to Create / Modify:**
  - `automation/scheduler.py`: APScheduler daemon configuration, job hooks, and lifecycle management.
  - `automation/pipeline.py`: Master pipeline sequentially calling download $\to$ preprocess $\to$ InSAR $\to$ U-Net $\to$ risk $\to$ DB update.
  - `tests/test_scheduler.py`: Validates job registration, manual triggers, and error recovery.
* **Verification:** Scheduler triggers mock and real pipeline stages, records execution status, and logs outputs.

---

### Phase 10: Local Spatial Database & Multi-Tab Dashboard
* **Objective:** Replace static flat files with a structured local SQLite database and expand the Streamlit dashboard to 7 specialized monitoring views.
* **Technical Details:**
  1. **Database Schema (`database/monitoring.db`):**
     - Tables: `acquisitions`, `rainfall_records`, `spatial_evidence`, `temporal_evidence`, `risk_history`, `alerts`, `pipeline_logs`.
     - Spatial queries supported via bounding box and row/column indexing.
  2. **Streamlit Multi-Tab Dashboard:**
     - Tab 1: **Project Overview** (Key metrics, study area summary, data latency status).
     - Tab 2: **Interactive 3D Digital Twin** (CesiumJS embedded iframe + Plotly terrain view).
     - Tab 3: **Continuous Monitoring** (Acquisition history, rainfall charts, InSAR temporal profiles).
     - Tab 4: **Risk Assessment** (Low/Med/High breakdown, transition matrices, hotspot map).
     - Tab 5: **AI Results** (U-Net patch segmentation viewer, confidence distributions, validation metrics).
     - Tab 6: **Automation Status** (Scheduler health, last run time, next check, task logs).
     - Tab 7: **Alerts & Reports** (Active decision-support alerts, human review verification queue, PDF/CSV export).
* **Files to Create / Modify:**
  - `database/schema.sql`: Complete relational schema DDL.
  - `src/data/db.py`: Database connection manager and query helpers.
  - `dashboard/app.py`: Integrated multi-tab dashboard layout.
  - `tests/test_database.py`: Verifies schema creation, CRUD operations, and historical queries.
* **Verification:** Database stores and queries multi-date records; Streamlit dashboard displays all 7 functional tabs with live data.

---

### Phase 11: Intelligent Decision-Support Alert System & Verification Logs
* **Objective:** Generate transparent, threshold-based alerts for human review when compound risk conditions are satisfied.
* **Technical Details:**
  1. **Alert Rules Engine:**
     - Trigger Condition 1: 3-day rainfall accumulation $> 100\text{ mm}$ AND localized high slope ($>25^\circ$).
     - Trigger Condition 2: Significant LOS displacement ($>15\text{ mm}$) with coherence $\gamma \ge 0.65$ within $500\text{ m}$ of critical infrastructure or historical GSI points.
     - Trigger Condition 3: Compound risk score $\ge 66.67$ across a cluster of $\ge 3$ contiguous cells.
  2. **Alert Payloads:** Include timestamp, affected coordinates, triggering indicators, sensor quality metrics, and recommended human inspection steps.
  3. **Verification Workflow:** Mark alerts as `Pending Review`, `Verified in Field`, or `False Alarm (Decorrelation/Atmospheric)`.
  4. **Notifications:** Local logging + optional Telegram/Email webhook when configured in `.env`.
* **Files to Create / Modify:**
  - `src/agent/alert_engine.py`: Multi-criteria alert rule evaluator.
  - `scripts/generate_alerts.py`: CLI alert generator and dispatcher.
  - `tests/test_alert_engine.py`: Tests threshold trigger conditions and false-alarm suppression.
* **Verification:** Simulated extreme weather and displacement correctly trigger structured decision-support alerts.

---

### Phase 12: End-to-End System Testing, Validation & Final Documentation
* **Objective:** Comprehensive testing of the complete automated digital twin lifecycle and final documentation.
* **Technical Details:**
  1. Full regression test suite covering all modules.
  2. Smoke test: Run end-to-end pipeline on sample test dataset.
  3. Validate laptop memory usage ($<4\text{ GB}$ peak) and execution timing.
  4. Finalize user documentation, operating manual, and API guides.
* **Files to Create / Modify:**
  - `tests/test_end_to_end.py`: End-to-end pipeline integration test.
  - `USER_MANUAL.md`: Step-by-step operating guide for Windows.
  - `README.md`: Updated repository documentation.
* **Verification:** Full automated test suite passes (`pytest` exit code 0).
