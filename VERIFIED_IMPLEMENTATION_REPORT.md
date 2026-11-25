# Verified Implementation Report

**Project:** Tirumala Hills Landslide Monitoring and Risk Assessment

**Assessment date:** 22 November 2026

## Verification conclusion

The repository has a verified first live InSAR-to-SQLite-to-Cesium workflow.
It does not have repeated, unattended continuous multi-temporal monitoring.

No live claim in this report is based on a mock or simulated InSAR raster.
The evidence is from ASF HyP3 job
`3889d809-88a3-4a93-89a5-258821932737`.

## Verified live workflow

| Component | Status | Verified evidence |
|---|---|---|
| HyP3 job | PASS | Job status `SUCCEEDED` |
| HyP3 product | PASS | 281781751-byte ZIP; 29 members passed integrity checking |
| LOS/coherence | PASS | EPSG:32644, 80 m, 69 x 110 grid |
| Valid quality cells | PASS | 5034 cells had coherence >= 0.50 and valid LOS |
| SQLite pair | PASS | `PAIR_20261109_20261121` status `PROCESSED` |
| Live observations | PASS | 7590 observation rows upserted for `2026-11-21` |
| Empirical risk | PASS | 5195 Low, 2177 Medium, 218 High |
| Cesium registry | PASS | Latest observation 2026-11-21; 7590 observed cells |
| Cesium HTTP assets | PASS | Live manifest, PNG texture and GLB returned HTTP 200 |
| Dashboard | PASS | Streamlit returned HTTP 200 |
| Windows scheduler | PASS | Task launch result 0; daemon lock prevented overlap |
| Repeated automation | NOT TESTED | Only one real live HyP3 cycle is verified |
| CDSE complete SLC download | PARTIAL | Invalid partial file was quarantined |
| NASA IMERG download | BLOCKED | CMR discovery works; GES DISC returned HTTP 401 |

## Independent raster verification

Aligned LOS:

- Minimum valid value: -0.111919 m
- Maximum valid value: -0.053715 m
- Missing/NoData: NaN

Aligned coherence:

- Minimum valid value: 0.024199
- Maximum valid value: 0.961330
- Missing/NoData: NaN

Coherence values below 0.50 are not used as quality-screened InSAR evidence.
The LOS map remains relative to the HyP3 phase reference and is not a vertical
ground-truth measurement.

## Existing SQLite records

The pair and observation state were checked against `database/monitoring.db`.

- 7590 observation rows exist for `2026-11-21`
- 5034 rows are marked `GOOD`
- 2556 rows are missing or low-quality
- 7590 observation rows were upserted for the live date
- The latest processed InSAR date is `2026-11-21`
- Multiple historical aggregate rows for `2026-11-21` were found in
  `risk_history`; database deduplication is a remaining consistency task

## Tests

Full test run:

```text
84 passed, 6 warnings, 6 subtests passed
```

Targeted live preprocessing/InSAR tests:

```text
9 passed
```

The test suite includes offline fixtures and mocks. It does not, by itself,
prove repeated live monitoring.

## Existing limitations

- Direct CDSE download of complete raw SLC scenes is incomplete.
- NASA GPM IMERG GES DISC retrieval returned HTTP 401.
- Telegram and SMTP live delivery were not verified.
- Complete aligned Sentinel-2 B01-B12 Tirumala inputs are unavailable.
- U-Net inference is not Tirumala-ground-truth validated.
- The scheduler was tested for task launch and overlap, not repeated cycles
  across multiple real acquisitions.

For the next phase, use
[CONTINUOUS_MONITORING_REMAINING_WORK_REPORT.md](./CONTINUOUS_MONITORING_REMAINING_WORK_REPORT.md).
