# Task 3: End-to-End Functional Test Report

**Execution date:** 23 November 2026  
**Overall status:** PASS WITH LIMITATIONS

## 1. Streamlit interactions

| Control | Expected | Actual | Result |
|---|---|---|---|
| Tab navigation | Switch among six tabs | Overview, 3D, Monitoring, Risk, Automation and Alerts tabs all switched successfully | PASS |
| Overview metrics | Show live stored counts | 7,590 nodes, 45,554 snapshots, 29 rainfall days, 33 alerts rendered | PASS |
| 3D Cesium embed | Load existing Cesium inside dashboard | Embedded Cesium page and controls rendered | PASS |
| Continuous monitoring | Show acquisition/rainfall/InSAR status | Latest S1 and InSAR states, pending/failed counts and rainfall series rendered | PASS |
| Risk simulator | Display and recalculate the empirical what-if model | Formula and four sliders rendered; no model or weight change was made | PASS |
| Automation status | Show scheduler/pipeline state | Running (6h), completed pipeline and download queue status rendered | PASS |
| Alerts | Show registered alert history | 33 records rendered: 17 critical, 1 warning, 15 advisory | PASS |
| Gemini text submit | Send project question and receive grounded response | Input and Ask AI control were exercised; relevant response appeared | PASS |
| Refresh/reload | Reload applications safely | Both HTTP endpoints remained available | PASS |

Download/export controls were present. No destructive or production-changing action was triggered.

## 2. Cesium interactions

| Control | Expected | Actual | Result |
|---|---|---|---|
| Initial camera | Render Tirumala overview | Terrain and overview view loaded | PASS |
| Terrain rendering | Render 80 m terrain | Terrain and elevation legend rendered | PASS |
| Elevation/slope/aspect | Toggle the matching layers | Elevation and slope switching worked | PASS |
| InSAR LOS | Switch to LOS and epoch-specific data | LOS, coherence and epoch controls rendered; pair selection changed active epoch | PASS |
| Coherence | Toggle quality coherence | Coherence control changed active legend and visibility state | PASS |
| Risk zones | Toggle empirical zones | Risk-zone control changed active legend and visibility state | PASS |
| GSI points | Toggle historical locations | GSI toggle changed state | PASS |
| GSI boundary | Toggle study-area boundary | Boundary remained visible and state was responsive | PASS |
| Epoch selection | Switch among 05-17 Aug, 17-29 Aug and 09-21 Nov | All three active labels changed successfully | PASS |
| Camera preset Overview | Reset to overview view | Overview button changed active state; reset control is present | PASS WITH LIMITATION |
| Reset View | Return to north-up overview | Button responded; automated browser click could be intercepted by an expanded overlay at some viewport positions | PASS WITH LIMITATION |
| Cell inspector | Click terrain and show matching cell | Inspector UI rendered; automated raycast click was not completed reliably | NOT FULLY VERIFIED |
| Top-down/nadir | Switch camera preset | Camera button state changed in the browser | PASS |

## 3. End-to-end data flow

1. Acquisition metadata exists in `acquisitions`.
2. Three InSAR pairs exist in `insar_pairs`; all are marked processed.
3. Temporal observations exist: 7,590 rows.
4. November quality-valid LOS rows: 5,034 from the project phase status.
5. Spatial observation snapshots: 45,554.
6. Backend and empirical risk scoring remain database-backed.
7. Cesium exported 6 layers and 3 InSAR epochs.
8. Synchronization status: `SYNCHRONIZED`.
9. Latest observation: 2026-11-21.
10. Rainfall remains aggregate/context only; latest rainfall date is 2026-08-29.

The browser did not use Random Forest predictions. It displays the empirical evidence index and benchmark/ML artifacts remain separate.

## 4. Gemini assistant

A live browser question was submitted:

> What factors contribute to the current Tirumala empirical risk assessment, and what are its main limitations?

The Gemini response:

- Used slope, terrain, InSAR and temporal context appropriately.
- Explicitly identified rainfall as temporal context rather than per-cell evidence.
- Stated that the index is not calibrated probability.
- Stated that LOS is not vertical displacement.
- Stated that independent pair phase references prevent cross-pair subtraction.
- Did not expose credentials or invent a new calibrated prediction.

Result: PASS.

## 5. Alerts and notifications

- Alert records: 33.
- Notification deliveries: 0.
- Telegram: unconfigured.
- SMTP: unconfigured.
- No test message was sent.
- Alert status is visible in the dashboard and database.
- Delivery must not be described as successful.

Result: alerts generated and displayed PASS; external delivery NOT VERIFIED.

## 6. Fixes performed

No source-code, database, frontend or risk changes were made.

No P0 fix was required.

## 7. Regression tests

- Relevant integration tests: 23 passed, 8 warnings.
- Full suite: 150 passed, 12 warnings, 6 subtests passed.
- Baseline and rerun are unchanged.

## 8. Final checkpoint

1. Streamlit dashboard works interactively: **YES**, with minor deprecation/theme warnings.
2. Cesium works interactively: **YES**, with raycast inspector and overlay-obstruction limitations.
3. Backend provides correct stored data: **YES**, based on unchanged database counts and synchronization status.
4. Gemini assistant works: **YES**, API and browser response verified.
5. Alerts are generated correctly: **YES** for database/displayed records; external delivery is NOT VERIFIED.
6. Incomplete features: Telegram/SMTP delivery, pixel-level rainfall, local ground truth, Raycast inspector reliability, and model training/calibration.
7. Final submission readiness: **PASS WITH LIMITATIONS**.
