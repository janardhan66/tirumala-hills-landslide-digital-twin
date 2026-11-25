# Backend Integration Contract

**Workspace:** `C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin`

**Assessment date:** 22 November 2026

## 1. Scope

This contract describes backend/data interfaces only. No Streamlit, Cesium,
HTML, JavaScript, CSS, GLB, texture or layer-manifest file is modified by the
backend integration.

The project has no existing HTTP API implementation. Safe consumers may use:

- SQLite database: `database/monitoring.db`
- Python database manager: `src/data/db.py`
- Backend integration module: `src/backend_integration.py`
- Export script: `scripts/export_backend_integration_status.py`
- Generated backend JSON:
  `outputs/backend/backend_integration_status.json`

## 2. Database Tables

Existing relevant tables:

| Table | Purpose |
|---|---|
| `acquisitions` | Sentinel-1 acquisition history and download state |
| `insar_pairs` | Pair, processing and HyP3 state |
| `temporal_insar_observations` | Traceable pair observations |
| `rainfall_records` | 29 existing rainfall records |
| `rainfall_rollup_validation` | Rollup reconciliation status |
| `environmental_dataset_registry` | Audited environmental data sources |
| `spatial_factor_availability` | Per-cell factor availability |
| `environmental_feature_definitions` | Factor definitions and limitations |
| `gsi_spatial_mapping` | Approximate GSI coordinate mapping |
| `risk_history` | Existing aggregate empirical risk history |
| `observation_snapshots` | Existing empirical per-cell snapshots |
| `alerts` | Existing database-backed evidence alerts |
| `pipeline_logs` | Pipeline execution history |
| `monitoring_discovery_events` | Satellite discovery events |
| `hyp3_job_status_history` | Existing HyP3 status history |

No database schema migration was required.

## 3. Risk Interface

Python:

`build_risk_explanation(db, limit=None)`

Fields:

- `calibration_status`: always `NOT_CALIBRATED`
- `formula`: 0.40 slope, 0.25 terrain, 0.20 InSAR, 0.15 temporal
- `summary`: relative empirical score/category/count
- `distribution`: existing category distribution
- `rows[]`: one explanation object per requested row
- `limitations[]`: scientific limitations

Row fields:

- `risk_score`
- `risk_category`
- `evidence_coverage_percent`
- `factor_availability`
- `explanation`
- `disclaimer`

Missing factors are excluded from available weight, not converted to zero.

## 4. Acquisition Interface

Python:

`get_acquisition_history(db)`

Fields:

- `acquisition_id`
- `satellite`
- `product_type`
- `sensor_mode`
- `beam_mode`
- `orbit_direction`
- `relative_orbit`
- `acquisition_date`
- `acquisition_timestamp`
- `download_status`
- `processing_status`
- `file_path`
- `error_message`
- `updated_at`

## 5. Pair Interface

Python:

`get_pair_history(db)`

Fields:

- `pair_id`
- `reference_date`
- `secondary_date`
- `temporal_baseline_days`
- `relative_orbit`
- `orbit_direction`
- `processing_status`
- `quality_status`
- `valid_pixels`
- `mean_coherence`
- `los_disp_tif`
- `coherence_tif`
- `hyp3_job_id`
- `submitted_at`
- `last_status_check_at`
- `output_validation_status`
- `scientific_status`

Status definitions:

- `REAL_PAIR_WITH_PAIR_SPECIFIC_PHASE_REFERENCE`
- `HISTORICAL_PAIR_NOT_RECALCULATED`
- `NOT_RELIABLE_WITH_SINGLE_PAIR`

## 6. Raster Interface

Python:

`validate_rasters()`

Fields per dataset:

- `crs`
- `shape`
- `resolution`
- `bounds`
- `nodata`
- `valid_cells`
- `missing_cells`
- `source_unchanged`

No source raster is modified.

## 7. Alert Interface

Python:

`build_actual_alert_payload(db)`

Fields:

- `observation_date`
- `rainfall_status`
- `rainfall_3day_mm`
- `actual_database_alert_records`
- `evaluated_alerts`
- `delivery_status`

`evaluated_alerts[]` fields:

- `trigger_rule`
- `severity`
- `warning_level`
- `affected_cells_count`
- `observation_date`
- `data_quality`
- `summary`
- `recommended_action`
- `disclaimer`
- `indicators`

External delivery status is always `NOT_TESTED_EXTERNAL_DELIVERY`.

## 8. Unified Backend Export

Script:

`python scripts/export_backend_integration_status.py`

JSON:

`outputs/backend/backend_integration_status.json`

Top-level fields:

- `status`
- `calibration_status`
- `acquisitions`
- `pairs`
- `data_freshness`
- `risk`
- `raster_validation`
- `alerts`
- `environmental_datasets`
- `feature_definitions`
- `rainfall_rollup_validation`
- `risk_history`
- `database_counts`
- `blocked`

## 9. Status Definitions

- `BACKEND_INTEGRATED_WITH_LIMITATIONS`
- `NOT_CALIBRATED`
- `NOT_RELIABLE_WITH_SINGLE_PAIR`
- `MATCHED`
- `REQUIRES_RECONCILIATION`
- `NOT_TESTED_EXTERNAL_DELIVERY`
- `WAITING_FOR_NEW_DATA`

## 10. Missing or Blocked Fields

Frontend consumers must not infer:

- Cumulative LOS displacement.
- LOS velocity.
- Vertical displacement.
- Calibrated probability.
- A confirmed landslide warning.
- A newly downloaded Sentinel-1 pair.
- A successful new HyP3 job.
- A valid rainfall 3-day value when reconciliation status is not `MATCHED`.
- Telegram or SMTP delivery success.
- Local U-Net Tirumala accuracy.
