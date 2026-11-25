# Stage 1: Multi-Temporal Acquisition and Pair-Management Report

**Assessment date:** 22 November 2026

## 1. Outcome

Stage 1 is implemented. The project now has:

- A safe SQLite migration for Stage 1 metadata.
- Acquisition metadata fields for acquisition timestamp, beam mode and spatial coverage.
- InSAR pair metadata fields for orbit, relative orbit, orbit compatibility,
  spatial overlap, quality status, selection method and output archive.
- A pair-selection module that requires a valid downloaded SLC archive.
- A no-submission discovery and pair-selection CLI.
- Tests for duplicate acquisition/pair prevention, orbit compatibility,
  temporal baseline, pair selection and existing-pair preservation.

No HyP3 job was submitted during Stage 1.

## 2. Database Backup

The migration backup was created before the production SQLite database was
modified:

- `database/backups/monitoring_20261122T093223Z.db`
- `database/backups/monitoring_20261122T093223Z.db-wal`
- `database/backups/monitoring_20261122T093223Z.db-shm`

A second verification migration backup was also created:

- `database/backups/monitoring_20261122T093524Z.db`

## 3. Schema Changes

### Acquisition table additions

- `acquisition_timestamp`
- `beam_mode`
- `spatial_coverage`

The existing acquisition primary key remains `acquisition_id`; no acquisition
rows were deleted or replaced.

### InSAR pair table additions

- `orbit_direction`
- `relative_orbit`
- `orbit_compatibility`
- `spatial_overlap_percent`
- `quality_status`
- `selection_method`
- `output_archive`

The existing pair primary key remains `pair_id`; no pair rows were deleted,
overwritten or duplicated.

## 4. Existing Pair Preservation

The existing pair remains:

- Pair ID: `PAIR_20261109_20261121`
- Reference: `220f79ba-248d-4e02-81ad-1f9f10d202ed`
- Secondary: `b69aeace-3306-4e9b-94f3-a6d643296386`
- Temporal baseline: 12 days
- Orbit: descending, relative orbit 92
- Processing status: `PROCESSED`
- Quality status: `PROCESSED`
- Spatial overlap metadata: 100.0%
- HyP3 job: `3889d809-88a3-4a93-89a5-258821932737`

The existing 7590 observation rows for `2026-11-21` remain in the database.
The independent database check reports 45554 total observation snapshots across
existing historical epochs and live rows.

## 5. Acquisition History

The database contains 17 Sentinel-1 acquisition catalog rows.

Two newly verified live scenes are represented:

| Acquisition | Date | Orbit | Relative orbit | Download status |
|---|---|---|---:|---|
| `220f79ba-248d-4e02-81ad-1f9f10d202ed` | 2026-11-09 | DESCENDING | 92 | FAILED |
| `b69aeace-3306-4e9b-94f3-a6d643296386` | 2026-11-21 | DESCENDING | 92 | DOWNLOADED |

The reference acquisition metadata remains associated with the live pair,
even though no complete direct-CDSE reference ZIP is retained in the local
acquisition file state. This does not change the fact that the HyP3 processing
package already exists and was independently verified.

## 6. Pair Selection

The implementation is in:

- `src/data/multi_temporal.py`

It supports:

- Temporal baseline calculation.
- Orbit direction validation.
- Relative-orbit validation.
- Sentinel-1 IW/SLC beam validation.
- WKT footprint overlap calculation.
- Configurable minimum/maximum temporal baseline.
- Configurable minimum AOI overlap.
- Duplicate pair prevention.
- A connected chronological pair-selection strategy.

The strict live selector now requires:

- Sentinel-1 SLC.
- `DOWNLOADED` status.
- Existing local file.
- Valid ZIP when the file is a ZIP.
- Same descending/ascending direction.
- Same relative orbit.
- Baseline from 6 to 36 days by default.
- At least 90% AOI overlap by default.

No all-to-all pair combinations are created.

## 7. Dry-Run Discovery Result

The Stage 1 CLI was run for 20-22 November 2026 with pair selection:

- CDSE products discovered: 1
- Duplicate acquisitions: 1
- New acquisitions registered: 0
- Proposed pair candidates: 0
- HyP3 submissions: 0

The strict result is correct: the cataloged secondary scene is retained, but
the strict selector does not combine it with acquisitions lacking a valid local
SLC archive.

## 8. Future Acquisition Handling Example

When CDSE discovers a genuinely new SLC:

1. The acquisition is inserted once using its CDSE product ID.
2. Download status begins at `PENDING`.
3. The ZIP is downloaded and tested atomically.
4. A valid archive is marked `DOWNLOADED`.
5. Pair selection compares it only with valid downloaded acquisitions on the
   same orbit direction and relative orbit.
6. A candidate is proposed within the baseline and overlap limits.
7. The pair is registered as `CANDIDATE`.
8. HyP3 submission remains disabled in Stage 1.

No future acquisition or pair is invented.

## 9. New or Modified Files

- `src/data/multi_temporal.py`
- `scripts/migrate_multi_temporal.py`
- `scripts/manage_multi_temporal.py`
- `database/schema.sql`
- `src/data/db.py`
- `scripts/download_sentinel1.py`
- `tests/test_multi_temporal.py`

The existing pair-processing and Cesium code remains intact.

## 10. Test Results

Stage 1 targeted tests:

- 5 multi-temporal tests passed.
- 23 Stage 1/database tests passed.

Full project suite:

- 89 passed
- 6 subtests passed
- 6 warnings

Warnings are existing deprecation and test-collection warnings, not Stage 1
failures.

## 11. Stage 1 Classification

- Database schema migration: PASS
- Database backup: PASS
- Existing pair preservation: PASS
- Acquisition metadata: PASS
- Duplicate acquisition handling: PASS
- Duplicate pair handling: PASS
- Orbit/baseline/overlap selection: PASS
- Discovery dry run: PASS
- No HyP3 submissions: PASS
- Continuous monitoring: NOT TESTED
