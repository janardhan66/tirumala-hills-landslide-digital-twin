# Backend Integration Report

**Assessment date:** 22 November 2026

## 1. Scope

This sprint implemented backend, database and risk integration only.

No files under Streamlit dashboard, Cesium HTML/JavaScript/CSS, GLB, texture or
layer-manifest surfaces were edited.

## 2. Inspection

Inspected:

- Master Phase 1-6 reports.
- Existing SQLite tables and migrations.
- `src/risk_assessment.py`.
- Environmental registry and feature definitions.
- InSAR pair and temporal observation tables.
- Existing alert engine.
- Acquisition and pipeline history.
- Existing raster paths and alignment.

## 3. Backup

Before backend implementation:

`database/backups/monitoring_backend_integration_20261122T171753Z.db`

No database migration or historical record deletion was performed.

## 4. Existing Formula Preserved

The existing empirical formula remains:

- Slope 40%.
- Terrain 25%.
- InSAR 20%.
- Temporal 15%.

The formula is not calibrated and remains a relative evidence index.

## 5. Explainable Risk Backend

Added:

- `src/backend_integration.py`
- `build_risk_explanation()`
- `explain_risk_row()` integration

The backend exposes:

- Available factors.
- Unavailable factors.
- Evidence coverage.
- Category reason.
- Quality limitations.
- Missing-factor exclusion.

Missing data is not treated as zero.

## 6. Acquisition and Processing History

`get_acquisition_history()` exposes actual Sentinel-1 catalog and download state.

`get_pair_history()` exposes:

- Reference and secondary dates.
- Baseline.
- Orbit metadata.
- Processing status.
- Quality status.
- HyP3 job and status fields.
- Relative LOS raster paths.
- Coherence raster paths.

Live pair:

- `PAIR_20261109_20261121`
- HyP3 job:
  `3889d809-88a3-4a93-89a5-258821932737`

## 7. Data Freshness

Unified backend status includes:

- Latest Sentinel-1 acquisition date.
- Latest rainfall date.
- Latest processed InSAR date.
- Latest discovery event.
- Latest pipeline run.

No fake freshness or live completion state is generated.

## 8. Alerts

The backend uses:

- Existing database alert records.
- Existing observation snapshots.
- Existing empirical risk fields.
- Existing rainfall rollup reconciliation status.
- Existing alert rules.

Rainfall is passed to alerts only when the latest daily rollup status is
`MATCHED`. Otherwise the rainfall state is unavailable or requires
reconciliation.

External Telegram/SMTP delivery remains:

`NOT_TESTED_EXTERNAL_DELIVERY`

## 9. Raster Validation

Backend raster validation checks:

- DEM.
- Slope.
- Aspect.
- Live LOS.
- Live coherence.
- CRS.
- Shape.
- Resolution.
- Bounds.
- NoData.
- Valid/missing counts.
- Alignment.

The validation result passed and source rasters remain unchanged.

## 10. Backend JSON Interface

Added:

`scripts/export_backend_integration_status.py`

Generated JSON:

`outputs/backend/backend_integration_status.json`

The contract is:

`BACKEND_INTEGRATION_CONTRACT.md`

No HTTP API was present in the project, so no new unsupported HTTP endpoint
was invented.

## 11. Focused Test Results

Backend-focused pytest run:

- 18 passed.
- 8 warnings.
- 0 failed.

Coverage included:

- Formula preservation.
- Missing-factor exclusion.
- Database history readability.
- Risk calibration status.
- Alert database usage.
- Raster alignment and NoData.
- Database immutability.
- Strict JSON export.

## 12. Completed

- Database backup.
- Backend risk explanation.
- Environmental factor registry exposure.
- Acquisition and pair history.
- Data freshness.
- Actual database alert payload.
- Raster validation.
- Backend JSON export.
- Integration contract.
- Focused tests.

## 13. Partial

- Live acquisition discovery: waiting for genuine new data.
- Rainfall rollups: reconciliation required.
- External notification delivery: not verified.
- Local U-Net Tirumala validation: unavailable.

## 14. Blocked

- New HyP3 submission.
- Real cumulative LOS displacement.
- Real velocity.
- GES DISC 401 rainfall access.
- Calibrated landslide probability.
- Vertical displacement conversion.
- Sentinel-2/land-cover per-cell evidence.

## 15. Scientific Boundary

The backend exposes empirical evidence only. It does not claim calibrated
probability, confirmed landslide warning, vertical displacement, cumulative
LOS displacement or real velocity.
