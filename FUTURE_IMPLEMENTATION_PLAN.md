# FUTURE IMPLEMENTATION PLAN: AUTOMATED CONTINUOUS MONITORING & 3D DIGITAL TWIN

**Document Version:** 1.0  
**Project Study Area:** Tirumala Hills, Andhra Pradesh, India  
**Execution Target:** Windows Laptop Environment (Python virtual environment)  

---

## 1. Roadmap Overview & Phased Execution

To build an automated, scientifically valid, laptop-friendly landslide monitoring system and realistic 3D Digital Twin, the implementation follows a 12-phase engineering plan:

The execution order below follows the user's current master prompt and
supersedes the phase order in the older technical notes that follow. Work stops
at the end of each phase for verification and documentation.

```text
Phase 1: Audit and preserve the existing project
   │
Phase 2: Validate and complete accurate Tirumala 3D terrain
   │
Phase 3: Integrate existing GIS evidence layers in 3D
   │
Phase 4: Index available observations and select processed InSAR pairs
   │
Phase 5: Discover and ingest Sentinel-1, Sentinel-2, and GPM data
   │
Phase 6: Automate preprocessing and validate InSAR processing
   │
Phase 7: Integrate scientifically compatible model analysis
   │
Phase 8: Add evidence-based risk scoring and history comparison
   │
Phase 9: Add background scheduling and pipeline orchestration
   │
Phase 10: Unify the database and dashboard
   │
Phase 11: Add human-verified alerts and optional notifications
   │
Phase 12: Validate and document the end-to-end workflow
```

### Current execution status (2026-11-21; reverified after implementation)

- **Phase 1 (Audit & Preservation):** Audit complete; selective checkpoint pending. The current tree remains dirty; do not stage it broadly.
- **Phase 2 (3D Terrain & CesiumJS):** COMPLETE. NoData-safe DEM mesh, validated projected grid and exaggeration, and working Cesium rendering.
- **Phase 3 (GIS Evidence Layers):** COMPLETE. Six aligned raster layers are embedded in DEM terrain meshes; AOI/GSI vectors are placed using DEM elevations, with nearest-sample distances disclosed.
- **Phase 4 (Temporal Observation Registry):** COMPLETE FOR AVAILABLE DATA. The registry indexes 35 epochs and the Cesium/Streamlit controls select the two processed InSAR pairs. No cross-pair subtraction is shown because their phase references are independent; other observation dates are not historical map layers.
- **Phase 5 (Automated Data Ingestion):** PARTIAL; LIVE RETRIEVAL UNVERIFIED. CDSE clients now paginate, surface API failures, retry undownloaded catalog entries, and write downloads atomically. IMERG extraction applies the V07 scale and fill mask, preserves Final/Late quality, and computes calendar-complete windows. No authenticated live retrieval was attempted; available source data remains static.
- **Phase 6 (InSAR Processing & Preprocessing):** PARTIAL. Grid preprocessing and HyP3 status handling are tested, but complete automated InSAR product generation and alignment are not verified.
- **Phase 7 (PyTorch 14-Channel U-Net):** PARTIAL. Benchmark inference and patch-building code exist, but Tirumala-specific inputs and predictions are not validated.
- **Phase 8 (Evidence-Based Risk Scoring):** OFFLINE-VERIFIED. Risk results and history writes are idempotent; cell transitions and consecutive hotspots are tested. Pipeline/CLI observations use processed InSAR dates instead of the run date. There are not enough trustworthy acquisition epochs to establish a live temporal trend.
- **Phase 9 (Automation Daemon & Pipeline):** PARTIAL. APScheduler is declared and installed, and pipeline dry-run behavior is tested as non-mutating. Live scheduled ingestion and full preprocessing/InSAR orchestration are not verified.
- **Phase 10 (SQLite Database & Multi-Tab Dashboard):** PARTIAL. Database CRUD and per-instance connection isolation are tested; dashboard operation against live, continually ingested data is not verified.
- **Phase 11 (Intelligent Decision-Support Alerts):** PARTIAL. Rule evaluation, persisted logging, and missing-rainfall handling are tested. External notification delivery and field verification remain unconfigured/unverified.
- **Phase 12 (End-to-End Validation & Documentation):** OFFLINE-VERIFIED. The full test suite passes (66 tests plus 6 subtests); authenticated ingestion, operational InSAR output generation, and a live end-to-end run remain unverified.

---

## 2. Detailed Phase Specifications

---

### Phase 1: Existing Repository Audit & Checkpoint
* **Objective:** Audit every component, catalog files, classify working vs incomplete code, and preserve working baseline.
* **Status:** **Audit completed 2026-11-21; selective checkpoint pending.**
* **Artifacts Created:**
  - `backup/pre-master-implementation-phase1` Git branch
  - `PROJECT_AUDIT.md`
  - `EXISTING_IMPLEMENTATION.md`
  - `FUTURE_IMPLEMENTATION_PLAN.md`
  - `TECHNOLOGY_ARCHITECTURE.md`
* **Verification at audit time:** All 10 tests then present passed in the project `venv`;
  targeted Python compilation and Cesium JavaScript syntax checks pass. The
  current worktree is not clean, so the existing branch checkpoint does not
  preserve its untracked files. No live API or pipeline run was performed.

---

### Phase 2: Full Geospatial 3D Terrain Construction (CesiumJS)
* **Current status:** **COMPLETE for terrain construction.** The DEM builder
  validates projected, north-up, meter-based rasters and positive finite
  exaggeration; it omits faces touching NoData and derives normals from valid
  faces. The four layer meshes and default model were regenerated. The source
  DEM has 4,083 valid cells and 3,507 NoData cells; each layer mesh has 7,821
  valid triangles.
* **Verification:** 13 focused terrain/layer tests pass. Generated GLB indices
  were checked against the DEM validity mask. Browser validation confirmed all
  four terrain models load. The GLBs use 1× mesh exaggeration; the existing
  Cesium slider supplies the display exaggeration, preventing the former 2× × 2×
  double scaling. Layer draping/alignment is tracked under Phase 3.
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
* **Verification:** The browser loads all four DEM-derived meshes. The source
  raster is 80 m, EPSG:32644, and its measured valid elevation span is
  180.03–899.16 m. Layer-to-terrain alignment is verified in Phase 3.

---

### Phase 3: Multi-Layer Satellite & GIS Evidence Integration in 3D
* **Current status:** **COMPLETE for the available static evidence layers.**
  Exported elevation, slope, aspect, LOS displacement, coherence, and risk-zone
  textures are embedded in six DEM-aligned GLB meshes. The AOI boundary and GSI
  markers are positioned at sampled terrain heights; GSI popups expose distance
  to the nearest valid DEM sample. Some map-derived GSI markers are more than
  500 m from a valid cell because of DEM NoData coverage, so those heights are
  approximate.
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
  - `src/digital_twin/layer_exporter.py`: Validates raster grids and exports RGBA textures and terrain GLBs.
  - `viewer/cesium/layers_manifest.json`: Layer and terrain-model metadata.
  - `viewer/cesium/app.js`: Loads textured terrain layers and DEM-positioned vectors.
  - `tests/test_layer_exporter.py`: Validates alignment, nodata masking, units, and model export.
* **Verification:** 16 focused terrain/layer tests pass. All six generated GLBs
  have 7,821 faces referencing valid DEM cells. Browser checks confirmed all
  models load, the layer checkbox/opacity controls work, and vector heights
  track vertical exaggeration. The base Esri imagery and evidence layers use
  separate globe/mesh surfaces; no Sentinel-2 RGB terrain texture is available.

---

### Phase 4: Multi-Temporal Historical Timeline & Observation Scrubbing
* **Current status:** **COMPLETE FOR AVAILABLE DATA, WITH SCIENTIFIC LIMITATIONS.**
  The registry contains 35 chronological epochs, and the Cesium viewer and
  Streamlit dashboard select between the two available processed InSAR pairs.
  Each pair uses an independent phase reference, so an unqualified
  pair-to-pair displacement difference is not calculated. Rainfall and risk
  dates are indexed but do not have historical map layers.
* **Objective:** Enable time-based observation selection and historical change analysis in the 3D Digital Twin and dashboard.
* **Technical Details:**
  1. Build an observation registry indexing each Sentinel-1 pair, IMERG rainfall period, and model evaluation date.
  2. Implement a CesiumJS Timeline and Streamlit date scrubber.
  3. Implement a temporal differential comparison only when the observations
     share a compatible reference and processing basis. The available pairs do
     not meet that condition, so the cross-pair difference is intentionally
     withheld.
* **Files to Create / Modify:**
  - `src/features/temporal_registry.py`: Indexes temporal acquisition epochs.
  - `viewer/cesium/app.js`, `viewer/cesium/index.html`, `viewer/cesium/cesium.css`: Pair selection, layer visibility, and inspection controls.
  - `dashboard/app.py`: Streamlit pair selector synchronized with the viewer.
  - `tests/test_temporal_registry.py`: Validates chronological sorting, registry export, coordinate conversion, and pair-raster quality masks/alignment.
* **Verification:** Focused temporal/exporter tests pass; browser checks confirm
  slider and previous/next controls switch the selected pair, only that pair's
  model is visible, the URL is synchronized, and the inspector uses that pair's
  LOS/coherence values. No unsupported cross-pair change is presented.

---

### Phase 5: Automated Satellite (CDSE) & Rainfall (GPM/IMERG) Ingestion
* **Current status:** **PARTIAL; LIVE RETRIEVAL UNVERIFIED.** CDSE OData
  pagination, explicit request errors, retryable catalog states, atomic archive
  downloads, and IMERG Final/Late handling are implemented. IMERG values use
  the documented 0.1 scale and fill-value mask; rolling totals require complete
  calendar windows. Focused offline tests pass. No authenticated live download
  was attempted.
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
* **Verification:** Mocked tests cover OData pagination and propagated API
  failures; raster tests cover IMERG scaling and NoData handling; database tests
  cover download retries. Live authentication, retrieval, and downstream
  processing still require user-provided credentials and verification.

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
