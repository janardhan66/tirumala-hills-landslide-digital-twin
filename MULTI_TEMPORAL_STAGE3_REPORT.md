# Stage 3: Multi-Temporal InSAR Time-Series Framework Report

**Assessment date:** 22 November 2026

## 1. Outcome

Stage 3 implemented a guarded multi-temporal InSAR framework. It does not
claim or generate a real deformation time series or velocity because the
verified SBAS network is insufficient.

The only traceable Stage 3 real observation is
`PAIR_20261109_20261121`. Historical pair rows exist, but they are not marked
quality-validated for a new SBAS inversion.

## 2. Existing Data Inspection

Existing real pair:

- Pair: `PAIR_20261109_20261121`
- Reference date: 2026-11-09
- Secondary date: 2026-11-21
- Baseline: 12 days
- LOS source:
  `data/processed/dinsar/tirumala/gsi_aoi/PAIR_20261109_20261121/tirumala_live_los_disp_80m.tif`
- Coherence source:
  `data/processed/dinsar/tirumala/gsi_aoi/PAIR_20261109_20261121/tirumala_live_coherence_80m.tif`
- CRS: EPSG:32644
- Grid: 69 x 110
- Pixel size: 80 x 80 m
- LOS unit: metres
- Coherence range: 0 to 1
- Valid aligned LOS cells: 7240
- Quality-valid LOS/coherence cells: 5034
- Reference convention: relative to the automatic pair phase reference

No missing raster value was converted to zero.

## 3. Temporal Observation Storage

New table:

- `temporal_insar_observations`

Each row records:

- `cell_id`
- `pair_id`
- Reference date
- Secondary date
- Acquisition date
- LOS displacement metres
- Coherence
- Quality status
- NoData status
- Source raster
- Processing metadata

The real migration populated 7590 rows for the 21 November 2026 secondary
date. 5034 rows are valid and 2556 are insufficient or NoData.

Existing 7590 `observation_snapshots` rows remain separate and unchanged.

## 4. Interferogram Network

The network module represents acquisition dates as nodes and processed
interferograms as edges. The Stage 3 export identifies:

- 5 nodes
- 3 pair edges
- 1 quality-valid edge
- 4 connected components
- Component sizes: 1, 1, 1, 2

The pair-specific LOS values use separate phase references. No cross-pair
differential LOS series or cumulative displacement was calculated.

## 5. SBAS-Style Inversion

The mathematical module constructs:

```text
A * x = d
```

where:

- `A` contains reference-minus-secondary incidence rows.
- `d` contains valid per-edge LOS increments.
- `x` contains cumulative relative LOS values at acquisition dates.
- Coherence supplies observation weights.

The implementation:

- Uses weighted least squares.
- Checks matrix rank.
- Checks independent valid-edge count.
- Detects disconnected/underdetermined networks.
- Returns `INSUFFICIENT_DATA` for one pair.
- Never infers a velocity from one pair.

Synthetic tests recovered a 10 mm per 90-day linear signal and 40 mm/year
correctly. Synthetic results are test fixtures only and are not in the SQLite
real-observation table or Cesium.

## 6. Velocity Estimation

LOS velocity was not generated from real data. Stage 3 explicitly reports:

- Velocity status: `NOT_RELIABLE_WITH_SINGLE_PAIR`
- Unit for future values: mm/year
- Velocity is relative LOS, not vertical velocity
- A reliable trend requires multiple genuine, quality-valid interferograms

## 7. Spatial and Risk Interpretation

The framework distinguishes:

- Stable LOS evidence
- Increasing LOS evidence
- Decreasing LOS evidence
- Inconsistent observations
- Insufficient-quality observations

No such classification is reported as a confirmed landslide. The existing
empirical risk formula remains unchanged. Temporal features are not used to
replace or double-count the existing InSAR evidence until enough real
observations exist.

## 8. Cesium and Dashboard Status

Stage 3 exports:

- `viewer/cesium/data/stage3_temporal_status.json`

The status explicitly reports:

- One valid real edge
- Insufficient-data time-series status
- Not-reliable-single-pair velocity status
- Reference-point LOS convention
- Valid/insufficient observation counts

Existing terrain models, historical pair models, textures and timeline remain
unchanged. The monitoring tab now displays an insufficient-data warning.

## 9. Scientific Limitations

- LOS is a projection and not full 3D displacement.
- Vertical displacement requires geometric assumptions.
- Each pair is relative to its own phase reference.
- No common reference adjustment is established across pairs.
- Atmospheric delay may contaminate phase.
- Phase unwrapping can contain errors.
- Low coherence and temporal decorrelation reduce reliability.
- One interferogram cannot support cumulative displacement or velocity.
- Multiple independent, compatible genuine pairs are required for SBAS inversion.

## 10. Testing

Full test suite:

- 96 passed
- 6 subtests passed
- 6 warnings

Stage 3/temporal tests:

- 23 passed

Tests cover:

- Single-pair insufficient status
- Synthetic two-edge inversion
- Missing observations
- Low-coherence exclusion
- Temporal network components
- Unit recovery
- Existing temporal registry behavior

## 11. Component Status

| Component | Status |
|---|---|
| Existing data inspection | PASS |
| Temporal observation table | PASS |
| Traceable per-pair observations | PASS |
| Duplicate prevention | PASS |
| Interferogram network | PASS |
| One-pair insufficient-data guard | PASS |
| Weighted SBAS module | PASS for synthetic math |
| Real SBAS displacement | NOT TESTED |
| Velocity estimation | NOT TESTED |
| Spatial trend categories | NOT TESTED |
| Risk temporal integration | NOT TESTED |
| Cesium stage 3 status | PASS |
| Dashboard insufficient-data warning | PASS |
| Real multi-date visualization | NOT TESTED |

## 12. Modified and Added Files

- `src/analysis/temporal_insar.py`
- `src/analysis/__init__.py`
- `src/data/db.py`
- `database/schema.sql`
- `scripts/populate_stage3_temporal.py`
- `scripts/migrate_stage3_timeseries.py`
- `scripts/export_stage3_temporal.py`
- `dashboard/tabs_extension.py`
- `viewer/cesium/data/stage3_temporal_status.json`
- `tests/test_stage3_timeseries.py`

No HyP3 job was submitted in Stage 3.
