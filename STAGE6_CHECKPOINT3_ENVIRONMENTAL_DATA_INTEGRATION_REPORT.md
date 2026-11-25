# Stage 6 Checkpoint 3: Environmental Data Integration Report

**Assessment date:** 22 November 2026

## 1. Outcome

Status: **PASS WITH DATA QUALITY LIMITATION**

Checkpoint 3 integrated existing audited environmental datasets into separate
SQLite registry and spatial-factor tables. It did not change the existing
risk formula, historical observations, pair records or InSAR values.

## 2. Database Backup

- `database/backups/monitoring_stage6_checkpoint3_20261122T141700Z.db`

The database was not recreated or reset.

## 3. Integrated Datasets

Eight environmental dataset records were registered:

| Dataset key | Source | Quality/status |
|---|---|---|
| dem | Local Copernicus-derived raster | READY |
| slope | DEM-derived raster | READY |
| aspect | DEM-derived raster | READY |
| rainfall | Existing GPM IMERG V07C-derived records | REQUIRES_ROLLUP_RECONCILIATION |
| gsi_inventory | GSI Figure 3.2 | READY WITH PROVENANCE LIMITATION |
| insar_los | ASF HyP3 GAMMA | VALID WITH REFERENCE LIMITATION |
| insar_coherence | ASF HyP3 GAMMA | VALID |
| unet_benchmark | Landslide4Sense H5 benchmark | SOFTWARE READY / LOCAL VALIDATION BLOCKED |

## 4. Spatial Alignment

All available common rasters align to:

- CRS: EPSG:32644
- Shape: 69 x 110
- Resolution: 80 x 80 m
- Bounds: 319720,1508840 to 328520,1514360

The DEM, slope, aspect, LOS and coherence rasters use the same grid and
transform. No resampling or value replacement was applied.

Missing-data percentages:

- DEM: 46.206%
- Slope: 51.357%
- Aspect: 46.206%
- LOS: 4.611%
- Coherence: 4.545%

## 5. Spatial Factor Availability

A new `spatial_factor_availability` table contains 7590 rows for
observation date `2026-11-21`.

Each row states availability independently for:

- DEM
- Slope
- Aspect
- Rainfall
- GSI
- InSAR LOS
- InSAR coherence
- U-Net

The U-Net availability flag is 0 because no georeferenced Tirumala U-Net
input exists.

Rainfall remains study-area aggregate information and is not marked as a
pixel-specific rainfall raster.

## 6. Rainfall Reconciliation

The 29-date daily rainfall CSV was recalculated independently into complete
calendar windows.

The result:

- 29 validation rows created.
- 27 dates are marked `REQUIRES_RECONCILIATION`.
- 2 incomplete-window edge dates remain matched or incomplete without a
  comparison.

Independent recalculation disagrees with stored database rollups. For example:

- 3 August 2026:
  - Recalculated 3-day: 14.80 mm
  - Stored database 3-day: 9.60 mm
- 7 August 2026:
  - Recalculated 3-day: 9.10 mm
  - Stored database 3-day: 2.40 mm
  - Recalculated 7-day: 24.50 mm
  - Stored database 7-day: 5.60 mm

No stored rainfall record was changed. The discrepancy is preserved in
`rainfall_rollup_validation` and the rainfall dataset registry is marked
`REQUIRES_ROLLUP_RECONCILIATION`.

## 7. GSI Integration

All 15 GSI inventory locations were mapped to 69 x 110 grid cell IDs.

- 15/15 records mapped.
- Every coordinate remains labelled `map-derived approximate`.
- Original latitude and longitude remain unchanged.
- Each mapping records exploratory cell proximity.

The GSI points are supporting historical context, not surveyed ground truth.

## 8. InSAR Integration

Existing pair `PAIR_20261109_20261121` remains:

- Processing status: `PROCESSED`
- LOS and coherence paths unchanged.
- Relative LOS interpretation unchanged.
- 7240 valid LOS cells.
- 7245 valid coherence cells.
- No LOS-to-vertical conversion.
- No cumulative displacement or velocity.

## 9. U-Net Metadata

Registered benchmark metadata:

- 3799 image H5 files.
- 3799 mask H5 files.
- Image shape: `(128, 128, 14)`.
- Mask shape: `(128, 128)`.
- HWC source and CHW inference layout.
- Binary masks.
- Model checkpoint path registered.
- Tirumala georeferenced prediction availability: false.

No Tirumala U-Net prediction was generated.

## 10. Database Changes

New tables:

- `environmental_dataset_registry`
- `spatial_factor_availability`
- `rainfall_rollup_validation`
- `gsi_spatial_mapping`

Existing tables preserved:

- `acquisitions`
- `insar_pairs`
- `rainfall_records`
- `spatial_evidence_grid`
- `observation_snapshots`
- `risk_history`
- `temporal_insar_observations`
- Stage 1-5 monitoring tables

Existing risk formula weights are unchanged.

## 11. Testing

Focused Checkpoint 3 tests:

- 31 passed.

Full suite:

- 106 passed.
- 6 subtests passed.
- 6 warnings.

Tests verify:

- Real raster alignment.
- CRS and shape.
- Rainfall independent rollup and discrepancy handling.
- GSI coordinate provenance.
- U-Net H5 dimensions.
- Database migration and existing risk weights.

## 12. Component Status

| Component | Status |
|---|---|
| Raster alignment | PASS |
| DEM/slope/aspect registry | PASS |
| GSI mapping | PASS |
| InSAR factor mapping | PASS |
| U-Net metadata registry | PASS |
| Rainfall reconciliation | PARTIAL |
| Risk formula | NOT CHANGED |
| Spatial factor registry | PASS |
| Sentinel-2 | BLOCKED |
| Land cover | BLOCKED |
| New GES DISC rainfall | BLOCKED |
| Local U-Net prediction | NOT TESTED |
| Existing record preservation | PASS |

## 13. Recommendation for Checkpoint 4

Checkpoint 4 should not implement a new risk formula yet.

Before risk implementation:

1. Reconcile or explicitly document rainfall rollup provenance.
2. Decide whether 3/7/14-day fields must come only from daily records.
3. Keep rainfall marked unavailable for per-cell risk calculations.
4. Validate GSI point proximity assumptions.
5. Preserve InSAR reference and coherence limitations.
6. Do not register Sentinel-2 or land-cover data until real local rasters exist.

Stage 6 Checkpoint 3 is complete. Checkpoint 4 has not started.
