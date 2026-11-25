# Stage 6 Checkpoint 4: Data Quality and Risk Feature Engineering Report

**Assessment date:** 22 November 2026

## 1. Executive Summary

Checkpoint 4 investigated rainfall rollups, defined factor specifications,
implemented quality/eligibility states, and prepared a separate experimental
feature framework. It did not activate a new risk formula or change existing
risk weights or records.

Main result:

- 29 rainfall records are retained.
- Independent calendar rollups are documented.
- Existing stored rollups disagree and 27 records are marked as requiring
  reconciliation in the database validation table.
- Only complete and reconciled rainfall windows will be eligible for future
  experimental feature use.
- The existing risk formula and weights remain unchanged.
- One factor run was registered as specification-only.

## 2. Workspace and Backup

Active workspace:

`C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin`

Checkpoint 4 database backup:

`database/backups/monitoring_stage6_checkpoint4_20261122T142952Z.db`

Existing Stage 1-5 implementation and the 7590 live/temporal observations
remain preserved.

## 3. Previous Checkpoint Preservation

Verified unchanged:

- Existing pair `PAIR_20261109_20261121`.
- HyP3 job `3889d809-88a3-4a93-89a5-258821932737`.
- 7590 live observation snapshots.
- 7590 temporal InSAR observations.
- Historical pair records.
- LOS/coherence rasters.
- Existing risk formula and weights.
- Stage 5 monitoring functionality.

## 4. Rainfall Discrepancy Investigation

The independent definition used target date D and the preceding calendar
dates:

- 3-day: D, D-1, D-2.
- 7-day: D through D-6.
- 14-day: D through D-13.

A window is complete only when every required daily value exists and is finite.
Missing values remain missing.

Examples:

| Date | Window | Independent recalculation | Existing database | Status |
|---|---|---:|---:|---|
| 2026-08-03 | 3-day | 14.80 mm | 9.60 mm | Reconciliation required |
| 2026-08-07 | 3-day | 9.10 mm | 2.40 mm | Reconciliation required |
| 2026-08-07 | 7-day | 24.50 mm | 5.60 mm | Reconciliation required |

Independent full-window examples:

- 2026-08-03: 3-day 14.80 mm.
- 2026-08-07: 3-day 9.10 mm; 7-day 24.50 mm.
- 2026-08-29: 3-day 0.20 mm; 7-day 9.30 mm; 14-day 11.50 mm.

Source of discrepancy:

- The exact source calculation method used to create the stored database
  rollups is not traceable to sufficient source metadata.
- The existing CSV feature values and database values disagree for multiple
  windows.
- The values do not differ only from missing-window edge handling.
- Therefore the affected rollups are not considered reconciled.

No historical rainfall record was overwritten.

## 5. Rainfall Eligibility

Rainfall is excluded from experimental feature use until:

- The daily source is complete for the entire window.
- Stored and independently recalculated values match within the documented
  tolerance.
- The window provenance is traceable.
- The result is not an edge window with missing required dates.

Rainfall remains a study-area temporal feature, not a 69 x 110 rainfall raster.

## 6. Environmental Factor Definitions

### DEM elevation

- Unit: metres.
- Grain: spatial cell.
- NoData: 0.0 is screened as invalid in the existing processing convention.
- Interpretation: terrain descriptor only.

### Slope

- Unit: degrees.
- Grain: spatial cell.
- NoData: 0.0 is screened where appropriate.
- Normalization proposal: study-area percentile, not a calibrated threshold.

### Aspect

- Unit: degrees and sine/cosine circular components.
- Value -1 is undefined, not an eastward direction.
- Linear 0-360 normalization is not used.

### InSAR LOS

- Unit: metres relative LOS.
- Pair: `PAIR_20261109_20261121`.
- Coherence threshold used for quality eligibility is explicit.
- Missing/low-quality values remain missing.
- No vertical conversion, velocity or cumulative displacement.

### Coherence

- Unit: 0-1.
- Low coherence remains insufficient quality, not zero displacement.

### GSI inventory proximity

- Unit: kilometres to nearest mapped inventory point.
- Coordinates remain map-derived approximate.
- Proximity is exploratory only.

### U-Net benchmark

- 3799 image and 3799 mask H5 patches.
- No georeferenced Tirumala input.
- No local prediction or validation.
- Local availability: blocked.

### Sentinel-2 and land cover

- No local Sentinel-2 raster.
- No local land-cover raster.
- Both remain unavailable and are not placeholder features.

## 7. Missing-Data and Quality Framework

Defined states:

- `AVAILABLE`
- `AVAILABLE_WITH_LIMITATION`
- `INSUFFICIENT_QUALITY`
- `MISSING`
- `NOT_APPLICABLE`
- `REQUIRES_RECONCILIATION`
- `BLOCKED`

For each feature, the framework distinguishes:

- Value.
- Existence.
- Scientific usability.
- Quality validation.
- Provenance.

Missing values are never converted to zero by default.

## 8. Experimental Risk Feature Specification

The following feature definitions are separate from the production risk formula:

- DEM elevation.
- Slope.
- Aspect sine/cosine.
- Relative LOS displacement.
- InSAR coherence.
- Reconciled rainfall 3-day.
- Reconciled rainfall 7-day.
- Reconciled rainfall 14-day.
- GSI proximity.
- U-Net benchmark metadata only.

No experimental feature values or combined score are activated.

## 9. Normalization Assumptions

Proposed but not activated:

- Elevation: reported range or optional percentile.
- Slope: optional study-area percentile.
- Aspect: sine/cosine circular variables.
- LOS: optional absolute-range normalization, clearly marked exploratory.
- Coherence: direct 0-1 quality variable.
- Rainfall: raw mm only after reconciliation.
- GSI proximity: exploratory nearest-point distance.

Any threshold or normalization remains an assumption until supporting project
evidence or independent validation is available.

## 10. Explainability Design

A future assessment should be able to report:

- Available factors.
- Missing factors.
- Insufficient-quality factors.
- Factor contributions.
- Reconciled versus stored rainfall evidence.
- GSI provenance.
- InSAR reference limitation.
- U-Net unavailable state.
- Previous/current observation context.
- Whether a change is due to data, quality or measured evidence.

This is a proposed schema, not a generated explanation or model prediction.

## 11. Database Implementation

Checkpoint 4 added:

- `environmental_feature_definitions`
- `experimental_feature_runs`
- `experimental_feature_values`

It registered 10 feature specifications.

One specification-only experimental run was registered:

- Run status: `SPECIFICATION_ONLY`
- Result status: `NO_REAL_RISK_SCORE_ACTIVATED`
- `synthetic_values_written`: false
- Existing risk formula unchanged.

Existing observations and risk history were not modified.

## 12. Risk Formula Preservation

Existing weights are unchanged:

- Slope: 0.40
- Terrain: 0.25
- InSAR: 0.20
- Temporal: 0.15

No new factor weight or combined risk score was activated.

## 13. Testing

Focused Checkpoint 4 tests:

- 42 passed.

Full suite:

- 113 passed.
- 6 subtests passed.
- 6 warnings.

Tests covered:

- 3-, 7- and 14-day rolling design.
- Missing and incomplete windows.
- Aspect -1 undefined handling.
- Circular aspect components.
- LOS missing-value handling.
- U-Net unavailable state.
- Existing risk weight preservation.
- Synthetic feature framework behavior.

## 14. Dashboard and Cesium

No new risk visualization was activated.

Existing dashboard and Cesium data remain available, with:

- Data-quality limitation language.
- Rainfall reconciliation status.
- InSAR reference limitation.
- GSI provenance limitation.
- U-Net unavailable state.

## 15. Component Status

| Component | Status |
|---|---|
| Rainfall discrepancy investigation | PARTIAL |
| Independent 3/7/14-day calculation | PASS |
| Reconciliation eligibility | PARTIAL |
| Factor definitions | PASS |
| Missing-data framework | PASS |
| Quality-state framework | PASS |
| Aspect circular handling | PASS |
| InSAR feature limitations | PASS |
| GSI explanatory provenance | PASS |
| U-Net benchmark-only status | PASS |
| Experimental feature DB | PASS |
| Existing risk formula preservation | PASS |
| New risk activation | NOT TESTED / intentionally not activated |
| Dashboard/Cesium risk visualization | NOT CHANGED |
| Full test suite | PASS |

## 16. Remaining Blockers

- Rainfall 27 of 29 complete-window rows need reconciliation.
- GES DISC and fresh rainfall remain unresolved.
- Sentinel-2 and land-cover rasters are unavailable.
- Tirumala U-Net local ground truth is unavailable.
- InSAR pair-specific phase references are not established as common.
- Real deformation trend/velocity remains unavailable.

## 17. Recommendation for Checkpoint 5

Checkpoint 5 should not activate a new risk formula until:

1. Rainfall discrepancy provenance is resolved or affected windows remain
   explicitly excluded.
2. GSI and InSAR limitation rules are accepted.
3. U-Net remains benchmark-only.
4. A separate experimental feature run has documented quality coverage.

Checkpoint 4 is complete; no production risk formula or risk value was changed.
