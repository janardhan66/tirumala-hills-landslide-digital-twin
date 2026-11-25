# Stage 6 Checkpoint 2: Dataset Audit Report

**Assessment date:** 22 November 2026

## 1. Scope

This checkpoint audits existing data and external access only. It does not
modify the existing risk formula, database records, datasets or verified
Stage 1-5 outputs. It does not download large datasets or submit HyP3 jobs.

## 2. Rainfall Audit

### Existing coverage

- Date range: 1-29 August 2026
- Database rows: 29
- CSV rows: 29
- Unit: millimetres
- Grid-cell coverage: 1 aggregate study-area row per date
- Source metadata: `NASA GPM IMERG V07C`
- Database quality: `FINAL`
- Daily missing values: 0

### Accumulations

The feature CSV contains:

- 3-day accumulations: 27 complete values
- 7-day accumulations: 23 complete values
- 14-day accumulations: 16 complete values
- 2, 6 and 13 calendar-window edge values missing at the start respectively

The SQLite database currently has no missing 3-, 7- or 14-day values in its
29-row test, but the retained CSV and database should be reconciled before
treating database rollups as source-verified.

At the first complete window, the retained feature CSV reports 14.8 mm for
3-day accumulation while the database first row currently reports 16.5 mm.
This discrepancy requires provenance and rollup reconciliation before any
rainfall trigger is calculated from database rollups.

Daily exact-value comparison found no listed date/row mismatch above
floating-point precision. The database and CSV preserve the same 29 daily
date range.

### Limitations

- Rainfall is study-area-level context, not a 69 x 110 pixel rainfall field.
- No spatial rainfall raster is retained for per-cell integration.
- GES DISC download is blocked by HTTP 401.
- Earthdata login endpoint is reachable, but GES DISC is rejecting the
  configured session or authorization.

## 3. DEM, Slope and Aspect Audit

All three rasters align exactly:

| Dataset | CRS | Shape | Resolution | Bounds | NoData | Valid cells |
|---|---|---:|---:|---|---|---:|
| DEM | EPSG:32644 | 69 x 110 | 80 m | 319720,1508840 to 328520,1514360 | 0.0 | 4083 |
| Slope | EPSG:32644 | 69 x 110 | 80 m | 319720,1508840 to 328520,1514360 | 0.0 | 3692 |
| Aspect | EPSG:32644 | 69 x 110 | 80 m | 319720,1508840 to 328520,1514360 | -9999.0 | 4083 |

Validated ranges:

- DEM: 180.027 to 899.161 m
- Slope: 0.219 to 46.075 degrees
- Aspect: -1.0 to 359.986 degrees

CRS, shape, transform and resolution match. The DEM nodata value is 0.0,
while aspect uses -9999.0. Aspect -1.0 is a descriptor of no defined aspect
and must not be interpreted as an eastward azimuth.

Status: **READY** for spatial factor integration.

## 4. GSI Historical Landslide Inventory Audit

The GSI validation table contains 15 rows.

- 0 missing coordinates.
- 0 duplicate coordinates.
- 15 coordinates labelled `map-derived approximate`.
- Latitude range: 13.652931 to 13.677154.
- Longitude range: 79.341878 to 79.398334.
- Source: GSI Figure 3.2.

Data status:

- 7 terrain and InSAR available.
- 4 terrain data unavailable.
- 4 terrain available but InSAR quality insufficient.

The coordinates are supporting map-derived evidence, not surveyed GPS ground
truth. The original GSI report bibliographic citation is not preserved and
coordinate accuracy is not independently established.

Status: **READY WITH PROVENANCE LIMITATION**.

## 5. U-Net H5 Audit

Dataset inventory:

- Image H5 files: 3799
- Mask H5 files: 3799

All 3799 image H5 files:

- Dataset: `img`
- Shape: `(128, 128, 14)`
- HWC source layout

All 3799 mask H5 files:

- Dataset: `mask`
- Shape: `(128, 128)`
- Labels: binary 0/1

Across all masks:

- Zero pixels: 60,800,026
- Positive pixels: 1,442,790
- Positive fraction: 2.318%

The image audit found:

- 871399424 finite/total elements.
- 0 bad image opens.
- 0 non-finite elements in the audited H5 content.
- Float64 source values; existing inference converts to float32.

The model expects HWC-to-CHW conversion and `(14, 128, 128)` input.

Status:

- Software compatibility: PASS
- Benchmark asset quality: PASS
- Tirumala local ground-truth validation: BLOCKED
- Georeferenced Tirumala U-Net input: NOT AVAILABLE

Do not present Landslide4Sense performance as local Tirumala accuracy.

## 6. InSAR LOS and Coherence Audit

The live pair is:

- `PAIR_20261109_20261121`
- Reference: 2026-11-09
- Secondary: 2026-11-21
- HyP3 GAMMA 20x4
- 80 m output
- EPSG:32644
- Shape: 69 x 110
- Reference point: 14.4744471 N, 78.81569024 E

LOS alignment:

- Valid cells: 7240
- Range: -0.111919 to -0.053715 m
- NoData: NaN

Coherence alignment:

- Valid cells: 7245
- Range: 0.024199 to 0.961330
- NoData: NaN

The LOS and coherence rasters align exactly with the DEM, slope and aspect.
The LOS file is relative pair LOS, not vertical displacement.

Status: **READY WITH SCIENTIFIC LIMITATION**.

## 7. GES DISC and Rainfall Access

Official CMR metadata confirms:

- Final IMERG collection `GPM_3IMERGDF`, V07, coverage through 2025-09-30.
- Late IMERG collection `GPM_3IMERGDL`, V07, ongoing coverage.
- A current 2026 `.nc4` Late granule can be discovered.

The actual GES DISC object URL returned HTTP 401 with the Earthdata Basic
challenge. The Earthdata login host itself responds, so the problem is not
Earthdata login service availability; it is GES DISC authorization or session
exchange for this account/configuration.

Official alternatives:

- CMR plus GES DISC HTTPS/S3 credentials.
- NASA Earthdata S3 credentials for GES DISC data.
- Copernicus Climate Data Store ERA5-Land precipitation as a separate official
  alternative, requiring a new dataset integration and validation.
- CHIRPS is an official NASA/USGS-supported climate rainfall alternative,
  but it is a different product and must not be mixed silently with IMERG.

Status: **BLOCKED** for new IMERG download until GES DISC authorization works.

## 8. Sentinel-2 and Land-Cover Sources

### Sentinel-2

Official options identified:

- Copernicus Data Space Ecosystem Sentinel-2 L2A.
- NASA CMR HLS Sentinel-2 product `HLSS30`, V2.0.
- ESA/NASA Harmonized Landsat Sentinel-2 as an alternative source.

No local Sentinel-2 product or complete 12-band TIRUMALA set exists.

Status: **BLOCKED / WAITING_FOR_DATA**.

### Land cover

Official ESA WorldCover 10 m 2021 v200 land-cover product is suitable:

- 11 land-cover classes.
- 10 m resolution.
- Sentinel-1/Sentinel-2 derived.
- CC-BY-4.0.

No local land-cover raster exists and no download was performed.

Status: **BLOCKED / WAITING_FOR_DATA**.

## 9. Dataset Availability and Quality Matrix

| Dataset | Source | Date range | Resolution | Coverage | Quality | Stage 6 status |
|---|---|---|---|---|---|---|
| Rainfall | Existing GPM IMERG V07C-derived records | 1-29 Aug 2026 | Study-area aggregate | 29 dates | Good historical completeness | READY WITH SPATIAL LIMITATION |
| DEM | Local Copernicus-derived raster | Static | 80 m | 69 x 110 AOI | Aligned, EPSG:32644 | READY |
| Slope | Local DEM-derived raster | Static | 80 m | 69 x 110 AOI | 3692 valid cells | READY |
| Aspect | Local DEM-derived raster | Static | 80 m | 69 x 110 AOI | Nodata -9999 | READY |
| GSI inventory | GSI Figure 3.2 map-derived | Historical | Point locations | 15 points | Approximate | READY WITH PROVENANCE LIMITATION |
| InSAR LOS | ASF HyP3 GAMMA | 9-21 Nov 2026 | 80 m | 69 x 110 AOI | 7240 valid values | READY WITH REFERENCE LIMITATION |
| InSAR coherence | ASF HyP3 GAMMA | 9-21 Nov 2026 | 80 m | 69 x 110 AOI | 7245 valid values | READY WITH QUALITY LIMITATION |
| U-Net images/masks | Landslide4Sense H5 | Training set | 128 x 128 | 3799 patch pairs | Complete binary masks | SOFTWARE READY / LOCAL VALIDATION BLOCKED |
| Sentinel-2 | CDSE/HLS official source | No local data | 10-30 m candidate | Tirumala | Not evaluated locally | BLOCKED |
| Land cover | ESA WorldCover 2021 | 2021 | 10 m | Global/Tirumala | Official product | BLOCKED / NOT DOWNLOADED |
| New rainfall download | GES DISC | Not available locally | Candidate daily | Tirumala | 401 unauthorized | BLOCKED |

## 10. Reuse Recommendation

Ready for integration without new acquisition:

- DEM.
- Slope.
- Aspect.
- GSI inventory coordinates.
- Existing rainfall daily and 3/7/14-day context.
- Existing InSAR LOS and coherence.
- Existing U-Net checkpoint and H5 benchmark data.
- Existing spatial/evidence risk formula.

Requires external access or processing before integration:

- New rainfall download.
- Sentinel-2 band set.
- ESA WorldCover land-cover raster.
- Independent Tirumala U-Net ground truth.

Not ready for calibrated claims:

- Local landslide probability.
- Local U-Net accuracy.
- Real cumulative deformation.
- LOS vertical conversion.
- Automatic landslide warning.

## 11. Validation Tests

Checkpoint 2 read-only validation used:

- 32 focused data-ingestion, raster-preprocessing, temporal and risk tests.
- 100 full-suite tests passed in the latest project baseline.
- 6 subtests passed.
- No database or dataset mutation occurred during the audit.

## 12. Checkpoint 3 Recommendation

Proceed with Checkpoint 3 using only ready local datasets:

1. Register DEM/slope/aspect, rainfall, GSI, InSAR and U-Net benchmark metadata.
2. Align existing rasters and derive factor availability tables.
3. Preserve missing and low-quality values.
4. Do not add land cover or Sentinel-2 until a real validated raster exists.
5. Keep NASA IMERG as `BLOCKED` until GES DISC authorization is resolved.
6. Defer the multi-factor spatial risk implementation to Checkpoint 4/5 after
   the data registry and explainable factor availability are stable.

The Checkpoint 2 audit is complete and no existing database or dataset record
was modified.
