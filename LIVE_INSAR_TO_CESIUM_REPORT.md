# Live InSAR-to-Cesium Workflow Report

**Assessment date:** 2026-11-22

## Summary

The first new real InSAR observation was downloaded from ASF HyP3, validated,
aligned to the Tirumala 80 m grid, stored in SQLite, included in a recalculated
empirical risk assessment, and exported to the CesiumJS 3D viewer.

This is a single 12-day HyP3 result. It is not a calibrated landslide
probability, a vertical-ground-truth measurement, or evidence of a future
landslide.

## Component Status

| Component | Status | Evidence |
|---|---|---|
| Existing HyP3 job | PASS | Job `3889d809-88a3-4a93-89a5-258821932737` is `SUCCEEDED` |
| HyP3 product download | PASS | 281781751-byte ZIP downloaded and validated |
| InSAR extraction | PASS | All 29 ZIP members passed `testzip()` |
| Raster validation | PASS | LOS/coherence are EPSG:32644, 80 m, float rasters |
| Tirumala alignment | PASS | LOS and coherence aligned to 69 x 110 cells |
| Database update | PASS | Pair `PAIR_20261109_20261121` is `PROCESSED` |
| Risk update | PASS | 7590 cells; Low 5195, Medium 2177, High 218 |
| Cesium synchronization | PASS | Live pair is in manifest, texture, GLB model and timeline |
| Test suite | PASS | 84 passed, 6 subtests passed |
| Dashboard | PASS | Streamlit HTTP 200 |
| Cesium server | PASS | Manifest, registry, PNG and GLB all HTTP 200 |
| CDSE Sentinel-1 download | PARTIAL | The reference partial archive was quarantined; no local full CDSE ZIP is claimed |
| NASA IMERG | BLOCKED | CMR discovery works; GES DISC Earthdata download returned HTTP 401 |
| Scheduler | PASS | Task launched with `LastTaskResult=0`; pipeline lock prevents overlap |

## HyP3 Product

- Job ID: `3889d809-88a3-4a93-89a5-258821932737`
- Job type: `INSAR_GAMMA`
- Status: `SUCCEEDED`
- Reference: `S1D_IW_SLC__1SDV_20261109T003100_20261109T003127_005383_00A43F_866B`
- Secondary: `S1D_IW_SLC__1SDV_20261121T003100_20261121T003127_005558_00AA46_2C8C`
- Baseline: 12 days
- Filename: `S1DD_20261109T003100_20261121T003100_VVR012_INT80_G_ueF_FD61.zip`
- Size: 281781751 bytes
- Output resolution: 80 m
- Processing: GAMMA 20x4, phase filter 0.6, MCF unwrapping
- DEM: Copernicus GLO-30

## InSAR Validation

Source rasters:

- LOS displacement: meters
- Vertical displacement: meters, under a vertical-only assumption
- Coherence: 0 to 1
- CRS: EPSG:32644
- Source shape: 2915 x 3615
- Source pixel size: 80 x 80 m
- Product reference point: 14.4744471 N, 78.81569024 E

Aligned outputs:

- `tirumala_live_los_disp_80m.tif`
- `tirumala_live_coherence_80m.tif`
- Shape: 69 x 110
- Pixel size: 80 x 80 m
- Quality-valid LOS/coherence cells: 5034
- Missing or low-quality cells are retained as missing; zeros are not converted
  into displacement measurements.

LOS values range from -0.111919 to -0.053715 m in valid AOI pixels. This
is a relative pair measurement and may contain atmospheric and unwrapping
effects. The supplied map warns that a reference adjustment may be required.

## Database and Risk

- Pair: `PAIR_20261109_20261121`
- Processing status: `PROCESSED`
- Observation date: `2026-11-21`
- Upserted observation rows for the live date: 7590
- Quality GOOD snapshots: 5034
- Missing/low-quality snapshots: 2556
- Empirical evidence scores:
  - Low: 5195
  - Medium: 2177
  - High: 218
  - Mean score: 29.73

The dashboard labels and report documentation must continue to describe these
values as relative empirical evidence scores, not calibrated probabilities.

## CesiumJS

The live pair was added to:

- `viewer/cesium/layers_manifest.json`
- `viewer/cesium/data/spatial_grid_lookup.json`
- `viewer/cesium/data/temporal_registry.json`
- `viewer/cesium/data/sync_status.json`

New served artifacts:

- `viewer/cesium/textures/layer_los_pair_20261109_20261121.png`
- `viewer/cesium/models/tirumala_terrain_los_pair_20261109_20261121.glb`

The sync status is `SYNCHRONIZED`, the latest observation is `2026-11-21`,
7590 cells are observed, and the registry contains the live pair timeline entry.

## CDSE and Rainfall

The direct CDSE Sentinel-1 download was not completed as a valid local archive.
The invalid 3104964608-byte reference partial archive was quarantined:

`data/raw/sentinel1/S1D_IW_SLC__1SDV_20261109T003100_20261109T003127_005383_00A43F_866B.SAFE.zip.part.quarantine-20261122T091547Z`

The official GPM CMR metadata and CMR `.nc4` granule lookup are implemented.
A confirmed Late granule was found, but GES DISC returned HTTP 401 with the
configured Earthdata session. No rainfall was fabricated or inserted.

## Verification

- Full test suite: 84 passed, 6 subtests passed
- Streamlit: HTTP 200
- Cesium viewer: HTTP 200
- Cesium live texture/model/registry: HTTP 200
- Scheduler task: launch result `0`

Independent verification also confirms that 7590 live-date rows are upserts,
not necessarily newly created snapshots. Database inspection found repeated
aggregate `risk_history` entries for `2026-11-21`; consolidating one current
aggregate per observation date remains database-hardening work.
