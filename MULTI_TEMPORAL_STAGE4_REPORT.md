# Stage 4: Real Multi-Temporal InSAR Acquisition and Validation Report

**Assessment date:** 22 November 2026

## 1. Outcome

Status: **WAITING_FOR_NEW_DATA**

Stage 4 inspection and live discovery found no genuinely new Sentinel-1
acquisition or compatible pair eligible for an additional InSAR job.
No synthetic observation, displacement or velocity was created.

The existing pair remains preserved:

- `PAIR_20261109_20261121`
- HyP3 job `3889d809-88a3-4a93-89a5-258821932737`
- Processing status `PROCESSED`
- Quality status `VALID`

## 2. Live Acquisition Discovery

CDSE discovery was executed for 29 October to 22 November 2026.

- Products discovered: 2
- Existing acquisition matches: 2
- Genuine new acquisitions: 0
- Candidate pairs: 0
- Invalid pairs: 0
- HyP3 submissions: 0

The discovery results were existing catalog entries. The strict Stage 1
selector did not generate a new candidate because the full pair of valid
downloaded SLC inputs was not available.

## 3. Pair Compatibility Assessment

Existing live pair:

- Reference: 9 November 2026
- Secondary: 21 November 2026
- Relative orbit: 92
- Direction: descending
- Baseline: 12 days
- Spatial overlap metadata: 100.0%
- Orbit compatibility: verified
- Processing: valid HyP3 GAMMA 20x4

No additional pair was selected. The strict selector excludes acquisitions
that are duplicates, missing valid downloaded archives, outside relative orbit,
non-descending, outside the baseline limits or below spatial overlap.

## 4. HyP3 Cost and Approval

HyP3 GAMMA 20x4 is catalogued at 10 service credits per pair. This value is
service-catalog information, not an account credit balance.

Because no valid candidate pair exists, no submission is pending and no credit
consumption was authorized or performed.

## 5. Existing Job State

Existing job:

- Job ID: `3889d809-88a3-4a93-89a5-258821932737`
- Status: `SUCCEEDED`
- Request time: `2026-11-22 06:06:42 UTC`
- 281781751-byte ZIP was previously validated
- 29 ZIP members passed integrity checking
- No new job ID was submitted
- One status-history row is stored

The restart-safe monitor rechecked the pair and found no pending job.

## 6. Acquisition and Observation Database State

Database state:

- Sentinel-1 acquisition catalog: existing records preserved
- InSAR pairs: 3 registered historical/live pairs
- Temporal observation rows: 7590
- Live snapshots for `2026-11-21`: 7590
- Valid temporal observations: 5034
- Missing or low-quality temporal observations: 2556

The existing pair output remains:

- LOS: `tirumala_live_los_disp_80m.tif`
- Coherence: `tirumala_live_coherence_80m.tif`
- CRS: EPSG:32644
- Grid: 69 x 110
- Pixel size: 80 x 80 m

No historical snapshot or temporal observation was overwritten with fabricated
data.

## 7. Reference-Consistency Assessment

Status: **NOT_ESTABLISHED_ACROSS_PAIRS**

The 09-21 November pair uses a relative LOS measurement referenced to its own
HyP3 phase-unwrapping reference point. Cross-pair displacement comparison is
not considered physically consistent until a common spatial reference region
or scientifically justified correction is established.

Remaining limitations:

- Atmospheric phase contamination
- Phase-unwrapping errors
- Temporal decorrelation
- Low coherence
- LOS geometry, not full 3D motion
- Pair-specific reference dependence

## 8. Real Network Readiness

Stage 3 network export identifies:

- Node count: 5
- Registered pair edges: 3
- Quality-valid edge count: 1
- Connected components: 4
- Component sizes: 1, 1, 1, 2
- Real SBAS ready: false

The real network remains insufficient for cumulative displacement or velocity.
The historical pair rows are not marked as validated Stage 4 inputs.

## 9. Dashboard and Cesium Status

The following status is exported to:

- `viewer/cesium/data/stage4_status.json`

It reports:

- Overall status: `WAITING_FOR_NEW_DATA`
- Latest discovered acquisition
- Latest processed acquisition
- New pair count: 0
- Completed job count: 1
- Failed job count: 0
- Valid network edge count: 1
- Real SBAS readiness: false

The dashboard monitoring tab also displays a Stage 4 waiting summary.
Cesium status text includes the Stage 4 state and valid-edge count.

No real cumulative displacement or velocity is displayed.

## 10. Testing

Focused Stage 4 tests:

- 17 passed

Full suite:

- 97 passed
- 6 subtests passed
- 6 warnings

Test coverage confirms:

- No candidate from only duplicate discoveries
- No fabricated pair or acquisition
- No new job submission
- Network readiness remains insufficient
- Existing pair, snapshots and temporal observations are preserved

## 11. Database Backup

Stage 4 database checkpoint:

- `database/backups/monitoring_stage4_20261122T124034Z.db`

## 12. Modified and Added Files

- `scripts/export_stage4_status.py`
- `viewer/cesium/data/stage4_status.json`
- `dashboard/tabs_extension.py`
- `viewer/cesium/app.js`
- `tests/test_stage4_acquisition.py`
- `MULTI_TEMPORAL_STAGE4_REPORT.md`

No new data migration or historical record replacement was required.

## 13. Component Status

| Component | Status |
|---|---|
| Live acquisition discovery | PASS |
| Duplicate acquisition prevention | PASS |
| Candidate pair selection | PASS |
| HyP3 credit reporting | PASS |
| New HyP3 submission | NOT TESTED (no candidate) |
| New output download | NOT TESTED |
| Raster validation | NOT TESTED for a new pair |
| Database new-observation integration | NOT TESTED |
| Network connectivity assessment | PASS |
| Reference consistency | PARTIAL / NOT ESTABLISHED |
| Real SBAS readiness | NOT_READY |
| Dashboard and Cesium status | PASS |
| Historical data preservation | PASS |
| Full tests | PASS |

## 14. Remaining Blocker

Stage 4 cannot proceed to another real pair until a genuinely new, compatible,
spatially overlapping Sentinel-1 SLC acquisition becomes available and a valid
chronological pair can be formed.

No paid submission or new real observation has been claimed.
