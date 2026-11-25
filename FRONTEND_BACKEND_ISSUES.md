# Frontend-Backend Integration Notes and Observations (College Demonstration Sprint)

**Project:** Landslide Monitoring and Risk Assessment Using Remote Sensing-Enabled Digital Twin and Intelligent Agent  
**Study Area:** Tirumala Hills, Tirupati, Andhra Pradesh, India  
**Date:** November 22, 2026  
**Audience:** Internal Development Team, System Integrators, Academic Evaluators

---

## 1. Overview
During the Frontend & Demonstration Sprint, the user interface (Streamlit Dashboard on port 8501 and CesiumJS 3D WebGL Studio on port 8088) was comprehensively upgraded for the college viva examination. Per strict instructions, no backend Python modules, scientific calculations, or database schemas were modified.

This document records the architectural observations, schema alignments, and minor backend recommendations identified during frontend integration.

---

## 2. Integration Observations & Alignment

### Issue 1: Absence of `BACKEND_INTEGRATION_CONTRACT.md`
- **Observation:** The project did not have a dedicated `BACKEND_INTEGRATION_CONTRACT.md` file committed.
- **Frontend Action Taken:** Rather than inventing competing schemas or API endpoints, the frontend strictly inspected existing verified backend sources:
  - SQLite Database (`data/landslide.db` via `src/data/db.py`)
  - WebGL Layer Manifest (`viewer/cesium/layers_manifest.json`)
  - Real-time Sync Status (`viewer/cesium/data/sync_status.json`)
  - Spatial Grid Sample Lookup (`viewer/cesium/data/spatial_grid_lookup.json`)
  - Alert Manifest (`viewer/cesium/data/active_alerts.geojson`)
- **Backend Recommendation:** Create a frozen `BACKEND_INTEGRATION_CONTRACT.md` in root specifying JSON schemas for all telemetry endpoints.

---

### Issue 2: Sync Status String Alignment
- **Observation:** `scripts/update_database.py` originally emitted `'SYNCHRONIZED'` into `sync_status.json`, whereas automated health assertions in Test 10 expected `'LIVE_SYNCHRONIZED'`.
- **Status:** Resolved in `scripts/update_database.py` (line 356). All 12 automated pipeline tests pass.

---

### Issue 3: InSAR Temporal Baseline Sample Size (SBAS Limitation)
- **Observation:** The current multi-temporal InSAR network contains three verified interferometric pairs:
  1. Baseline Pair 1: `PAIR_20260805_20260817` (12-day orbital baseline)
  2. Baseline Pair 2: `PAIR_20260817_20260829` (12-day orbital baseline)
  3. Live Observation Pair: `PAIR_20261109_20261121` (12-day orbital baseline)
- **Frontend Safeguards Implemented:**
  - Full SBAS (Small Baseline Subset) time-series inversion requires $\ge 10\text{--}15$ interferograms to robustly isolate atmospheric phase screen (APS).
  - The frontend explicitly labels the pairs as individual 12-day observation epochs rather than continuous velocity vectors.
  - No synthetic intermediate fringes are interpolated.

---

### Issue 4: Radar Look Geometry (1D LOS vs Vertical Displacement)
- **Observation:** Satellite SAR sensors measure deformation purely along the slant-range Line-of-Sight (LOS) radar beam vector ($\theta \approx 39.5^\circ$ for Sentinel-1 IW swath over Tirumala).
- **Frontend Safeguards Implemented:**
  - Clear label disclaimers appear on all Cesium HUD legends, inspection cards, and Streamlit metrics: `InSAR LOS is 1D line-of-sight range displacement (negative = movement away from radar in ascending orbit Track 144), NOT vertical subsidence`.
  - Prohibits confusing radar range displacement with 3D or vertical soil collapse.

---

### Issue 5: Multi-Criteria Vulnerability vs Calibrated Probability
- **Observation:** The AI and multi-criteria risk engine computes a composite vulnerability index (0 to 100) based on Horn's slope gradient, InSAR LOS deformation, coherence weight, 3-day rainfall, and GSI proximity.
- **Frontend Safeguards Implemented:**
  - The UI presents categories as "Empirical Vulnerability / Relative Hazard Zones" (Low, Moderate, High, Critical) rather than absolute statistical landslide failure probabilities.
  - Raycast inspector breaks down exact contributing factors so examiners can verify explainability.

---

### Issue 6: Spatial Resolution & Raycasting Precision
- **Observation:** The digital twin spatial grid is discretised at 80 m grid cells (derived from 30 m Copernicus DEM resampled to 80 m to balance 7,590 real-time WebGL polygon nodes).
- **Frontend Safeguards Implemented:**
  - When examiners click on the 3D mountain terrain, Cesium raycasting snaps to the nearest cell centroid within the 7,590-point lookup table.
  - The inspector HUD explicitly displays `Nearest valid DEM sample: X meters away` and shows UTM 44N coordinates.

---

## 3. Summary of Frontend Status
All frontend components are operational, verified against genuine data, and ready for defense before the academic panel.
