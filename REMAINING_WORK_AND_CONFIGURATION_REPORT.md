# Remaining Work and Configuration Report

**Assessment date:** 2026-11-22 (local time, UTC+5:30)  
**Current state:** One live HyP3-to-SQLite-to-Cesium workflow is verified.
Repeated unattended monitoring and live raw-SLC/IMERG ingestion remain
incomplete or blocked.

## Verified on 2026-11-22

- Dependencies, including APScheduler and HyP3 SDK, are installed.
- 84 Python tests passed, with 6 subtests passed.
- The canonical Streamlit dashboard responds with HTTP 200 on port 8501.
- The master pipeline dry run completes successfully.
- The scheduler daemon is running with a 6-hour interval.
- Scheduler and pipeline telemetry files are being published.
- Sentinel-1 and Sentinel-2 discovery use the CDSE API safely.
- Missing CDSE/NASA credentials are reported without downloading or
  fabricating products.
- SAFE and Sentinel-2 archive handling is implemented; complete S2 bands are
  clipped and reprojected to the canonical 80 m grid.
- HyP3 job submission, status checking, download extraction, and LOS/coherence
  alignment are implemented behind credential checks.
- HyP3 job `3889d809-88a3-4a93-89a5-258821932737` succeeded and its product
  ZIP was downloaded and integrity-tested.
- Live LOS/coherence rasters were aligned to 69 x 110 cells at 80 m and stored
  for pair `PAIR_20261109_20261121`.
- Cesium timeline, texture, GLB model and sync status include 21 November 2026.
- Telegram and SMTP delivery functions have credential and response validation.
- Gemini credentials load and live model generation was verified successfully
  with `gemini-3.1-flash-lite`; no secret values are printed.
- Dashboard startup now loads the U-Net lazily, only when uploaded HDF5
  inference or model information is requested.
- Research CSV loaders use a 5-minute Streamlit cache; scheduler and pipeline
  telemetry use a 5-second cache.
- Streamlit file watching is disabled and the local server configuration is
  pinned to `127.0.0.1:8501`.
- CDSE OAuth authentication was validated successfully.
- Live CDSE discovery found one Sentinel-1 product for 20–22 November 2026.
- HyP3 authentication was validated and account job discovery completed
  successfully.
- NASA Earthdata credentials load in the downloader, but Final/Late historical
  file URL probes returned 404 for the configured endpoint/version. The
  rainfall stage remains safely blocked rather than writing synthetic records.

## Blockers to end-to-end operation

1. **CDSE downloads — PARTIAL.** OAuth authentication and live metadata
   discovery are verified. A complete direct raw-SLC download did not finish;
   the invalid 3104964608-byte reference partial archive was quarantined.
   Final range/size/ZIP/resume verification needs one completed download.
2. **NASA IMERG retrieval — BLOCKED.** CMR collection and `.nc4` granule
   discovery are implemented and official Late granule metadata was found.
   GES DISC returned HTTP 401 with the configured Earthdata session. Existing
   rainfall rows are preserved and no rainfall was fabricated.
3. **Sentinel SAFE preprocessing — PARTIAL.** SAFE/Sentinel-2 archive
   handling is implemented with integrity and temporary extraction, but a
   completed raw Sentinel-1 full download and complete S2 band set are still
   required for end-to-end preprocessing.
4. **Automatic InSAR processing — PARTIAL.** SNAP GPT is present
   at `C:\Program Files\esa-snap\bin\gpt.exe` and `hyp3_sdk` is installed.
   `process_insar.py` contains a SNAP graph scaffold and manual HyP3
   submit/status helpers, but the scheduled `process_new_insar_pairs()` path
   only checks prerequisites and does not call either processor or select and
   submit new pairs. The SNAP graph does not unwrap phase; neither path
   completes validated LOS/coherence extraction, alignment, database
   provenance, and Digital Twin integration for new scenes. No real InSAR job
   was submitted. Do not interpret raw SAR differences as displacement or LOS
   as vertical displacement.
5. **Current evidence and 3D freshness — STALE.** The latest stored observation
   and rainfall dates are 2026-08-29. The local Cesium lookup is synchronized
   to existing records, not a newly downloaded or processed product.
6. **U-Net local inference — BLOCKED for operational use.** The checkpoint
   loads in offline tests, and its 14-channel shape is exercised. Complete
   aligned Sentinel-2 input is absent, so the pipeline skips inference.
   Training/inference normalization compatibility and Tirumala-specific
   validation remain unverified. Keep zero-fill experimental mode disabled for
   operational predictions.
7. **Risk/alert freshness — LIMITED.** Historical risk and alerts exist in
   SQLite, but no new observation was processed in this pass. Existing
   sensitivity/risk classes are relative evidence, not calibrated
   probabilities or future-landslide predictions.
8. **Background scheduler — NOT RUNNING.** There is no scheduler status file
   or scheduler-state row. The Task Scheduler helper was parsed but not
   executed; no Windows task was registered.
9. **Notifications — NOT CONFIGURED/TESTED.** Telegram bot/chat credentials
   and SMTP username/password/recipient are absent. Alert email/Telegram
   delivery was not attempted.
10. **Gemini — PARTIALLY CONFIGURED.** `GEMINI_API_KEY` is present in the
    local environment without its value being read or displayed, and the
    `google-genai` 3.6.1 SDK imports successfully. No Gemini request was made,
    so key validity, model availability, quota, and API response behavior are
    unverified.

Do not claim 100% completion until a new real product has been discovered,
downloaded, preprocessed, scientifically analyzed, stored, and reflected in
the Cesium viewer with verifiable provenance.

## Account and credential setup

Create or use the following accounts, then enter credentials locally in the
project-root `.env`. Never commit `.env`, print secret values, or send them in
chat.

### Copernicus Data Space Ecosystem (Sentinel-1/2)

- Account: [Copernicus Data Space](https://dataspace.copernicus.eu/)
- Register, verify the account, and use the same credentials for CDSE OData
  authentication.
- Set:

  ```dotenv
  CDSE_USERNAME=your_account_email
  CDSE_PASSWORD=your_password
  ```

### NASA Earthdata Login (IMERG and ASF HyP3)

- Account: [NASA Earthdata registration](https://urs.earthdata.nasa.gov/users/new)
- Authorize the NASA GES DISC application for IMERG access. HyP3 requires an
  Earthdata account as well; no real HyP3 job was submitted in this pass.
- Set:

  ```dotenv
  EARTHDATA_USERNAME=your_earthdata_username
  EARTHDATA_PASSWORD=your_password
  ```

### Gemini project Q&A

- Manage an API key through [Google AI Studio](https://aistudio.google.com/apikey).
- Set `GEMINI_API_KEY` in `.env`. A variable is already present in the local
  environment; retain the value privately and check its validity/quota in the
  provider console. No API request was made during this work.

### Optional alert notifications

- Telegram: create a bot with BotFather and configure `TELEGRAM_BOT_TOKEN`
  and `TELEGRAM_CHAT_ID`.
- Email: configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
  `SMTP_PASSWORD`, and `ALERT_EMAIL_TO`. Use a provider-approved SMTP
  credential/app password.
- Delivery is not considered configured or tested until a test alert is
  explicitly approved and delivered.

The provided `.env.example` lists these keys and
`MONITORING_INTERVAL_HOURS=6`. If `.env` already exists, do not overwrite it
with the template.

## Windows commands

Run commands from the project root:

```powershell
Set-Location C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin
```

Install dependencies into the existing virtual environment when needed:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `.env` does not exist, create it once and edit it locally; do not overwrite
an existing file:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Start the background scheduler (first cycle begins at startup, then follows
the configured interval):

```powershell
.\venv\Scripts\python.exe automation\scheduler.py start
```

Register current-user sign-in startup in Windows Task Scheduler (this changes
the Windows task configuration only when run; it was not run during
verification):

```powershell
.\scripts\register_windows_task.ps1 -PythonPath "$PWD\venv\Scripts\python.exe"
```

The scheduled task starts after the user signs in; this is not a service that
runs before login. The laptop must stay powered on and connected to the
internet for local monitoring.

Start the Streamlit dashboard:

```powershell
.\venv\Scripts\python.exe -m streamlit run dashboard\app.py --server.port 8501
```

Start the CesiumJS 3D viewer server in a separate terminal:

```powershell
.\venv\Scripts\python.exe scripts\serve_3d_viewer.py
```

Trigger one manual pipeline run:

```powershell
.\venv\Scripts\python.exe automation\pipeline.py
```

This may attempt remote access and update pipeline/database records. Missing
credentials and unimplemented processing stages will be reported; it is not
an end-to-end success demonstration.

Run the offline regression tests:

```powershell
.\venv\Scripts\python.exe -m pytest -q tests\test_data_ingestion.py tests\test_insar_pipeline.py tests\test_risk_engine.py tests\test_preprocess_data.py tests\test_end_to_end.py::TestDatabaseAndCatalog::test_catalog_duplicate_detection tests\test_end_to_end.py::TestMasterPipelineDryRun tests\test_layer_exporter.py tests\test_temporal_registry.py tests\test_unet_pipeline.py tests\test_scheduler.py tests\test_digital_twin_3d.py tests\test_cesium_builder.py
```

The live integration file `tests\test_automated_monitoring_workflow.py` was
not run: it queries remote CDSE and the project database and expects local
credentials/state. Review its effects and ensure credentials and test
isolation before running it.

## Required next implementation and verification steps

- Implement SAFE extraction, product-specific band handling, AOI clipping,
  EPSG:32644 reprojection, reference-grid alignment, and idempotent
  per-product processing records.
- Complete a real InSAR pipeline (SNAP graph or HyP3 orchestration), including
  pair selection, scientific processing, LOS/coherence outputs, QC metrics,
  and provenance. Do not fabricate displacement products.
- Wire successful new outputs through feature extraction, evidence risk,
  alerts, database history, and Cesium export; test that failed/incomplete
  products cannot become the latest successful observation.
- Validate the checkpoint's 14-channel ordering and normalization against
  its training pipeline and a real, complete aligned local input. Preserve
  Landslide4Sense validation metrics with their dataset context.
- Run credentialed discovery/download and rainfall ingestion; record actual
  dates, product IDs, checksums/file sizes, and non-secret error details.
- Start the scheduler and verify its next-run telemetry. Register the
  Windows task only with the user's approval.
- Perform a browser-level dashboard/Cesium refresh test after a successful
  new dataset is processed. Verify the observation date, layer provenance,
  risk assessment, alerts, and freshness in the UI.
- Test Gemini only after confirming API use is authorized; verify live DB
  grounding without exposing the key. Test optional Telegram/SMTP delivery
  only with the user's approval.
