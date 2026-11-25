# Academic Project Completion Report

## Tirumala Hills Landslide Monitoring and 3D Digital Twin

**Assessment date:** 22 November 2026

## 1. Project Scope

The project is a research and demonstration platform for combining Tirumala
terrain, Sentinel-1 InSAR, rainfall context, historical landslide locations,
rule-based evidence assessment, Landslide4Sense HDF5 segmentation and CesiumJS
visualization. It is not an operational landslide early-warning system and does
not provide calibrated probability of future landslide occurrence.

## 2. Verified Accomplishments

### 2.1 One live InSAR observation workflow

ASF HyP3 job `3889d809-88a3-4a93-89a5-258821932737` was independently
checked and found in `SUCCEEDED` status. The job represents the pair
`PAIR_20261109_20261121`:

- Reference acquisition: 9 November 2026
- Secondary acquisition: 21 November 2026
- Temporal baseline: 12 days
- Processing: GAMMA 20x4
- Adaptive phase filter: 0.6
- Unwrapping: MCF
- Output resolution: 80 m
- DEM: Copernicus GLO-30

The downloaded ZIP is 281781751 bytes. ZIP integrity and all 29 members passed
`testzip()`. The source package contains LOS displacement, vertical
displacement, coherence, unwrapped phase, incidence, DEM, water-mask and
amplitude rasters in EPSG:32644.

### 2.2 Geospatial alignment

LOS and coherence rasters were aligned to the existing Tirumala grid:

- CRS: EPSG:32644
- Shape: 69 x 110
- Pixel size: 80 x 80 m
- Quality valid combined LOS/coherence pixels: 5034
- Missing or low-quality values were retained as missing
- No missing value was replaced with a displacement value or zero

The LOS map is in meters and relative to the automatic HyP3 phase reference
point. Positive values indicate movement towards the sensor and negative values
indicate movement away from the sensor according to the HyP3 product metadata.
It is not a calibrated vertical or 3D ground-motion measurement.

### 2.3 SQLite database and evidence score

The pair is stored as `PROCESSED` with:

- LOS raster path
- Coherence raster path
- Valid pixel count: 5034
- Mean coherence: 0.589436948299408
- Processing and limitation notes

The 7590-cell live-date record set was upserted for `2026-11-21`. The empirical
evidence result was:

- Low: 5195
- Medium: 2177
- High: 218
- Mean score: 29.73
- Maximum score: 84.99

These values are relative evidence categories. They are not calibrated
landslide probability, predicted probability or confirmed landslide hazard.

### 2.4 CesiumJS synchronization

The live pair was exported to:

- `layers_manifest.json`
- `spatial_grid_lookup.json`
- `temporal_registry.json`
- `sync_status.json`
- Live LOS PNG texture
- Live terrain-overlaid GLB model

The synchronization status independently reads `SYNCHRONIZED`, latest
observation date `2026-11-21`, observed cells 7590 and active alerts 32.
Both the manifest/registry and the live texture/GLB were returned successfully
by the local Cesium HTTP server.

### 2.5 Testing

The final full Python test run independently passed:

- 84 tests passed
- 6 subtests passed
- 6 warnings

Targeted post-live-integration InSAR/preprocessing tests passed 9/9.

## 3. Methodology

The project uses a staged and auditable workflow:

1. Discover Sentinel-1 acquisitions through CDSE OData.
2. Check duplicate acquisition IDs in SQLite.
3. Attempt resumable downloads with range handling and ZIP validation.
4. Submit compatible Sentinel-1 pairs to ASF HyP3.
5. Poll existing jobs without submitting duplicate jobs.
6. Download and integrity-check terminal products.
7. Inspect CRS, resolution, units, bounds and NoData.
8. Clip and reproject LOS/coherence to EPSG:32644 at 80 m.
9. Preserve missing values and coherence-screen valid observations.
10. Upsert observation snapshots and risk history.
11. Export raster overlays, lookup, registry and GLB assets to CesiumJS.
12. Present uncertainty and limitations in the dashboard.

The evidence score is a transparent weighted combination of slope, terrain,
InSAR and temporal indicators. It is not a physical landslide simulation and
does not replace geological or field assessment.

## 4. Feature Classification

| Feature | Classification | Evidence |
|---|---|---|
| Dashboard | PASS | Streamlit HTTP 200 |
| Database | PASS | Live pair and 7590 observation rows verified |
| CDSE discovery | PASS | Recent IW SLC metadata discovered |
| CDSE full raw-SLC download | PARTIAL | Partial file quarantined; valid full ZIP not retained |
| HyP3 authentication/submission | PASS | Job accepted and succeeded |
| HyP3 output download | PASS | 281781751-byte ZIP and all members validated |
| InSAR raster alignment | PASS | 69 x 110, EPSG:32644, 80 m |
| Empirical risk reassessment | PASS | One live observation scored |
| Cesium live export | PASS | Texture, GLB, manifest, registry and HTTP 200 |
| Windows scheduler | PASS | Task launch result zero; scheduled daemon telemetry verified |
| Repeated monitoring cycles | NOT TESTED | Only one real live HyP3 cycle is verified |
| NASA IMERG ingestion | BLOCKED | CMR works, but GES DISC Earthdata download returned HTTP 401 |
| Sentinel-2 for Tirumala U-Net | BLOCKED | No complete aligned B01-B12 dataset is available |
| Tirumala U-Net validation | PARTIAL | Model loads; benchmark result is not Tirumala validation |
| Telegram and SMTP | NOT TESTED | Credentials and delivery were not verified |

## 5. Limitations

The HyP3 LOS measurement is relative to an automatic unwrapping reference
point and may contain atmospheric effects or phase-unwrapping errors. The
water mask was not applied during unwrapping.

The vertical displacement map uses an assumption that displacement is entirely
vertical. This is not treated as field-validated ground truth.

Rainfall records remain historical and fresh IMERG retrieval is blocked. No
fresh rainfall was fabricated.

The direct CDSE raw-SLC download did not complete. Therefore it should not be
claimed that a complete repeated CDSE-to-HyP3 pipeline is operational.

Repeated scheduler cycles have not been proven over multiple real acquisitions.
The next completion milestone requires at least two or more real, independently
processed, database-stored and Cesium-visible observation epochs, without
manual intervention.

## 6. Conclusion

The project is substantially implemented and has passed one complete real
HyP3-to-database-to-Cesium workflow. It is suitable as a verified research
prototype and academic demonstration. It is not yet suitable for submission
as a continuously operating operational landslide-monitoring system.
