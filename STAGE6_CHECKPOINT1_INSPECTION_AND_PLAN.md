# Stage 6 Checkpoint 1: Inspection and Implementation Plan

**Assessment date:** 22 November 2026

## 1. Active Workspace

Active project root:

`C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin`

Repository:

`janardhan66/tirumala-hills-landslide-digital-twin`

The existing Streamlit application is under `dashboard/app.py`. The existing
Cesium viewer is under `viewer/cesium/`.

## 2. Database Backup

Checkpoint 1 database backup:

`database/backups/monitoring_stage6_checkpoint1_20261122T130738Z.db`

No source code or database data was changed during this inspection.

## 3. Existing Architecture Inspected

The project retains the Stage 1-5 implementation:

- Sentinel-1 CDSE discovery and catalog management.
- ASF HyP3 submission/status/product orchestration.
- SQLite acquisition, pair, temporal observation and pipeline tables.
- 69 x 110, 80 m EPSG:32644 spatial grid.
- 7590 spatial evidence snapshots.
- 7590 traceable temporal InSAR observations.
- Rule-based empirical risk assessment.
- Streamlit six-tab dashboard.
- CesiumJS terrain, pair, texture and status exports.
- Gemini assistant integration.
- APScheduler/Windows task monitoring.

## 4. Existing Data Audit

### Sentinel-1 and InSAR

- Existing processed pair:
  `PAIR_20261109_20261121`
- HyP3 job:
  `3889d809-88a3-4a93-89a5-258821932737`
- LOS and coherence rasters:
  Available and aligned to EPSG:32644, 69 x 110, 80 m.
- Quality-valid InSAR temporal observations:
  5034
- Real SBAS/network readiness:
  Insufficient data

These layers are suitable for an evidence module only. LOS remains relative
to the pair-specific phase reference and is not vertical displacement.

### Rainfall

Existing rainfall files contain 29 dates for 1-29 August 2026. The database
contains 29 rainfall records.

The current rainfall feature file is study-area-level context:

- `rainfall_mean_mm`
- 3-, 7- and 14-day accumulations
- No demonstrably pixel-specific spatial rainfall raster

Live GES DISC retrieval was blocked:

- NASA GES DISC Earthdata download returned HTTP 401.
- Official CMR/`.nc4` discovery works.
- Existing rainfall records must be preserved.

### DEM and terrain

Available:

- DEM raster:
  `tirumala_dem_80m_gsi_aoi.tif`
- Slope raster:
  `tirumala_slope_80m_gsi_aoi.tif`
- Aspect raster:
  `tirumala_aspect_80m_gsi_aoi.tif`
- Terrain alignment:
  EPSG:32644, 80 m, 69 x 110

Drainage derivatives are not confirmed and will not be added until a real
DEM-based workflow is validated.

### Historical inventory

Available GSI inventory data includes 15 map-derived approximate locations.

The CSV and GeoJSON describe map-derived/reference coordinates, not surveyed
GPS ground truth.

They are suitable for supporting proximity evidence only.

### Land cover

No land-cover raster or LULC dataset was found under `data/`.

No raw or processed Sentinel-2 files are currently available:

- Raw Sentinel-2 files: 0
- Processed Sentinel-2 TIF files: 0

Land cover is therefore **NOT TESTED/BLOCKED** by missing data.

### U-Net

Available:

- 3799 image H5 patches.
- 3799 mask H5 patches.
- Saved checkpoint:
  `landslide_unet_14channel_best.pth`

Validated sample shape:

- Input: `(128, 128, 14)`, float64 source.
- Output mask: `(128, 128)`, uint8.
- Channel order: HWC in source H5; code converts to CHW.
- Channels 12 and 13 are described as slope and DEM.

Local Tirumala validation remains unavailable. The model must remain a
Landslide4Sense benchmark demonstration unless independent local ground truth
is added.

## 5. Existing Risk Formula

The existing formula remains:

```text
Risk Score =
  0.40 x slope percentile
  + 0.25 x terrain indicator
  + 0.20 x InSAR indicator
  + 0.15 x temporal indicator
```

Unavailable components are omitted and available weights are renormalized.
The output is explicitly an empirical evidence index, not a calibrated
landslide probability.

Stage 6 will implement a separate multi-factor framework rather than silently
changing or replacing this formula.

## 6. Gemini

Gemini live generation was verified with `gemini-3.1-flash-lite`.

The current assistant retrieves fixed database telemetry and project
documentation. Stage 6 will add structured, read-only factor explanations
without allowing SQL or database modification.

## 7. External API Status

| Source | Status |
|---|---|
| CDSE Sentinel-1 metadata | PASS/LIVE |
| CDSE full SLC download | PARTIAL |
| HyP3 existing pair processing | PASS |
| NASA GPM IMERG | BLOCKED by HTTP 401 |
| Official land-cover source | NOT TESTED; no local product |
| Sentinel-2 | BLOCKED; no valid Tirumala band set |
| Gemini | PASS/LIVE |
| Telegram/SMTP | NOT TESTED |

## 8. Implementation Plan

### Checkpoint 2: Environmental data integration

Implement a data registry and explicit source/acquisition/provenance model.
Start with existing rainfall, DEM, slope, inventory and InSAR tables.
Do not create or infer missing raster data.

### Checkpoint 3: Common spatial integration

Create a reusable EPSG:32644 80 m alignment validator. Add missing-data and
quality metadata. Reuse existing rasters before downloading or transforming
any external data.

### Checkpoint 4: Multi-factor risk module

Create a separate experimental evidence index with:

- Slope.
- DEM/terrain.
- Rainfall 3/7/14-day context.
- GSI proximity.
- Valid InSAR LOS/coherence.
- Temporal availability.
- U-Net only if a valid georeferenced or explicitly screened input exists.

No category will be forced when essential evidence is missing.

### Checkpoint 5: Explainability

Store factor availability, factor contribution, previous/current observation,
missing evidence and a generated textual explanation for each spatial cell.

### Checkpoint 6: Streamlit and Cesium

Add source-backed environmental metrics and insufficient-data regions.
Reuse existing terrain, historical, InSAR and risk layers. Add no synthetic
rainfall, land-cover or U-Net map layer.

### Checkpoint 7: Gemini grounding

Add database-backed factor availability and risk explanation context while
keeping SQL execution disabled.

### Checkpoint 8: Scheduler integration

Reuse the Stage 5 jobs. Add only validated data checks and export status.
Do not add paid HyP3 submission or silently fabricate alternative data.

### Checkpoint 9: Tests and report

Add unit/integration tests for:

- CRS and alignment.
- Missing data and NoData.
- Rainfall complete calendar windows.
- Inventory coordinate validity.
- Risk factor normalization.
- Explanation grounding.
- Database preservation.
- Cesium and dashboard status.

## 9. Current Baseline Test Result

Before Stage 6 implementation:

- 100 tests passed.
- 6 subtests passed.
- 6 warnings.

## 10. Checkpoint 1 Status

| Area | Status |
|---|---|
| Workspace inspection | PASS |
| Database backup | PASS |
| Existing formula audit | PASS |
| DEM/slope/aspect audit | PASS |
| Rainfall audit | PARTIAL |
| GSI inventory audit | PASS |
| InSAR audit | PASS |
| U-Net audit | PARTIAL |
| Sentinel-2 audit | BLOCKED |
| Land-cover audit | BLOCKED |
| Gemini live availability | PASS |
| Scheduler inspection | PASS |
| Existing functionality preservation | PASS |

No implementation code was changed in Checkpoint 1.
