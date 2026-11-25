# Stage 2: Automated Multi-Temporal HyP3 Processing Report

**Assessment date:** 22 November 2026

## 1. Outcome

Stage 2 is implemented as a controlled, restart-safe HyP3 processing workflow.
No new HyP3 job was submitted because live CDSE discovery found no genuinely
new, valid downloaded SLC pair eligible for processing.

The first real pair remains:

- `PAIR_20261109_20261121`
- HyP3 job `3889d809-88a3-4a93-89a5-258821932737`
- Status `SUCCEEDED` / pair status `PROCESSED`

## 2. Acquisition and Pair Discovery

Live CDSE discovery was run for 29 October to 22 November 2026:

- Products discovered: 2
- New acquisitions: 0
- Duplicates excluded: 2
- Strict pair candidates: 0
- HyP3 submissions: 0

The strict Stage 1 selector requires a valid local downloaded SLC for both
reference and secondary acquisitions. Only the 21 November 2026 secondary
scene has a validated local 7723375924-byte ZIP; the 9 November reference
scene has no complete local archive.

No future date or synthetic pair ID was invented.

## 3. HyP3 Submission Safeguards

Implemented:

- `submit_approved_pair(...)`
- Explicit `approval_granted=False` rejection.
- HyP3 GAMMA 20x4 published cost lookup.
- 20x4 expected cost recorded as 10 service credits.
- Submission configuration JSON.
- Submitted and status-check timestamps.
- Duplicate pair/job registration checks.

The project does not expose an account credit balance through the SDK cost
catalog. Therefore Stage 2 will require explicit user approval before any
new job consumes credits. No new submission was authorized or attempted.

## 4. Job Status Persistence

The SQLite migration added:

- `submitted_at`
- `last_status_check_at`
- `job_config_json`
- `expected_credit_cost`
- `output_validation_status`
- `hyp3_job_status_history`

Existing pair `PAIR_20261109_20261121` now records:

- Submitted at: `2026-11-22T06:06:42+00:00`
- Last status check: `2026-11-22T09:46:30.053299+00:00`
- Expected credit cost: 10
- Configuration: GAMMA, 20x4, displacement maps, DEM and incidence map
- Status history: `SUCCEEDED`

The monitor rereads pending status combinations after restart and does not
submit duplicate jobs.

## 5. Product Retrieval

The existing succeeded job has one 281781751-byte output ZIP:

`S1DD_20261109T003100_20261121T003100_VVR012_INT80_G_ueF_FD61.zip`

The product was previously downloaded and its 29 ZIP members passed
`testzip()`. The Stage 2 monitor safely extracts downloaded HyP3 ZIPs in a
temporary directory and validates members before copying rasters.

No partial new product download was marked successful.

## 6. Raster Validation and Alignment

The existing pair outputs are independently verified at:

- `PAIR_20261109_20261121/tirumala_live_los_disp_80m.tif`
- `PAIR_20261109_20261121/tirumala_live_coherence_80m.tif`

Both are:

- EPSG:32644
- 69 x 110
- 80 x 80 m
- LOS valid range -0.111919 to -0.053715 m
- Coherence valid range 0.024199 to 0.961330
- Missing/NoData represented as NaN

No missing pixels were converted to zero displacement.

## 7. Database Integration

The existing pair is preserved:

- Processing status: `PROCESSED`
- Quality status: `VALID`
- Output validation status: `VALID`
- 7590 existing observations for `2026-11-21`
- No duplicate pair was created
- No duplicate snapshot batch was added

One new status-history row was persisted for the succeeded job. The existing
pair's LOS and coherence output paths remain the canonical live filenames.

## 8. Testing

Full test suite:

- 91 passed
- 6 subtests passed
- 6 warnings

Stage 2/pair tests:

- 11 passed

Covered:

- Duplicate job prevention by existing pair/job ID
- Approval-gated submission
- Persisted job status history
- Restart recovery via SQLite
- Existing pair preservation
- Downloaded-SLC pair filtering
- LOS/coherence raster shape and CRS validation
- No missing-pixel substitution

## 9. Controlled Live Demonstration

Status: BLOCKED by no new eligible real pair.

The existing succeeded job was polled successfully and revalidated. CDSE
discovery found only duplicate products. Therefore:

- No additional job was submitted
- No additional ZIP was downloaded
- No additional observation snapshots were invented
- No credit/quota was consumed

## 10. Component Status

| Feature | Status |
|---|---|
| Stage 2 job monitor | PASS |
| Persisted status history | PASS |
| Restart recovery | PASS |
| Duplicate submission prevention | PASS |
| Credit-cost reporting | PASS (catalog cost only) |
| Approval gate | PASS |
| ZIP integrity and extraction | PASS |
| Raster validation/alignment | PASS |
| Existing pair preservation | PASS |
| New pair discovery | PARTIAL (only duplicates found) |
| New pair submission | BLOCKED (no eligible pair and no authorization) |
| New pair processing | NOT TESTED |
| Additional database observations | NOT TESTED |
| Continuous monitoring across repeated real cycles | NOT TESTED |

## 11. Modified Files

- `src/data/db.py`
- `database/schema.sql`
- `scripts/process_insar.py`
- `scripts/migrate_stage2_hyp3.py`
- `scripts/hyp3_job_monitor.py`
- `tests/test_insar_pipeline.py`

Stage 2 does not start Stage 3 time-series inversion or cumulative deformation.
