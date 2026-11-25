# Master Phase 4 – Satellite and Rainfall Discovery Report

**Assessment date:** 22 November 2026

## 1. Phase Summary

Status: **WAITING_FOR_NEW_DATA**

Master Phase 4 was completed as a discovery-only phase. It used live CDSE
metadata discovery and official CMR/NASA diagnostics. It did not download a
Sentinel-1 product, submit an HyP3 job, download rainfall, create a new pair,
modify rainfall values or update InSAR observations.

## 2. Database Backup

Database backup:

`database/backups/monitoring_master_phase4_20261122T153701Z.db`

No historical records were deleted or overwritten.

## 3. Existing Data Preserved

- 20 Sentinel-1 acquisition records.
- 3 InSAR pair records.
- Existing pair `PAIR_20261109_20261121`.
- Existing HyP3 job
  `3889d809-88a3-4a93-89a5-258821932737`.
- 29 rainfall records for 1-29 August 2026.
- 45554 observation snapshot rows in the database, including
  36171 rows for `PAIR_20261109_20261121`, 7950 rows for
  `PAIR_20260817_20260829`, and 1433 legacy/null-pair rows.
- 7590 common-grid temporal observations.
- 7590 temporal InSAR observations.
- Existing terrain, GLB, texture and GIS assets.

## 4. Sentinel-1 Discovery

Live CDSE discovery:

- Search period: 29 October to 22 November 2026.
- Products found: 2.
- Duplicate products: 2.
- Genuine new acquisitions: 0.
- Candidate pairs: 0.
- Downloads: 0.
- HyP3 submissions: 0.
- Credits consumed: 0.

Both discovered products were existing catalog IDs:

- `b69aeace-3306-4e9b-94f3-a6d643296386`
- `220f79ba-248d-4e02-81ad-1f9f10d202ed`

Status:

`WAITING_FOR_NEW_ACQUISITIONS`

Latest live discovery event:

- Search period: 29 October to 22 November 2026.
- Products found: 2.
- Duplicate products: 2.
- Genuine new acquisitions: 0.
- Discovery completion: 22 November 2026.
- Status: `WAITING_FOR_NEW_DATA`.

## 5. Candidate Pair Readiness

No candidate pair was selected because the strict pair selector requires:

- Valid downloaded SLC inputs.
- Same relative orbit.
- Compatible direction and sensor mode.
- Temporal baseline within limits.
- Sufficient spatial overlap.
- No duplicate pair.

The existing live pair remains the only fully processed pair used by the
system.

## 6. Rainfall Discovery

Existing records:

- 29 records.
- Date range: 1-29 August 2026.
- Source: NASA GPM IMERG V07C-derived records.
- Grain: study-area aggregate, not 69 x 110 pixel rainfall.

Official CMR metadata discovery found an IMERG Late `.nc4` granule.

GES DISC HTTP status:

- Range request status: 401.
- WWW-Authenticate: Basic Earthdata Login challenge.
- Diagnosis: authenticated Earthdata credentials or GES DISC session
  authorization are not accepted for the protected object in this run.

Status:

`RAINFALL_ACCESS_BLOCKED`

No rainfall record was changed and no data was downloaded.

The 3-, 7- and 14-day database rollups remain marked for reconciliation:
27 of 29 validation rows require reconciliation.

## 7. Sentinel-2 and Land Cover

Sentinel-2:

- HLS Sentinel-2 collection metadata is discoverable.
- No local valid Tirumala 12-band raster set exists.
- No data downloaded.

Status: `NOT_TESTED`

Land cover:

- ESA WorldCover 10 m 2021 is an official source.
- No local raster exists.
- No data downloaded.

Status: `NOT_TESTED`

## 8. HyP3 Credit Protection

Existing job:

- `3889d809-88a3-4a93-89a5-258821932737`
- Status: `SUCCEEDED`

No new job was submitted.
No credits were consumed in Master Phase 4.

## 9. Database and Status Output

Created status file:

`viewer/cesium/data/master_phase4_status.json`

It records:

- Sentinel-1 discovery status.
- Duplicate/new/candidate counts.
- Rainfall access status.
- Sentinel-2/land-cover readiness.
- Existing pair/job preservation.
- Database counts.

No risk formula or historical observation was changed.

## 10. Testing

Focused discovery tests:

- 21 passed.

Full suite:

- 120 passed.
- 6 subtests passed.
- 6 warnings.

The focused tests verify duplicate detection and rainfall preservation.
No live download or live HyP3 submission was tested.

## 11. Component Status

| Component | Status |
|---|---|
| Sentinel-1 live discovery | PASS |
| Sentinel-1 download | NOT TESTED |
| New acquisition detection | PASS |
| Duplicate prevention | PASS |
| Pair candidate discovery | PASS |
| HyP3 submission | NOT TESTED |
| Existing HyP3 job monitoring | PASS |
| IMERG CMR metadata | PASS |
| GES DISC data access | BLOCKED |
| Existing rainfall preservation | PASS |
| Sentinel-2 availability | NOT TESTED |
| Land-cover availability | NOT TESTED |
| Database preservation | PASS |
| 3D layer preservation | PASS |

## 12. Remaining Blockers

- No genuine new Sentinel-1 acquisition found.
- No valid downloaded SLC pair available for a new job.
- GES DISC object access returns HTTP 401.
- No local valid Sentinel-2 12-band Tirumala set.
- No local land-cover raster.
- Rainfall rollup reconciliation remains unresolved.

## 13. Phase 5 Readiness

Master Phase 4 is complete.

The project is ready to remain in discovery-only status and wait for:

- A genuinely new Sentinel-1 acquisition.
- A valid compatible pair and explicit HyP3 credit approval.
- GES DISC authentication repair or an approved official alternative.
- A complete Sentinel-2 or land-cover acquisition and validation.

No Phase 5 work was started.
