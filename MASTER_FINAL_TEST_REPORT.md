# Master Final Test Report

**Assessment date:** 22 November 2026

## 1. Focused Emergency Integration Tests

Final focused run:

- 25 passed.
- 6 subtests passed.
- 2 warnings.
- 0 failed.

Coverage:

- Unified status export.
- Preservation counts.
- Existing empirical formula.
- Missing-factor exclusion.
- Risk explainability.
- Cesium manifest assets.
- Missing-rainfall alert guard.
- Existing risk, Cesium and Stage 5 tests.

## 2. Full-Suite Results

Final pytest run:

- 142 passed.
- 6 subtests passed.
- 6 warnings.
- 0 failed.

Warnings:

- One existing test-return warning in `test_gemini.py`.
- Existing datetime.utcnow deprecation warnings.
- Existing alert/risk database datetime warning.

## 3. Dashboard Verification

Streamlit HTTP:

- Status: 200.
- Browser title: Tirumala Hills Landslide Monitoring.
- Spatial observations: 2650.
- Historical pairs: 2569.
- Active alerts: 33.
- Screenshot saved.

## 4. Cesium Verification

Initial browser verification found:

- Literal NaN in generated JSON.
- Undefined Stage 3/5 status globals.

Both issues were fixed and reloaded.

Final browser verification:

- Viewer initialized.
- Evidence layers loaded.
- Temporal InSAR controls loaded.
- GSI controls loaded.
- Final status banner displayed.
- Screenshot saved.

## 5. JSON Validation

All Cesium JSON files under `viewer/cesium` passed strict `json.load` parsing
after replacing invalid NaN values with JSON null.

## 6. Database Integrity

Read-only verification retained:

- 20 acquisitions.
- 3 InSAR pairs.
- 29 rainfall records.
- 45554 observation snapshots.
- 7590 temporal observations.
- 7590 spatial-grid records.
- 33 alerts.

No historical table or scientific record was deleted or overwritten.
