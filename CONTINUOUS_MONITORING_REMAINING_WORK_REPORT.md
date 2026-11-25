# Continuous Multi-Temporal Monitoring Remaining Work

**Assessment date:** 22 November 2026

## 1. Completed Before the Next Development Phase

- Live HyP3 authentication and job submission.
- Existing HyP3 job polling without duplicate submission.
- 281781751-byte product download and ZIP integrity validation.
- Los/coherence CRS, resolution, NoData and unit inspection.
- Alignment to EPSG:32644 at 80 m.
- SQLite pair, acquisition and observation upsert.
- Empirical risk reassessment for the 09-21 November 2026 observation.
- Cesium live pair, texture, GLB model, timeline and sync registry export.
- 84 test pass and 6 subtest pass verification.

## 2. Remaining Work

### 2.1 CDSE raw-SLC acquisition

Status: PARTIAL

Implement and verify:

- Robust range/resume handling for large 7-8 GB archives.
- Accept or reject range responses correctly.
- Compare final bytes to catalog `ContentLength`.
- Use `testzip()` and central-directory validation.
- Quarantine partials only after bounded retries.
- Preserve valid historical acquisitions.
- Record checksum or provenance when CDSE provides it.
- Run a complete download from discovery through retained valid ZIP.

The reference partial archive currently quarantined is:
`S1D_IW_SLC__1SDV_20261109T003100_20261109T003127_005383_00A43F_866B.SAFE.zip.part.quarantine-20261122T091547Z`.

### 2.2 NASA GPM IMERG

Status: BLOCKED

Official CMR collection and granule discovery works. The CMR returned valid
Late `.nc4` granule metadata. Direct GES DISC download with the configured
Earthdata session returned HTTP 401.

Required work:

- Confirm the Earthdata account is authorized for GES DISC.
- Test S3 credentials and HTTPS Earthdata redirect flow.
- Verify product latency and daily date availability.
- Download one `.nc4` file and validate NetCDF variables and fill values.
- Extract mean precipitation only for the Tirumala AOI.
- Compute complete 1, 3, 7 and 14-day windows.
- Preserve existing records until a new granule passes validation.

Do not use the old `.tif` filenames or fabricate rainfall.

### 2.3 Repeated HyP3 cycles

Status: NOT TESTED

Implement and demonstrate:

- Stable pair selection from different relative orbits.
- Baseline compatibility checks.
- Per-pair deduplication.
- Job credit and quota checks.
- Atomic status transitions.
- Automatic download, extraction and integrity validation.
- Alignment and clipping of each pair.
- Reference-point limitations and no cross-pair subtraction.
- Retry only failed jobs when the failure reason allows retry.

### 2.4 Database consistency

Status: PARTIAL

The live snapshot upserts worked for 7590 cells. Remaining work includes:

- Confirming and cleaning duplicate historical `risk_history` rows where needed.
- Avoiding duplicate acquisition and pair records.
- Adding explicit data-quality provenance per observation.
- Storing observed versus missing valid-pixel counts.
- Tracking stale evidence separately from missing evidence.
- Adding schema constraints for unique pair, date and snapshot keys.

### 2.5 Cesium continuous refresh

Status: PARTIAL

The first live pair is visible in manifest, registry and GLB assets. Next:

- Add automatic layer refresh after a pair is processed.
- Add user-visible processing state and job ID.
- Add timeline filtering for valid processed pairs only.
- Add missing/stale data indicators.
- Rebuild only changed overlays and models.
- Test viewer refresh without full server restart.

### 2.6 Alert delivery

Status: NOT TESTED

Telegram and SMTP functions exist but live delivery requires credentials and
controlled test approval. Add delivery status, retry, deduplication and
message acknowledgement.

### 2.7 Sentinel-2 U-Net

Status: BLOCKED

No complete aligned 12-band Tirumala input set is available. The U-Net remains
a benchmark-compatible upload workflow, not a Tirumala-validated detector.

Required work:

- Acquire or synthesize exactly aligned Sentinel-2 bands.
- Document normalization compatibility with Landslide4Sense training.
- Validate with independent local or field labels.
- Never use zero-filled optical channels in operational mode.

## 3. Definition of Completion for Continuous Monitoring

Continuous monitoring will be considered complete only after repeated cycles
demonstrate, for more than one real InSAR epoch:

1. Discovery and duplicate suppression.
2. Valid CDSE or ASF scene acquisition.
3. InSAR job submission and terminal success.
4. Raster integrity and geospatial validation.
5. Valid database snapshots.
6. Updated empirical risk evidence.
7. Cesium timeline, texture and GLB refresh.
8. Scheduler no-overlap and restart behavior.
9. Preserved historical records and explicit blocked/fresh/stale status.
