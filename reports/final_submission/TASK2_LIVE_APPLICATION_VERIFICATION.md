# Task 2: Live Application Verification

**Verification date:** 23 November 2026  
**Overall status:** PASS WITH LIMITATIONS  
**Runtime scope:** Existing Streamlit and Cesium applications only

## 1. Pre-start inspection

- Workspace: `C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin`
- Canonical Python: `C:\Users\yarra\AppData\Local\Programs\Python\Python313\python.exe`
- Streamlit: 1.55.0
- Streamlit launch command:
  `python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false`
- Cesium launch command:
  `python scripts/serve_3d_viewer.py --open-browser`
- Before start, ports 8501 and 8088 were not occupied.
- No duplicate application instance was started.

## 2. Streamlit verification

- URL: `http://127.0.0.1:8501`
- Health endpoint: HTTP 200
- Process: listening on 127.0.0.1:8501
- Page title: `Tirumala Hills Landslide Monitoring`
- Browser rendering: passed
- Screenshot-style browser verification: passed
- Startup log shows Streamlit deprecation warnings for `use_container_width`; no fatal startup exception.

### Tabs verified

| Tab | Browser result |
|---|---|
| Overview | Loaded; 7,590 grid nodes, 45,554 observation snapshots, 29 rainfall days and 33 active alerts displayed |
| 3D Digital Twin | Loaded; embedded Cesium iframe is visible and responsive |
| Continuous Monitoring | Loaded; rainfall, InSAR, acquisition and retry sections displayed |
| Risk Assessment | Loaded; 40/25/20/15 methodology and what-if simulator rendered |
| Automation Status | Loaded; scheduler running, 6 pending downloads and 10 failed downloads displayed |
| Alerts & Reports | Loaded; 17 critical, 1 warning and 15 advisory alerts displayed |

The Overview also loaded the Gemini component and showed a live/available status area.

## 3. Cesium verification

- URL: `http://127.0.0.1:8088`
- Static server: HTTP 200
- Process: listening on 0.0.0.0:8088
- Browser page title: `Tirumala Hills 3D Digital Twin | Geospatial Landslide Monitoring`
- Main terrain view: loaded
- Map controls: loaded
- Slope layer switching: verified
- Elevation checkbox: verified
- InSAR LOS checkbox: verified
- Camera Overview button: verified
- All three InSAR epoch controls rendered and changed the active epoch:
  - 05-17 August 2026
  - 17-29 August 2026
  - 09-21 November 2026
- GSI reference toggle: rendered
- GSI boundary toggle: rendered
- Terrain inspector: rendered with no selection until terrain click
- Exaggeration control: rendered
- Browser requests for the terrain models and manifests returned HTTP 200.

### Asset requests verified

- Elevation GLB
- Slope GLB
- Aspect GLB
- InSAR LOS GLB
- Coherence GLB
- Risk-zone GLB
- Both August epoch GLBs
- November epoch GLB
- Spatial grid lookup
- GSI GeoJSON
- AOI GeoJSON
- Active alerts GeoJSON
- Temporal registry
- Synchronization status

Only a missing favicon request was observed as HTTP 404. This is a P2 asset issue.

## 4. Backend and database

- Streamlit read the database successfully.
- Cesium read its generated static assets successfully.
- The latest displayed observation date is 2026-11-21.
- Cesium synchronization status was `SYNCHRONIZED`.
- Database counts remained unchanged during runtime verification:
  - observation_snapshots: 45,554
  - risk_history: 2
  - alerts: 33
  - pipeline_logs: 144
  - temporal_insar_observations: 7,590
  - notification_deliveries: 0
- No production database migration or risk-score write was performed by this verification.

## 5. Gemini

- Gemini credential key: present in existing `.env`
- Credential was not exposed.
- Minimal safe live API check: `SUCCESS`
- UI Gemini component: loaded in Overview.
- Browser Gemini response was not submitted because a live conversational exchange is not necessary for the safe runtime connectivity check.

## 6. Notifications

- Telegram credentials: not configured.
- SMTP credentials: not configured.
- Notification deliveries: 0.
- No test message was sent.
- Notification delivery is not live-verified.

## 7. Browser console/startup issues

- Streamlit reports theme sidebar color warnings in browser console.
- Streamlit reports `use_container_width` deprecation warnings.
- Cesium requests a favicon that is absent.
- No fatal Streamlit or Cesium browser rendering error was observed.

## 8. Tests rerun

- Relevant tests: 23 passed, 8 warnings.
- Full-suite result remains the prior verified result: 150 passed, 12 warnings, 6 subtests passed.

## 9. Final gate

**Live applications:** WORKING WITH LIMITATIONS

No P0 issue. P1 notification delivery remains unverified externally. Browser functionality and core application loading passed.
