# Master Phase 6 – InSAR and Temporal Change Analysis Report

**Assessment date:** 22 November 2026

## 1. Phase Objective

Status: **NOT_RELIABLE_WITH_SINGLE_PAIR**

Master Phase 6 implemented and validated the scientific InSAR audit,
raster-quality, temporal-network, and inversion guard framework. It used the
existing verified live pair and did not create a synthetic interferogram,
cumulative displacement map or velocity estimate.

Real cumulative displacement and velocity are not reliable with the available
quality-valid temporal network.

## 2. Existing Data Audit

Read-only database audit found:

- 20 Sentinel-1 acquisition records.
- 3 InSAR pair records.
- Existing pair `PAIR_20261109_20261121`.
- Existing HyP3 job `3889d809-88a3-4a93-89a5-258821932737`.
- 45554 observation snapshot rows.
- 7590 temporal InSAR observations.
- 7590 spatial evidence-grid records.
- 29 rainfall records preserved.

The live pair references:

- Reference acquisition:
  `220f79ba-248d-4e02-81ad-1f9f10d202ed`
- Secondary acquisition:
  `b69aeace-3306-4e9b-94f3-a6d643296386`
- Reference date: 2026-11-09.
- Secondary date: 2026-11-21.
- Temporal baseline: 12 days.
- Relative orbit: 92.
- Orbit direction: DESCENDING.
- Processing method: ASF HyP3 GAMMA.

No new HyP3 job was submitted.

## 3. Database Backup

Created before additive migration:

`database/backups/monitoring_master_phase6_20261122T161914Z.db`

No existing scientific table or record was deleted or overwritten.

## 4. Processing Tools and Versions

- Python: 3.13.0.
- Rasterio: 1.5.2.
- NumPy: 2.3.3.
- SciPy: 1.16.2.
- PyProj: 3.8.0.
- pandas: 2.3.3.
- hyp3_sdk: 7.7.8.
- GDAL executable: not found.
- SNAP executable: not found.
- ISCE2 executable: not found.
- ISCE3 executable: not found.
- Snappy executable: not found.

Status: **PASS WITH LIMITATIONS**

The existing HyP3 product remains the only processed local data source.
No local tool was used to claim interferogram regeneration.

## 5. Pair Compatibility

The existing live pair is preserved and marked:

- Processing status: PROCESSED.
- Quality status: VALID.
- Orbit compatibility: VERIFIED.
- Spatial overlap: 100%.
- Relative orbit: 92.
- Direction: DESCENDING.
- Baseline: 12 days.

No additional pair was selected or submitted.

## 6. Interferogram Processing Status

Status: **PASS WITH LIMITATIONS**

An interferogram product already exists from the successful HyP3 job. Phase 6
did not regenerate phase unwrapping or interferogram formation. Processing
parameters, source pair IDs and software metadata remain traceable through the
existing pair record.

Phase unwrapping quality and atmospheric contamination remain documented
scientific limitations.

## 7. Coherence Quality

Live aligned coherence raster:

- CRS: EPSG:32644.
- Shape: 69 × 110.
- Resolution: 80 m.
- Bounds:
  319720, 1508840 to 328520, 1514360.
- Valid finite cells: 7245.
- Range: 0.0241987966 to 0.9613294601.
- Mean: 0.5894369260.
- NoData convention: masked/NaN.

The project coherence threshold is 0.50. This is a project quality rule, not a
universal physical boundary.

## 8. LOS Displacement Validation

Live aligned LOS raster:

- CRS: EPSG:32644.
- Shape: 69 × 110.
- Resolution: 80 m.
- Valid finite cells: 7240.
- Range: -0.1119190753 m to -0.0537146255 m.
- Mean: -0.0879678460 m.
- NoData convention: masked/NaN.

Quality-valid LOS/coherence intersection with coherence >= 0.50:

- 5034 cells.

The LOS measurement is relative line-of-sight displacement. It was not
converted to vertical displacement.

Low coherence and NoData were not converted to zero movement.

## 9. Raster Alignment

Both live rasters align to:

- CRS EPSG:32644.
- 69 × 110 grid.
- 80 m resolution.
- Common bounds.

Status: **PASS**

Existing source rasters were not replaced or resampled.

## 10. Temporal Network Structure

Recalculated from current database:

- Acquisition nodes: 5.
- All pair edges: 3.
- Quality-valid edges: 1.
- Connected components: 4.
- Component sizes: 1, 1, 1, 2.
- Matrix rank: 1.

Only `PAIR_20261109_20261121` is currently a quality-valid edge.

Status: **NOT_RELIABLE_WITH_SINGLE_PAIR**

## 11. Connected-Component Analysis

The live valid edge connects the 2026-11-09 and 2026-11-21 nodes.
The remaining acquisition nodes are disconnected from that edge.

No synthetic edge was added.

## 12. Matrix Rank and Inversion

The rank of the single valid-edge observation matrix is 1.

The current network cannot support cumulative displacement or velocity
inversion for all acquisition nodes.

Status: **NOT_RELIABLE_WITH_SINGLE_PAIR**

## 13. Cumulative Displacement Status

Status: **NOT_RELIABLE_WITH_SINGLE_PAIR**

No cumulative LOS displacement map or numerical result was produced.

## 14. Velocity Status

Status: **NOT_RELIABLE_WITH_SINGLE_PAIR**

No real velocity was produced.

## 15. Uncertainty and Residual Analysis

Residual error: unavailable.

Uncertainty: unavailable.

A single relative pair cannot establish a temporal trend, and pair-specific
phase-reference alignment has not been established.

## 16. Database Changes

Additive tables created:

- `insar_processing_runs`
- `insar_raster_validation`
- `insar_temporal_network`
- `insar_inversion_runs`

The migration preserves existing pair and observation records.

Phase 6 exports populated versioned audit records:

- 4 processing runs.
- 8 raster-validation records.
- 1 temporal-network record.
- 1 blocked inversion record.

No real or synthetic displacement value was inserted into the temporal
observation table.

## 17. Dashboard Integration

The monitoring tab now displays:

- Phase 6 status.
- Quality-valid LOS cell count.
- Valid temporal edge count.
- Connected components.
- Cumulative displacement status.
- Velocity status.
- A warning that no synthetic deformation is shown.

## 18. Cesium Integration

Created:

`viewer/cesium/data/master_phase6_status.json`

It contains:

- Live pair metadata.
- LOS and coherence statistics.
- Network status.
- Matrix rank.
- Inversion/blocker status.
- Processing tool metadata.
- Zero new HyP3 jobs and zero credits consumed.

No existing terrain GLB, DEM, slope, aspect, LOS texture, coherence texture or
GSI layer was replaced.

## 19. Focused Test Results

Phase 6 and Phase 5 focused tests:

- 17 passed.

Coverage includes:

- Raster CRS/grid/NoData handling.
- Synthetic network connected/disconnected cases.
- Single-pair guard.
- Rank-deficient matrix guard.
- Additive database migration.
- Live status export.
- JSON no-NaN validation.

## 20. Full-Suite Test Results

Status: **PASS**

Final pytest full-suite run:

- 137 passed.
- 6 subtests passed.
- 6 warnings.
- 0 failed.

The warnings are existing test-return and datetime deprecation warnings.

## 21. Live-Data versus Synthetic-Test Distinction

The 5034 quality-valid cells, raster statistics and network counts are derived
from real existing Tirumala rasters and database records.

The synthetic tests exercise software behavior only. They insert no
synthetic observations into the real database and produce no displayed
Tirumala deformation.

## 22. Scientific Limitations

- Phase reference is not established as a common spatial reference across
  pairs.
- One quality-valid edge cannot define a multi-temporal time series.
- Atmospheric contamination and unwrapping quality remain unknown limitations.
- LOS is not vertical displacement.
- Negative or positive LOS values alone do not identify a landslide.
- A vertical/descending and ascending decomposition is not available.
- Residual error and uncertainty cannot be reliably estimated for this network.

## 23. Remaining Blockers

- No additional quality-valid interferogram edge.
- Pair-specific reference alignment required.
- No local SNAP/ISCE/GDAL InSAR processor installed.
- No new compatible acquisition downloaded.
- No explicit approval for a new HyP3 job.
- No defensible real cumulative displacement or velocity.

## 24. Phase 7 Readiness

Status: **NOT_RELIABLE_WITH_SINGLE_PAIR**

Phase 6 is complete as a scientific framework and single-pair limitation
assessment. Phase 7 AI/ML risk assessment was not started.

Real temporal inversion readiness requires a sufficiently connected network,
consistently referenced phase measurements and additional validated
observations.
