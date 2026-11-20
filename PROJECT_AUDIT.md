# PROJECT AUDIT: TIRUMALA HILLS LANDSLIDE DIGITAL TWIN

**Audit Timestamp:** 2026-11-20  
**Project Workspace:** `C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin`  
**Git Branch:** `experiment/3d-digital-twin` (Checkpoint branch: `backup/pre-master-implementation-phase1`)  
**Lead Roles:** Senior Remote Sensing Engineer, GIS Developer, AI/ML Engineer, 3D Digital Twin Developer, Full-Stack Python Developer  

---

## 1. Executive Summary

This audit assesses the state of the **Tirumala Hills Landslide Monitoring and Risk Assessment Digital Twin**. The project integrates satellite remote sensing (Sentinel-1 InSAR), topographic data (Copernicus/HyP3 DEM and derived slope), meteorological data (NASA GPM/IMERG rainfall), historical landslide records (GSI published map points), deep learning segmentation (PyTorch 14-channel U-Net), rule-based decision support (Intelligent Agent), and interactive GIS interfaces.

### Core Audit Findings
- **Strengths:** 
  1. A well-constructed, quality-screened geospatial feature database (2,650 spatial records, 2,569 temporal InSAR records) on a strictly aligned 80 m grid in UTM Zone 44N (EPSG:32644).
  2. A fully operational canonical Streamlit dashboard (`dashboard/app.py`) providing system metrics, evidence tables, rainfall context, U-Net inference demonstration, and an embedded 2D Leaflet GIS digital twin (`results/digital_twin/tirumala_final_digital_twin.html`).
  3. A georeferenced 3D terrain surface generator (`src/digital_twin/terrain_3d.py`) displaying local DEM elevation and multi-layer overlays (Elevation, Slope, Coherence, LOS displacement).
  4. A transparent, rule-based evidence scoring system (`src/risk_assessment.py`) avoiding fabricated landslide probabilities.
- **Gaps & Deficiencies for Continuous Operation:**
  1. No automated data ingestion pipeline: satellite acquisitions and IMERG files are currently manual, static snapshots (August 2026).
  2. No automated continuous InSAR processor: the project relied on offline ASF HyP3 products extracted locally under `C:\S1\HyP3\Tirumala\extracted`.
  3. The 3D Digital Twin uses Plotly mesh visualization rather than a full geospatial 3D globe/tileset engine (CesiumJS).
  4. The U-Net model is trained on the global Landslide4Sense benchmark and lacks Tirumala-specific domain transfer.
  5. No database engine: features are stored in flat CSV and GeoTIFF files without indexing or ACID transaction history.
  6. No background automation daemon or scheduler (APScheduler/cron).

---

## 2. Directory Structure and Repository Organization

The repository contains 62 scripts, 28 source modules, 4 model checkpoints/artifacts, 7,965 raw files (predominantly Landslide4Sense HDF5 patches), 40 processed raster assets, and 24 structured feature datasets.

```text
landslide_digital_twin/
├── dashboard/                     # Streamlit application directory
│   ├── app.py                     # Canonical Tirumala dashboard (3,967 lines)
│   └── app1.py ... app14.py       # Legacy / backup iterations (requires cleanup)
├── data/
│   ├── raw/
│   │   ├── aoi/                   # Tirumala GeoJSON boundaries (WGS84)
│   │   ├── dem/                   # Raw DEM GeoTIFFs
│   │   ├── inventory/             # GSI Figure 3.2 digitized landslide points
│   │   ├── landslide4sense/       # HDF5 train/val patches (14 channels)
│   │   ├── rainfall/              # IMERG Daily V07C GeoTIFFs (Aug 11-29, 2026)
│   │   └── sentinel1/             # Raw Sentinel-1 SLC SAFE archives
│   ├── processed/
│   │   ├── dinsar/tirumala/       # Clipped and masked InSAR rasters (80m, EPSG:32644)
│   │   └── rainfall/tirumala/     # Clipped daily rainfall rasters and time series
│   └── features/                  # Tabular spatial and temporal feature datasets
├── models/
│   ├── landslide_unet_14channel_best.pth  # PyTorch U-Net checkpoint (7.5 MB)
│   ├── landslide_unet_14channel_test.pth  # Testing checkpoint
│   ├── landslide_random_forest.joblib     # Patch-level RF (147 MB)
│   └── landslide_random_forest_v2.joblib  # Patch-level RF (1.2 GB)
├── outputs/                       # Statistical reports, Moran's I permutation tests
├── results/
│   └── digital_twin/              # Folium Leaflet 2D HTML map and PNG overlays
├── scripts/                       # 62 standalone analytical and data prep scripts
├── src/
│   ├── agent/                     # Decision agent logic
│   ├── digital_twin/              # 3D terrain and twin generation
│   ├── features/                  # Slope, alignment, and raster extraction
│   ├── models/                    # U-Net architecture, training, and inference
│   └── risk_assessment.py         # Multi-criteria evidence scoring
└── tests/                         # Unit tests (e.g. test_digital_twin_3d.py)
```

---

## 3. Comprehensive Component Classification

Each component is classified into one of four states:
- **[WORKING]**: Fully implemented, verified with unit tests and runtime checks.
- **[PARTIAL]**: Implemented with limited scope, offline assets, or static windows.
- **[NEEDS_IMPROVEMENT]**: Working but suffers from architectural debt, poor discoverability, or performance bottlenecks.
- **[NOT_IMPLEMENTED]**: Identified in system architecture but nonexistent in code.

### 3.1 Data Ingestion & Satellite Processing

| Component | Status | Existing File(s) | Assessment & Action Required |
| :--- | :---: | :--- | :--- |
| **Sentinel-1 CDSE Search & Download** | **[NOT_IMPLEMENTED]** | None | Raw SLCs were manually staged in `data/raw/sentinel1/`. Need automated Copernicus Data Space API crawler with spatial/temporal/orbit filters and duplicate detection. |
| **InSAR Phase Processing Workflow** | **[PARTIAL]** | `scripts/clip_insar_to_gsi_aoi.py`, `scripts/clip_second_insar_to_gsi_aoi.py` | Relies on pre-generated ASF HyP3 output products. Local differential interferometry engine (SNAP/MintPy wrapper or HyP3 API client) is missing. |
| **InSAR Reference Point Assessment** | **[WORKING]** | `scripts/verify_second_insar_pair.py`, `outputs/final_reference_region_assessment_v2/` | Robust screening for Region 1 reference stability, Moran's I spatial autocorrelation tests, and phase unwrapping error checks. |
| **NASA GPM IMERG Rainfall Ingestion** | **[PARTIAL]** | `scripts/calculate_rainfall_features.py`, `data/processed/rainfall/` | Static retrieval of August 2026 IMERG V07C daily data. Lacks automated REST API polling from NASA GES DISC / Earthdata. |
| **Rainfall Accumulation Engine** | **[WORKING]** | `src/features/create_rainfall_features.py` | Correctly calculates 1-day, 3-day, 7-day, and 14-day rolling precipitation accumulations. |
| **DEM & Slope Extraction** | **[WORKING]** | `src/features/calculate_slope.py`, `scripts/calculate_gsi_aoi_slope.py` | Accurate Horn algorithm slope generation in degrees from 80 m DEM in EPSG:32644. |
| **Historical Landslide Inventory** | **[WORKING]** | `data/raw/inventory/tirumala_gsi_fig32_map_derived_inventory.csv` | 15 digitized GSI landslide hazard points digitized from published reports with coordinate uncertainty caveats. |

### 3.2 AI / ML & Risk Assessment

| Component | Status | Existing File(s) | Assessment & Action Required |
| :--- | :---: | :--- | :--- |
| **PyTorch U-Net Segmentation Architecture** | **[WORKING]** | `src/models/landslide_segmentation.py` | 14-channel input, 4-stage encoder-decoder with skip connections, batch normalization, and ReLU activations. |
| **U-Net Checkpoint Loading & Inference** | **[WORKING]** | `src/models/predict_uploaded_landslide.py`, `models/landslide_unet_14channel_best.pth` | Loads cleanly; achieves Val Dice 0.6561, IoU 0.5101 on Landslide4Sense benchmark. |
| **U-Net Tirumala Domain Transfer** | **[NOT_IMPLEMENTED]** | None | The U-Net requires 14 specific optical/terrain/radar bands (`(128, 128, 14)`). It cannot directly ingest arbitrary satellite GeoTIFFs without band synthesis and normalization. |
| **Random Forest Susceptibility Model** | **[NEEDS_IMPROVEMENT]**| `models/landslide_random_forest_v2.joblib` (1.2 GB), `src/models/train_random_forest.py` | Model is huge (1.2 GB), trained only on 2 features (slope, elevation) from Landslide4Sense patches, and rightly omitted from the production dashboard due to lack of local training labels. |
| **Evidence-Based Risk Scoring** | **[WORKING]** | `src/risk_assessment.py` | Transparent weighted scoring (Slope 40%, Terrain 25%, InSAR 20%, Temporal 15%) mapping to Low, Medium, and High categories. |
| **Intelligent Agent Decision Logic** | **[WORKING]** | `src/agent/landslide_agent.py`, `dashboard/app.py` | Rule-based decision engine recommending monitoring frequencies and field verification without fabricating probabilities. |

### 3.3 Digital Twin & Visualizations

| Component | Status | Existing File(s) | Assessment & Action Required |
| :--- | :---: | :--- | :--- |
| **2D Leaflet GIS Map** | **[WORKING]** | `results/digital_twin/tirumala_final_digital_twin.html` | High-quality Folium map with Esri satellite basemap, AOI boundary polygon, InSAR raster overlays, and GSI marker tooltips. |
| **3D Terrain Surface (Plotly)** | **[WORKING]** | `src/digital_twin/terrain_3d.py` | Georeferenced UTM surface mesh with 4 colormap overlays and vertical exaggeration slider. Fully tested and operational. |
| **CesiumJS Realistic 3D Globe Viewer** | **[NOT_IMPLEMENTED]** | None | Requires CesiumJS integration with quantized-mesh terrain, 3D tiles, satellite imagery streaming, and time-dynamic entity layers. |
| **Multi-temporal 3D Observation Slider** | **[PARTIAL]** | `dashboard/app.py` | Temporal difference is displayed statically between the two August 2026 pairs; continuous timeline scrubbing is missing. |

### 3.4 Automation, Backend & Database

| Component | Status | Existing File(s) | Assessment & Action Required |
| :--- | :---: | :--- | :--- |
| **Automation Scheduler** | **[NOT_IMPLEMENTED]** | None | No background task daemon (APScheduler) exists to orchestrate retrieval, processing, and alerts. |
| **End-to-End Processing Pipeline** | **[PARTIAL]** | Fragmented scripts in `scripts/` | Data processing requires running multiple disconnected scripts in sequence. Needs unified `automation/pipeline.py`. |
| **Relational / Spatial Database** | **[NOT_IMPLEMENTED]** | None | Relies entirely on static CSV files (`tirumala_final_agent_evidence.csv`). Needs SQLite/SpatiaLite or PostgreSQL/PostGIS. |
| **Intelligent Alert Generation** | **[PARTIAL]** | Rule checks in `dashboard/app.py` | Rules flag high-evidence pixels in UI, but automated dispatch (email/webhook/telegram) and alert logs are missing. |

---

## 4. Technical Debt and Repository Anomalies

1. **Duplicate Dashboard Files:**  
   The `dashboard/` directory contains 14 numbered backup files (`app1.py` through `app14.py`, `app_backup_final2.py`, etc.). These total over 20 MB of redundant code and cause confusion regarding the canonical entry point. `dashboard/app.py` is the single source of truth.
2. **Hardcoded Machine-Specific Paths:**  
   Several scripts in `scripts/` reference `C:\S1\HyP3\Tirumala\extracted\pair_05_17` and Windows drive paths that break when cloned to other systems. All file operations must use relative `Path(__file__).resolve().parents[...]`.
3. **Moghalrajpuram Legacy Code:**  
   Scripts and features for a separate study area (Moghalrajpuram, Vijayawada) remain in `src/agent/landslide_agent.py`, `src/dashboard/app.py`, and `data/features/moghalrajpuram_*`. They must remain segregated and not leak into Tirumala monitoring workflows.
4. **Untracked File Artifacts:**  
   An untracked file with control characters (`"lide digital twin for deployment\357\200\242"`) and massive 1.2 GB `.joblib` model binaries exist in the working directory.

---

## 5. Audit Conclusion & Readiness Matrix

| Objective Area | Current State | Target Future State | Complexity |
| :--- | :---: | :---: | :---: |
| **Phase 1: Audit & Checkpoint** | **100% COMPLETE** | Baseline preserved & documented | Low |
| **Phase 2: 3D Terrain Construction** | **80% COMPLETE** | Plotly 3D working; migrate to CesiumJS 3D | Medium |
| **Phase 3: Satellite & GIS Layers in 3D** | **70% COMPLETE** | 4 layers aligned; add CZML / 3D tiles | Medium |
| **Phase 4: Multi-temporal Observation** | **40% COMPLETE** | Add multi-date time series database | Medium |
| **Phase 5: Automated Ingestion (CDSE/IMERG)**| **0% COMPLETE** | Implement automated Python API clients | High |
| **Phase 6: Automated Preprocessing & InSAR** | **30% COMPLETE** | Build modular pipeline & quality checks | High |
| **Phase 7: AI/ML Inference Integration** | **75% COMPLETE** | U-Net operational; build Tirumala adapter | High |
| **Phase 8: Evidence Risk Engine** | **85% COMPLETE** | Formula active; link to live updates | Low |
| **Phase 9: Scheduler & Automation Pipeline** | **0% COMPLETE** | Build APScheduler automation daemon | Medium |
| **Phase 10: Unified Backend, DB & Dashboard**| **50% COMPLETE** | SQLite spatial schema + multi-tab UI | High |
| **Phase 11: Automated Alerting & Reports** | **25% COMPLETE** | Build structured alert logging & notifier | Medium |
| **Phase 12: End-to-End Validation** | **60% COMPLETE** | Full regression test suite | Medium |
