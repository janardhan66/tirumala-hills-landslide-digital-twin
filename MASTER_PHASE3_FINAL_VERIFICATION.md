# Master Phase 3 Final Test Verification

**Assessment date:** 22 November 2026

## Result

The exact full-suite result for the latest Phase 3 verification run is:

- Passed: 117
- Failed: 0
- Skipped: 0 (the captured output showed no skipped-test entry)
- Warnings: 6
- Subtests passed: 6

## Evidence

The captured terminal output for the final Phase 3 run states:

```text
117 passed, 6 warnings, 6 subtests passed
```

The pytest cache has no entries in `lastfailed`, and the full-suite terminal
output contains no failed-test section.

The pytest cache's `nodeids` list contains 118 collected test identifiers.
The cache can retain stale identifiers and does not itself prove passed,
failed or skipped counts for a run. It is not used as the primary count.

## Focused Phase 3 Verification

The captured focused Phase 3 run states:

- 17 passed
- 6 subtests passed

The focused test file is
`tests/test_phase3_gis_integration.py`.

## Discrepancy Resolution

The report initially recorded 114 passed. Later verification output explicitly
recorded 117 passed. The report has been corrected to 117.

The 114 count is treated as an earlier intermediate run, not the final
Phase 3 run.

## Scope

No tests were rerun for this reconciliation.
No source code, database records, GIS datasets, GLBs, textures, InSAR products
or application configuration were modified.

No Phase 4 work was started.
