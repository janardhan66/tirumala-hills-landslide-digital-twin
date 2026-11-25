# Stage 5: Automated Monitoring and 3D Digital Twin Report

**Assessment date:** 22 November 2026

## 1. Outcome

Status: **IMPLEMENTATION-COMPLETE WITH DATA BLOCKERS**

Stage 5 extends the existing project with a database-backed discovery/status
workflow, conservative scheduled tasks, persisted monitoring events,
approval-gated HyP3 polling, unified Cesium status, and dashboard telemetry.
No new satellite data or HyP3 job was submitted.

The system remains:

- **WAITING_FOR_NEW_DATA** for genuine Sentinel-1 acquisitions.
- Running locally only while the laptop and scheduler remain available.
- Preserving the existing pair, terrain, historical data and 7590 observation
  snapshots.

## 2. Database Backup

Stage 5 backup:

- `database/backups/monitoring_stage5_20261122T125106Z.db`

The existing database was not recreated or reset.

## 3. Existing Workspace Preserved

Preserved and reused:

- Stage 1 acquisition/pair management.
- Stage 2 HyP3 submission, status and validation.
- Stage 3 temporal observations and SBAS guard.
- Stage 4 waiting-for-new-data discovery.
- Existing pair `PAIR_20261109_20261121`.
- HyP3 job `3889d809-88a3-4a93-89a5-258821932737`.
- 7590 existing observation snapshots.
- 7590 Stage 3 temporal observation records.
- Existing terrain mesh and Cesium pair textures/models.
- Existing empirical risk formula and dashboard tabs.

## 4. Automated Sentinel-1 Discovery

Status: **PASS**

The existing CDSE search integration was reused and wrapped in a metadata-only
discovery event:

- No full acquisition ZIP download.
- No HyP3 submission.
- Duplicate IDs are excluded.
- New IDs are reported separately.

Live Stage 5 discovery for 29 October to 22 November 2026:

- Products found: 2
- Duplicate products: 2
- Genuine new acquisitions: 0
- Latest acquisition date: 21 November 2026
- Final status: `WAITING_FOR_NEW_DATA`

Discovery events are persisted in
`monitoring_discovery_events` and monitoring events are persisted in
`monitoring_events`.

## 5. Scheduler

Status: **PASS, local execution only**

The existing APScheduler was extended with:

- `sentinel1_discovery`: discovery every 24 hours.
- `hyp3_status_check`: existing-job polling every 1 hour.
- `stage5_status_export`: unified JSON export every 5 minutes.
- `pipeline_trigger`: existing master pipeline every configured 6 hours.

Each scheduled task has `max_instances=1`, coalescing and a concurrency lock.
The existing scheduler was observed running with PID 25856 and a status file.

Monitoring is not available when the laptop is off or disconnected.

## 6. Pair Eligibility and HyP3 Approval

Status: **PASS for safeguards / WAITING_FOR_NEW_DATA for live candidates**

The existing strict Stage 1 pair selector remains:

- Same relative orbit.
- Compatible orbit direction.
- IW/SLC compatibility.
- Spatial overlap.
- 6-36 day configured baseline.
- No duplicate pair.
- Valid local downloaded SLC requirement.

No candidate pair was available. The existing HyP3 `submit_approved_pair`
approval gate remains in effect:

- 20x4 GAMMA cost: 10 credits where exposed.
- No job submission in Stage 5.
- No duplicate job submission.

## 7. HyP3 Job and Product Monitoring

Status: **PASS for existing job / NOT TESTED for new outputs**

Existing job `3889d809-88a3-4a93-89a5-258821932737`:

- Status: `SUCCEEDED`
- Pair: `PAIR_20261109_20261121`
- Output status: `VALID`
- Status history persisted in SQLite.

No new completed pair was available. ZIP integrity and raster validation
behavior from previous stages remains implemented.

## 8. Temporal Network and SBAS Readiness

Status: **PARTIAL**

The Stage 3 network remains:

- 5 nodes
- 3 registered pair edges
- 1 quality-valid edge
- 4 disconnected components
- 7590 temporal observations
- 5034 valid temporal observations

Real SBAS readiness: false.
Cumulative displacement: `INSUFFICIENT_DATA`.
Velocity: `VELOCITY_NOT_AVAILABLE`.

No cumulative displacement or velocity was fabricated.

## 9. 3D Digital Twin

Status: **PASS**

Existing 3D functionality remains available:

- Real local project DEM.
- EPSG:32644 terrain alignment.
- Cesium terrain meshes.
- 09-21 November 2026 LOS pair.
- Coherence and existing evidence layers.
- Historical GSI and AOI assets.
- Timeline controls.
- Cell/raycast lookup.

The existing live pair is explicitly labelled relative LOS, not vertical
displacement or a velocity map.

## 10. Unified Dashboard

Status: **PASS**

The existing Streamlit monitoring tab now reports Stage 5 status:

- Overall status.
- New acquisitions.
- Candidate pairs.
- Valid SBAS edges.
- Discovery status.
- Latest processed acquisition.
- Real SBAS readiness.
- Velocity availability.

The existing 3D Digital Twin remains served through Cesium and Streamlit.

## 11. Unified Cesium Status

Status: **PASS**

Unified JSON:

- `viewer/cesium/data/stage5_monitoring_status.json`

It is generated from database and scheduler data. It includes:

- Overall monitoring status.
- Discovery status.
- Scheduler status.
- Processing counts.
- Network counts.
- Real SBAS readiness.
- Latest valid observation.
- Data freshness timestamp.

The file was returned successfully over the local Cesium HTTP server.

## 12. Notifications

Status: **PARTIAL**

Event types are logged in `monitoring_events`:

- Discovery.
- Status export.
- Existing alert paths.

Telegram and SMTP delivery are optional and remain unverified through live
delivery. No notification success is claimed unless provider confirmation
exists.

## 13. Testing

Full suite:

- 100 passed.
- 6 subtests passed.
- 6 warnings.

Stage 5 focused tests:

- 16 passed.

Test coverage includes:

- Discovery event persistence.
- Status JSON shape.
- Notification local audit.
- Scheduler job registration.
- Restart and overlap safeguards.
- Existing pair and temporal preservation.
- Insufficient-SBAS guards.

## 14. External API Status

| External service | Status |
|---|---|
| CDSE metadata discovery | PASS, live |
| CDSE full SLC download | PARTIAL/BLOCKED |
| HyP3 existing job polling | PASS |
| HyP3 new submission | NOT TESTED/no eligible pair |
| NASA GPM IMERG | BLOCKED by HTTP 401 |
| Telegram/SMTP | NOT TESTED |
| Gemini | LIVE TESTED earlier |

## 15. Local Run Instructions

Start Streamlit:

```powershell
python -m streamlit run dashboard/app.py
```

Start Cesium:

```powershell
python scripts/serve_3d_viewer.py
```

Start scheduler:

```powershell
python automation/scheduler.py start
```

Check status:

```powershell
python automation/scheduler.py status
python scripts/export_stage5_status.py
python scripts/export_stage5_status.py --discovery
```

The discovery-only command does not download products or submit HyP3 jobs.

## 16. Modified and Added Files

Key additions:

- `src/monitoring/stage5.py`
- `src/monitoring/notifications.py`
- `scripts/export_stage5_status.py`
- `tests/test_stage5_monitoring.py`
- `viewer/cesium/data/stage5_monitoring_status.json`

Existing files reused:

- `automation/scheduler.py`
- `automation/pipeline.py`
- `src/data/db.py`
- `scripts/process_insar.py`
- `scripts/manage_multi_temporal.py`
- `src/analysis/temporal_insar.py`
- `dashboard/tabs_extension.py`
- `viewer/cesium/app.js`

## 17. Component Status Summary

| Component | Status |
|---|---|
| Stage 5 discovery | PASS |
| Scheduled discovery | PASS |
| Scheduler lifecycle | PASS |
| Scheduler restart overlap | PASS |
| Unified status export | PASS |
| CDSE live metadata | PASS |
| Pair candidate workflow | WAITING_FOR_NEW_DATA |
| HyP3 new submission | NOT TESTED |
| Completed-product integration | PASS for existing pair |
| SBAS real inversion | NOT READY |
| Dashboard database metrics | PASS |
| Cesium status | PASS |
| Real 3D terrain | PASS |
| Telegram/SMTP live delivery | NOT TESTED |
| Full test suite | PASS |

## 18. Remaining Limitations

- No genuine new acquisition or candidate pair was found.
- No additional real InSAR pair has been processed.
- Real SBAS cumulative displacement and velocity are unavailable.
- CDSE full SLC download remains incomplete.
- NASA IMERG live retrieval remains blocked by HTTP 401.
- Telegram/SMTP delivery was not live-tested.
- Monitoring is not active while the laptop is off or the scheduler daemon is stopped.
