# Master Prompt - Phase 1 Audit and Implementation Plan

**Assessment date:** 22 November 2026

## 1. Audit Scope

The active workspace is:

`C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin`

Phase 1 is a preservation and audit phase. No download, preprocessing, InSAR
submission, database reset, risk-formula change or fabricated dataset was
performed.

## 2. Preserved Database Backup

Database backup created for this phase:

`database/backups/monitoring_master_phase1_20261122T150310Z.db`

## 3. Existing Database and Project State

| Item | Verified state |
|---|---|
| Sentinel-1 acquisitions | 20 catalog records |
| InSAR pairs | 3, including `PAIR_20261109_20261121` |
| Rainfall records | 29 historical daily records |
| Spatial grid records | 7590 |
| Observation snapshots | 45554 historical and live snapshot rows |
| Temporal InSAR observations | 7590 |
| Risk history | 11 records |
| Alerts | 33 records |
| Pipeline logs | 126 records |
| Latest existing risk summary | Low 5195, Medium 2177, High 218 |
| Latest existing observation date | 2026-11-21 |

The existing empirical risk summary is an evidence index, not calibrated
landslide probability.

## 4. Existing Application and Data

Working components:

- Streamlit dashboard on port 8501: HTTP 200.
- Local Cesium viewer on port 8088: HTTP 200.
- Canonical dashboard: `dashboard/app.py`.
- 69 x 110, 80 m DEM grid in EPSG:32644.
- DEM, slope and aspect rasters.
- Existing 2D GIS map and 3D terrain models.
- Existing GSI historical inventory.
- Existing 29-day rainfall records.
- Existing InSAR LOS/coherence rasters.
- Existing 3799 Landslide4Sense image/mask H5 pairs.
- Existing U-Net checkpoint:
  `landslide_unet_14channel_best.pth`.
- Existing Random Forest model files.
- Existing APScheduler and Windows Task Scheduler integration.

The U-Net is not georeferenced and no complete aligned Tirumala 14-channel
Sentinel-2 input is locally available. U-Net output is therefore not a
Tirumala-validated landslide prediction.

## 5. Existing Live Services

Verified:

- CDSE credentials configured.
- Earthdata credentials configured.
- Gemini credentials configured.
- Gemini live generation successful.
- HyP3 job
  `3889d809-88a3-4a93-89a5-258821932737`
  is `SUCCEEDED`.
- One real live pair:
  `PAIR_20261109_20261121`.
- Scheduler/processes are running locally.

Not fully verified:

- No valid full CDSE raw-SLC download is available for both new live scenes.
- GES DISC rainfall download returns HTTP 401.
- Telegram/SMTP delivery.
- A complete Sentinel-2 band set.
- Local land-cover data.
- Independent Tirumala U-Net validation.
- Repeated real automated monitoring cycles.
- Continuous 3D refresh after multiple new real observations.

## 6. Scientific Limitations

- InSAR LOS displacement is relative to pair-specific phase references.
- Direct pair subtraction is not established as cumulative displacement.
- One pair cannot establish a reliable deformation trend or velocity.
- Coherence below 0.50 is insufficient evidence, not zero movement.
- The rainfall records are study-area aggregate context, not pixel rainfall.
- The 29-date rainfall rollups contain unresolved source discrepancies.
- GSI points are approximate map-derived locations.
- Existing risk scores are relative evidence indices, not calibrated probability.
- Landslide4Sense U-Net performance is benchmark performance, not Tirumala
  ground-truth validation.

## 7. Baseline Test Result

Full current test suite:

- 113 passed.
- 6 subtests passed.
- 6 warnings.

The suite covers local fixtures, mocks and existing data. It does not prove
continuous live monitoring or real-time satellite integration.

## 8. Twelve-Phase Implementation Plan

### Phase 1 – Audit and preserve

Completed in this pass:

- Workspace/database/data/UI audit.
- Backup.
- Baseline test result.
- Documentation of scientific limitations.

### Phase 2 – Accurate 3D terrain

- Revalidate real DEM alignment and elevation bounds.
- Preserve existing GLB and textures.
- Replace no artificial terrain values.

### Phase 3 – GIS evidence in 3D

- Preserve elevation, slope, aspect, LOS, coherence and GSI layers.
- Add source/acquisition/quality metadata.
- Correct any stale layer registry fields.

### Phase 4 – Satellite and rainfall discovery

- Reuse Stage 1/5 CDSE discovery.
- Add bounded duplicate detection and discovery events.
- Keep downloads guarded and non-destructive.
- Diagnose GES DISC authorization before rainfall retry.
- Do not fabricate rainfall or satellite observations.

### Phase 5 – Download and preprocessing

- Complete resumable CDSE download.
- Validate ZIP size and internal archive integrity.
- Implement SAFE extraction and alignment.
- Mark partial downloads failed/quarantined.
- Preserve existing files.

### Phase 6 – Valid InSAR and temporal change

- Use existing pair manager and HyP3 integration.
- Require user approval for paid jobs.
- Poll pending jobs and preserve status history.
- Validate CRS, resolution, NoData and coherence.
- Build a time series only after multiple compatible, reference-consistent pairs.

### Phase 7 – AI/ML and risk assessment

- Preserve existing evidence formula and weights.
- Audit random forest training and feature definitions before reuse.
- Keep U-Net experimental and H5-only.
- Add explainability from real database factors.
- Do not activate probability claims.

### Phase 8 – Continuous monitoring and history

- Reuse single-owner APScheduler.
- Prevent overlapping jobs.
- Persist last success/failure and next execution.
- Preserve observation and alert history.
- Stop safely when credentials or data are unavailable.

### Phase 9 – Automatic 3D updates

- Export only changed textures/models/registry entries.
- Refresh Cesium without full reconstruction.
- Preserve existing pair/layer assets.
- Mark missing or stale observations explicitly.

### Phase 10 – Alerts and notifications

- Use documented threshold gates.
- Require human review.
- Preserve alert history and acknowledgment.
- Test Telegram/email only with configured credentials and explicit approval.

### Phase 11 – Dashboard integration

- Add database-backed data freshness.
- Add missing, stale and waiting states.
- Preserve existing six tabs.
- Add only real observation dates to the timeline.
- Keep risk scores explicitly empirical.

### Phase 12 – End-to-end tests

- Run offline regression suite.
- Add live-service tests separately and safely.
- Verify one repeated real satellite cycle before claiming continuous monitoring.
- Produce evidence logs for each phase.

## 9. Phase 1 Status

Phase 1: **PASS – audited and preserved**

Implementation has not yet started for later phases. The next phase is
accurate 3D terrain and layer validation, after the user approves beginning
Phase 2.
