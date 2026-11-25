# Master Final Demo Guide

**Assessment date:** 22 November 2026

## 1. Start URLs

- Streamlit dashboard: http://127.0.0.1:8501
- Cesium 3D viewer: http://127.0.0.1:8088

Both applications were verified at HTTP 200.

## 2. Recommended Dashboard Demonstration

1. Open the Streamlit dashboard.
2. Show the overview:
   - 7590 grid nodes.
   - 45554 observation snapshots.
   - 29 rainfall days.
   - 33 alerts.
3. Open **3D Digital Twin**:
   - Elevation terrain.
   - Slope/aspect layers.
   - LOS/coherence where applicable.
4. Open **Continuous Monitoring**:
   - Acquisition history.
   - Pair history.
   - Waiting-for-new-data state.
5. Open **Risk Assessment**:
   - Explain the 40/25/20/15 empirical formula.
   - Explain missing factors and evidence coverage.
6. Open **Alerts & Reports**:
   - Show local evidence alerts.
   - Do not present alerts as confirmed landslide warnings.

## 3. Recommended Cesium Demonstration

1. Open the Cesium viewer.
2. Confirm the Elevation layer is visible.
3. Toggle Slope, Aspect, LOS and Coherence.
4. Select different processed InSAR acquisition pairs.
5. Show the GSI approximate historical points.
6. Observe the banner:
   - Demonstration-ready status.
   - Empirical evidence index.
   - Single-pair temporal inversion limitation.

## 4. Required Scientific Disclaimers

Say explicitly:

- The risk index is empirical, not calibrated probability.
- LOS is relative line-of-sight displacement.
- Low coherence is insufficient evidence, not zero movement.
- Missing data was not replaced with zero.
- Cumulative displacement and velocity are not available from the single
  valid real pair network.
- GSI coordinates are approximate map-derived locations.
- Rainfall is study-area aggregate context.
- U-Net output is benchmark-only and not Tirumala-ground-truth validated.
- Telegram and SMTP delivery are not externally verified.

## 5. Screenshots

- [Dashboard screenshot](outputs/reports/MASTER_FINAL_DASHBOARD_SCREENSHOT.png)
- [Cesium screenshot](outputs/reports/MASTER_FINAL_CESIUM_SCREENSHOT.png)

## 6. Known Demonstration Limitations

- No new satellite download.
- No new HyP3 submission.
- GES DISC rainfall access returns HTTP 401.
- No real-time rainfall or Sentinel-2 refresh.
- No calibrated landslide probability.
- No confirmed landslide warning.
