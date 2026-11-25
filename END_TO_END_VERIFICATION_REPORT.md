# Controlled End-to-End Verification Report

**Assessment date:** 2026-11-22
**Verification mode:** Live service checks with bounded downloads

## Status Summary

| Stage | Status | Evidence |
|---|---|---|
| Sentinel-1 discovery | PASS | Two exact IW SLC candidates discovered for 9 and 21 November 2026 |
| Sentinel-1 metadata | PASS | Descending, IW, VV&VH, relative orbit 92, online, 7.7234 GB each |
| Sentinel-1 actual download | PARTIAL | Secondary transfer started and timed out/retry stalled; no valid ZIP completed |
| ASF HyP3 authentication | PASS | `HyP3` authenticated and returned zero existing jobs |
| ASF HyP3 submission | PASS | Exact pair was accepted after using ASF granule identifiers |
| HyP3 processing | PARTIAL | Job `3889d809-88a3-4a93-89a5-258821932737` remained `RUNNING` |
| Geospatial InSAR integration | NOT TESTED | No completed HyP3 output was available to inspect or align |
| Database update | PARTIAL | Candidate acquisitions and pair `PAIR_20261109_20261121` were stored; pair remains `SUBMITTED` |
| Risk assessment | BLOCKED | No newly processed InSAR output was available; existing risk data was preserved |
| CesiumJS refresh | NOT TESTED | No new valid observation was available, so no synchronization claim is made |
| NASA IMERG retrieval | PARTIAL | Official CMR lookup repaired discovery; Earthdata download returned HTTP 401 |
| Windows scheduled task | PASS | Task launched successfully, `LastTaskResult=0`, and overlap lock prevented a duplicate scheduler |
| Streamlit dashboard | PASS | HTTP 200 at `http://127.0.0.1:8501` |
| Gemini | PASS | Live generation passed with `gemini-3.1-flash-lite` |

## Sentinel-1

CDSE discovery for 8–22 November 2026 returned the exact two candidate scenes:

- Reference:
  - ID: `220f79ba-248d-4e02-81ad-1f9f10d202ed`
  - Name: `S1D_IW_SLC__1SDV_20261109T003100_20261109T003127_005383_00A43F_866B.SAFE`
  - Acquisition: `2026-11-09`
  - Size: `7723.4 MB`
- Secondary:
  - ID: `b69aeace-3306-4e9b-94f3-a6d643296386`
  - Name: `S1D_IW_SLC__1SDV_20261121T003100_20261121T003127_005558_00AA46_2C8C.SAFE`
  - Acquisition: `2026-11-21`
  - Size: `7723.4 MB`

Both candidates are descending IW SLC scenes, with relative orbit `92` and
VV&VH polarization. The actual secondary download used CDSE OAuth. It reached
`2020605952` bytes (`1927.3 MB`) and then failed/timed out during resume. The
resulting partial file is:

- `data/raw/sentinel1/S1D_IW_SLC__1SDV_20261121T003100_20261121T003127_005558_00AA46_2C8C.SAFE.zip.part`

Integrity check: `zipfile.is_zipfile(partial) = False`. It was recorded as
`FAILED`, not `DOWNLOADED`, and was not extracted or marked processed.

## ASF HyP3

The first submission attempt with `.SAFE` suffixes was rejected by the HyP3
API as invalid schema payload. A retry using the exact ASF granule identifiers
without `.SAFE` was accepted:

- Job ID: `3889d809-88a3-4a93-89a5-258821932737`
- Job type: `INSAR_GAMMA`
- Name: `tirumala_20261109_20261121`
- Request time: `2026-11-22 06:06:42 UTC`
- Status: `RUNNING`
- Looks: `20x4`
- Phase filter: `0.6`

No job completion or files were available during verification. Download and
integrity checks were not performed.

## Database

The new pair was stored as:

- Pair ID: `PAIR_20261109_20261121`
- Processing status: `SUBMITTED`
- Temporal baseline: `12` days
- HyP3 job ID: `3889d809-88a3-4a93-89a5-258821932737`

The secondary acquisition is `FAILED` for download. The reference acquisition
is also `FAILED` from the earlier catalog state. No duplicate pair was created.

## Rainfall

The configured hardcoded `.tif` URLs were incorrect for current IMERG retrieval.
Official CMR collection metadata confirmed:

- Final collection `GPM_3IMERGDF`, V07, coverage through `2025-09-30`.
- Late collection `GPM_3IMERGDL`, V07, ongoing coverage.

The downloader now resolves CMR granules and expects `.nc4` granules. A live
Late granule was found for `2026-11-07`, with title:

- `GPM_3IMERGDL.07:3B-DAY-L.MS.MRG.3IMERG.20261107-S000000-E235959.V07C.nc4`

The GES DISC HTTPS download rejected the configured Earthdata credentials with
HTTP 401. No rainfall row was inserted for `2026-11-07` or `2026-11-21`.
Existing rainfall records remain unchanged.

## Scheduler

The Windows task `TirumalaLandslideMonitoring` was triggered successfully:

- `LastRunTime`: `2026-11-22 11:45:15`
- `LastTaskResult`: `0`
- `NumberOfMissedRuns`: `0`

The scheduler lock identifies PID `25856` as the live scheduler. A second task
launch was blocked by the existing scheduler lock; no overlapping scheduler
instance was observed.

## Dashboard

The optimized Streamlit dashboard remains available:

- URL: `http://127.0.0.1:8501`
- Verification: HTTP 200

No newly processed observation was available, so the CesiumJS layer
inspector and timeline were not modified or claimed as synchronized.
