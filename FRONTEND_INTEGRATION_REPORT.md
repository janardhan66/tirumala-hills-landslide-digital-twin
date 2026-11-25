# FRONTEND INTEGRATION & COLLEGE VIVA DEMONSTRATION REPORT

**Project:** Landslide Monitoring and Risk Assessment Using Remote Sensing-Enabled Digital Twin and Intelligent Agent  
**Study Area:** Tirumala Hills, Tirupati, Andhra Pradesh, India  
**Target Audience:** Academic Evaluators, External Examiners, Project Guide  
**Release:** Frontend Sprint — College Viva Edition  
**Date:** November 22, 2026  

---

## 1. Executive Summary

This report confirms the completion of the Frontend, Cesium 3D Digital Twin, and Demonstration Presentation sprint for the Tirumala Hills Landslide Digital Twin. Both primary interfaces—the **Streamlit Analytical Dashboard** (`http://localhost:8501`) and the **CesiumJS 3D WebGL Digital Twin Studio** (`http://localhost:8088`)—have been upgraded to an integrated, evidence-backed presentation platform designed specifically for college examination panels.

### Key Verification Highlights
1. **Scientific Integrity Preserved:** Strict constraints adhered to—no backend calculations modified, no synthetic landslides simulated, no vertical subsidence falsely claimed (explicitly documented as 1D radar Line-of-Sight), and no calibrated probabilities overstated (documented as empirical multi-criteria susceptibility).
2. **Dual-Application Sync:** Cesium HTTP server (port 8088) and Streamlit dashboard (port 8501) run concurrently with real-time JSON heartbeat synchronization (`sync_status.json`).
3. **Multi-Layer 3D Terrain:** 80m Copernicus DEM GLB mesh accurately overlaying horn's slope, aspect, Sentinel-1 InSAR fringes, quality coherence ($\gamma \ge 0.50$), multi-factor hazard zones, and 15 Geological Survey of India (GSI) historical landslide locations.
4. **Interactive Examiner Raycasting:** Click-to-query raycasting computes ground coordinates, DEM elevation, Horn's slope angle, observation-epoch InSAR LOS displacement, radar coherence, rolling 3-day precipitation, and categorical risk evidence on the fly.
5. **Demonstration Architecture:** 6-tab logical sequence with 5-minute defense guideline chips embedded at the top of the application.

---

## 2. System Architecture & Demonstration Views

```
+--------------------------------------------------------------------------------------------------+
|                            COLLEGE VIVA DEMONSTRATION SUITE (5-MIN DEFENSE)                      |
+--------------------------------------------------------------------------------------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                                                               |
         v                                                                               v
+----------------------------------+                            +----------------------------------+
|  STREAMLIT ANALYTICAL DASHBOARD  |                            |   CESIUMJS 3D DIGITAL TWIN      |
|     (http://localhost:8501)      |                            |     (http://localhost:8088)      |
+----------------------------------+                            +----------------------------------+
| 1. Overview & Gemini AI Agent    |                            | • 80m Copernicus DEM Mesh (GLB)  |
| 2. 3D Digital Twin Studio        |                            | • 6 Dynamic Evidence Presets     |
| 3. Continuous Sentinel/Rainfall  | <==== Live Sync Heartbeat ====>| • InSAR Epoch Quick Pills        |
| 4. Risk Simulation & What-If     |       (sync_status.json)   | • 15 Historical GSI Points (3D)  |
| 5. APScheduler Automation Status |                            | • Raycasting Click Inspector HUD |
| 6. Decision Support & Alerts     |                            | • 360° Cinematic Drone Tour      |
+----------------------------------+                            +----------------------------------+
```

---

## 3. Detailed Feature Breakdown

### A. CesiumJS 3D WebGL Digital Twin (`viewer/cesium/`)
- **Topographic Base:** Real 80m Copernicus DEM GLTF/GLB terrain model centered at UTM 44N ($13.68^\circ\text{N}, 79.35^\circ\text{E}$).
- **Layer Preset Quick-Bar:** One-click toggles between 6 primary evidence layers:
  1. *Elevation:* 192 m to 884 m color ramp.
  2. *Horn's Slope:* $0^\circ$ to $45^\circ+$ gradient identifying steep escarpment flanks along the ghat roads.
  3. *Aspect:* Azimuthal slope orientation.
  4. *InSAR LOS Displacement:* Multi-temporal interferometric radar look fringes (negative = motion away from radar in ascending track 144).
  5. *Radar Coherence ($\gamma$):* Interferometric fringe quality index ($0.0$ to $1.0$).
  6. *Risk Zones:* Empirical multi-factor hazard classifications.
- **InSAR Multi-Temporal Observation Epochs:**
  - Fast-switching pill controls for verified interferometric pairs:
    - Baseline Epoch 1: `PAIR_20260805_20260817` (12-day baseline)
    - Baseline Epoch 2: `PAIR_20260817_20260829` (12-day baseline)
    - Live Epoch 3: `PAIR_20261109_20261121` (12-day baseline)
- **Interactive Raycasting Terrain Inspector:**
  - Real-time client-side spatial lookup across 7,590 terrain points.
  - Automatic expansion upon clicking any mountain surface point.
  - Multi-Factor Risk Evidence breakdown explaining the contributions of slope steepness, radar LOS range displacement, radar coherence, and NASA GPM precipitation.
  - Prominent scientific notice explaining radar geometry and empirical vulnerability.
- **Cinematic & Visual Controls:**
  - 360° Drone Orbit flyover around the Tirumala ridge.
  - Dynamic solar lighting modes (Daylight, Sunset, Cyber Night).
  - Landmark beacons for 1st Ghat Road (Ascending), 2nd Ghat Road (Descending), Tirumala Temple Township, and Critical Escarpment Flanks.
  - Vertical exaggeration slider ($1.0\times$ to $5.0\times$) with real-time vector height updating.

### B. Streamlit Analytical Dashboard (`dashboard/`)
- **College Viva Banner:** High-visibility banner highlighting the recommended 5-minute defense sequence for the examination committee.
- **Tab 1 — Overview & Gemini AI Assistant:** Project executive summary, study area geomorphological context, and the interactive Google Gemini LLM agent for natural-language spatial queries.
- **Tab 2 — 3D Digital Twin Studio:** Embedded responsive CesiumJS WebGL container with direct link button, paired with analytical Plotly 3D mesh and 2D Leaflet GIS map.
- **Tab 3 — Continuous Remote Sensing Monitoring:** Real-time Copernicus Data Space Sentinel-1 discovery records, multi-temporal InSAR baseline network graph, and NASA GPM IMERG 1-day, 3-day, 7-day, and 14-day rainfall time series.
- **Tab 4 — Risk Assessment & What-If Simulator:** Multi-factor empirical hazard breakdown, GSI spatial validation table, and interactive slider-driven precipitation/displacement simulation engine.
- **Tab 5 — Automation Status:** Real-time APScheduler heartbeat telemetry, lockfile verification, and pipeline stage health.
- **Tab 6 — Decision-Support Alerts & Reports:** Evidence-grounded spatial alerts with explicit observation dates, severity badges, and human-in-the-loop review actions.

---

## 4. Completed, Partial, and Blocked Features Table

| Feature / Component | Status | Implementation Details | Scientific / Operational Notes |
| :--- | :---: | :--- | :--- |
| **Streamlit 6-Tab Interface** | **COMPLETED** | Verified across all 6 tabs in `dashboard/app.py` & `dashboard/tabs_extension.py` | Full navigation flow with examiner sequence |
| **College Viva Banner & Guide** | **COMPLETED** | Embedded above main navigation with 5-minute defense chips | Clear structural guide for presentations |
| **Cesium 3D Terrain Rendering** | **COMPLETED** | 80m Copernicus DEM GLB mesh loaded via CesiumJS WebGL | Accurate UTM 44N geolocation |
| **Layer Preset Quick-Bar** | **COMPLETED** | Grid of 6 buttons (Elevation, Slope, Aspect, LOS, Coherence, Risk) | Solo/focus switching with synchronized legends |
| **GSI Historical Hazard Points** | **COMPLETED** | 15 verified points loaded from `tirumala_gsi_points.geojson` | Positioned with DEM-adaptive terrain heights |
| **InSAR Observation Epoch Selector** | **COMPLETED** | Quick-select pills + slider for all 3 verified Sentinel-1 pairs | Auto-activates LOS layer and updates labels |
| **Terrain Raycasting Inspector** | **COMPLETED** | ScreenSpaceEventHandler raycasting + 7,590-cell lookup | Auto-unhides on click with evidence breakdown |
| **Scientific Disclaimers & Notes** | **COMPLETED** | Permanent disclaimers in HUD, Inspector, and Dashboard | Strictly prevents misinterpreting LOS or risk |
| **Live Sync Telemetry Badge** | **COMPLETED** | In-memory polling of `sync_status.json` with animated indicator | No full page reload required |
| **Cinematic Drone Tour & Lighting** | **COMPLETED** | Orbit flyover around ridge; Day/Sunset/Night presets | Smooth interactive presentation tools |
| **Full SBAS Multi-Year Velocity** | **PARTIALLY WORKING** | 3 observation pairs supported; baseline pairs visualized | True SBAS time-series requires $\ge 10\text{--}15$ pairs |
| **Real-Time Continuous Satellite Video** | **NOT IMPLEMENTED** | Documented as physically impossible for orbital SAR | Satellite revisit cycle is fixed at 12 days |

---

## 5. Recommended 5-Minute Demonstration Walkthrough for Viva

When presenting to your guide and examiners, follow this structured script:

1. **Minute 1: Introduction & Objective (Tab 1)**
   - Introduce the project: Continuous landslide monitoring for Tirumala Hills using satellite remote sensing (Sentinel-1 SAR, Copernicus DEM, NASA GPM IMERG).
   - Show the 80m study area grid (7,590 cells) covering both Ghat Roads and the Tirumala township.
   - Ask the Gemini AI agent a spatial question (e.g., *"What is the geomorphological vulnerability along the 2nd Ghat Road?"*).

2. **Minute 2: The 3D Digital Twin (Tab 2 / Cesium Studio)**
   - Open the 3D Digital Twin (`http://localhost:8088`).
   - Demonstrate the Layer Presets: Click **Elevation** ➔ **Slope** (pointing out steep escarpments $>25^\circ$) ➔ **InSAR LOS** ➔ **Risk Zones**.
   - Show the **InSAR Observation Epochs**: Switch between `05–17 Aug`, `17–29 Aug`, and `09–21 Nov 2026`.
   - Click a mountain flank near 2nd Ghat Road to show the **Raycast Terrain Inspector** automatically populating with coordinates, elevation, slope, InSAR LOS (-14.2 mm), and the Multi-Factor Evidence Breakdown.

3. **Minute 3: Continuous Remote Sensing & Rainfall (Tab 3)**
   - Show automatic Sentinel-1 product discovery from Copernicus Data Space Ecosystem.
   - Show the NASA GPM IMERG rolling rainfall charts (1-day, 3-day, 7-day, 14-day precipitation).
   - Point out that all data reflects genuine satellite acquisition dates.

4. **Minute 4: Risk Assessment & What-If Simulation (Tab 4)**
   - Explain the multi-criteria index (Horn's slope + InSAR deformation + coherence + antecedent rainfall).
   - Show the GSI validation table confirming historical spatial alignment across 15 hazard locations.
   - Adjust the What-If simulation slider to demonstrate how heavy monsoon precipitation triggers escalated hazard zones.

5. **Minute 5: Automation Telemetry & Evidence-Based Alerts (Tabs 5 & 6)**
   - Show the background APScheduler telemetry confirming scheduled polling.
   - Show the active warning alerts generated with specific observation dates.
   - Conclude with the scientific rigor statement: empirical susceptibility, 1D radar LOS look geometry, and 12-day orbital cadence.
