# Phase 7 - Checkpoint 2: Spatial Feature and Ground-Truth Readiness

**Execution date:** 23 November 2026  
**Status:** PASS WITH LIMITATIONS  
**Decision:** NO - do not begin scientifically defensible Tirumala-specific Random Forest training with the currently available evidence.

## 1. Executive summary

The project has a canonical 69 x 110 Tirumala grid in EPSG:32644 with 80 m cells. The canonical DEM, slope, aspect, live November 2026 InSAR LOS/coherence, approximate GSI points and one November 2026 temporal-change raster are available and aligned to the 7,590-cell grid.

An experimental feature table was created outside production data stores. It contains one record for every grid cell and preserves missing measurements as missing values. Rainfall was not synthesized at cell level. Sentinel-2 bands and land-cover rasters were not available. No target label or model was created.

The evidence is insufficient for local supervised training: independent, georeferenced, temporally consistent positive and negative landslide labels are not established.

## 2. Backup and database integrity

- Backup: `database/backups/monitoring_phase7_checkpoint2_20261123T083701Z.db`
- SQLite integrity: `ok`
- Observation snapshots: 45,554
- Risk history: 2
- Alerts: 33
- Production database modified: No
- Existing production risk formula/weights modified: No
- Existing model artifacts modified: No
- Frontend/Cesium modified: No

## 3. Canonical spatial grid

- Dimensions: 69 rows x 110 columns = 7,590 cells
- CRS: EPSG:32644
- Resolution: 80 m
- Bounds: 319720, 1508840 to 328520, 1514360
- DEM valid cells: 4,083
- Slope valid cells: 3,692
- Aspect valid cells: 4,083
- November live InSAR LOS valid observations: 7,240
- November live coherence valid observations: 7,245
- November quality-valid LOS/coherence cells at coherence >= 0.50: 5,034

The DEM, slope, aspect and live LOS/coherence rasters use the same 110 x 69 shape, CRS, 80 m transform and bounds.

## 4. Raster and feature readiness

| Dataset | Source period | Alignment | Valid / missing | ML readiness |
|---|---|---|---:|---|
| DEM | Existing processed terrain | Canonical | 4,083 / 3,507 | Usable with missingness |
| Slope | Existing processed terrain | Canonical | 3,692 / 3,898 | Usable with missingness |
| Aspect | Existing processed terrain | Canonical | 4,083 / 3,507 | Usable with missingness |
| InSAR LOS | 2026-11-09 to 2026-11-21 | Canonical | 7,240 / 350 | Pair-specific LOS, not vertical displacement |
| InSAR coherence | 2026-11-09 to 2026-11-21 | Canonical | 7,245 / 345 | Coherence >= 0.50 quality rule |
| Temporal LOS change | 2026-08-05/17 to 2026-11-17/29 | Canonical | 2,569 / 5,021 | Separate pair-derived change, not cumulative velocity |

NoData and low-coherence observations are unavailable, not zero. LOS is line-of-sight displacement relative to its pair reference phase.

## 5. Experimental feature table

Created:

- `tirumala_experimental_feature_availability.csv`
- 7,590 records, one per grid cell
- 2609 cells have the four direct predictors plus GSI-distance status marked complete in the current availability definition
- 4981 records are partial
- Rainfall fields remain null for every cell
- GSI distance is Euclidean 2-D distance in EPSG:32644 to the nearest of 15 approximate map-derived GSI points

The GSI distance field is contextual proximity evidence, not landslide probability or ground truth.

## 6. Rainfall audit

Available files contain 29 or 13/19 dated study-area aggregate records, with values expressed in mm and `grid_cells` ranging from 1 to 4 in the files audited. This does not establish a pixel-level rainfall raster and the 29-record CSV is not reconcileable with a 7,590-cell grid.

The 2026-11-21 updated file contains only one record and no usable historical completeness. The 3/7/14-day rollups are computed temporal aggregates, not spatial rainfall fields.

Rainfall rollups were therefore marked unavailable for the experimental cell table.

## 7. Sentinel-2 and land-cover readiness

The project search log records Sentinel-2 product searches and download attempts, but no complete local Sentinel-2 band directory was found. The CDSE credentials were unavailable for recent downloads.

No complete, locally usable set of B01-B12 rasters or derived land-cover raster was identified. Sentinel-2 and land-cover predictors are unavailable; no optical values were fabricated.

## 8. U-Net readiness

- Landslide4Sense HDF5 images: 3,799
- HDF5 masks: 3,799
- Image shape: 128 x 128 x 14
- Mask shape: 128 x 128
- Existing extraction identifies channel 12 as slope and channel 13 as DEM/elevation
- The patches have no demonstrated reliable mapping to Tirumala cells
- The U-Net is benchmark-trained and locally unvalidated
- No Tirumala inference was performed

## 9. Landslide4Sense RF duplicate analysis

The v3 CSV remains unchanged with 190,644 rows. Its exact duplicate-row count is 12,388.

Duplicate analysis distinguishes:

- exact duplicate rows within identical patch IDs;
- exact rows present across patch IDs;
- slope/elevation combinations repeated across patches;
- slope/elevation combinations associated with conflicting labels.

These repeated combinations are not independent spatial observations. The full machine-readable details are in `rf_duplicate_analysis.json`. The patch-separated benchmark holdout is not sufficient to remove feature-combination overlap across patches, and no deletion or replacement was performed.

## 10. Ground-truth inventory

Existing positive-evidence sources:

- 15 GSI Figure 3.2 map-derived approximate point symbols
- COOLR-derived news reports for 2017 and 2013 Tirumala landslide events

Limitations:

- GSI symbols lack verified event dates, failure footprints, coordinate accuracy and field confirmation.
- COOLR coordinates are approximate and have location uncertainties of 1 km or 5 km.
- Historical events occurred before the available 2026 InSAR/rainfall period.
- No verified, temporally matched landslide boundaries or independent negative landslide/non-landslide labels were identified.
- Absence of a historical record does not prove a negative label.

The GSI and news records are contextual inventory evidence only. They do not support scientifically defensible cell-level positive or negative target labels.

## 11. Future spatial training data design

If sufficient independent evidence is later collected, the proposed unit should remain the canonical 80 m EPSG:32644 cell.

Required design:

- Positive labels: verified landslide polygons or point events buffered according to documented coordinate and footprint uncertainty, temporally matched to predictor observations.
- Negative labels: independently assessed stable areas, not points or areas selected simply because no incident was recorded.
- Predictor evidence: aligned DEM, slope, aspect, pair-specific InSAR quality/LOS, temporally appropriate rainfall rasters, optical indices if complete and land cover if quality-controlled.
- Missing data: preserve missing values and quality flags; do not zero-fill NoData or low-coherence pixels.
- Validation: spatially blocked or geographic-domain holdouts and an independent Tirumala test set.
- Temporal matching: require a common event/acquisition-reference convention before combining pairs or rainfall windows.
- Additional evidence: field survey/geotechnical inventory, precise polygons, event dates, stable-area verification and independent validation.

No target labels should be generated until this evidence is available.

## 12. Scientific limitations

- No independent Tirumala ground truth.
- No pixel-level rainfall predictor.
- No complete Sentinel-2 or land-cover predictor stack.
- InSAR is pair-specific and cannot be treated as cumulative displacement or velocity.
- GSI and historical news records are approximate.
- The existing benchmark RF remains external-benchmark-derived and locally unvalidated.
- Terrain validity and missingness are not representative of the full AOI.

## 13. Go/no-go recommendation

**GO/NO-GO: NO**

The available data can support a feature-readiness audit and future data collection, but it is not sufficient to begin scientifically defensible Tirumala-specific Random Forest training.

## 14. Files created

- `generate_checkpoint2.py`
- `PHASE7_CHECKPOINT2_SPATIAL_FEATURE_AND_GROUND_TRUTH_READINESS.md`
- `phase7_checkpoint2_status.json`
- `tirumala_experimental_feature_availability.csv`
- `feature_metadata.json`
- `ground_truth_inventory.csv`
- `rf_duplicate_analysis.json`

## 15. Test and verification results

- Python generator syntax compilation: passed
- Experimental CSV: 7,590 records; missing rainfall intentionally preserved
- JSON files: read successfully
- No model training performed
- Relevant Phase 7 tests: 23 passed, 8 warnings
- Full test suite: 150 passed, 12 warnings, 6 subtests passed
