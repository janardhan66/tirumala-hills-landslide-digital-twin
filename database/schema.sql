-- ============================================================
-- Tirumala Hills Landslide Digital Twin — SQLite Database Schema
-- ============================================================
-- Database: monitoring.db
-- Engine:   SQLite 3 with JSON1 extension
-- Purpose:  Store all satellite products, observations, risk assessments,
--           alerts, and pipeline execution history with full audit trail.
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. Satellite Product Catalog
-- ============================================================
CREATE TABLE IF NOT EXISTS acquisitions (
    acquisition_id   TEXT PRIMARY KEY,          -- Copernicus product UUID or ASF granule ID
    satellite        TEXT NOT NULL,             -- 'Sentinel-1', 'Sentinel-2'
    product_type     TEXT NOT NULL,             -- 'SLC', 'GRD', 'S2MSI2A'
    sensor_mode      TEXT,                      -- 'IW', 'MSI'
    orbit_direction  TEXT,                      -- 'DESCENDING', 'ASCENDING'
    orbit_number     INTEGER,
    relative_orbit   INTEGER,
    acquisition_date TEXT NOT NULL,             -- 'YYYY-MM-DD'
    start_time       TEXT,                      -- ISO 8601 timestamp
    end_time         TEXT,
    polarisation     TEXT,                      -- 'VV+VH', 'VV', etc.
    acquisition_timestamp TEXT,
    beam_mode        TEXT,
    spatial_coverage TEXT,
    cloud_cover      REAL,                      -- Sentinel-2 only (percentage)
    footprint_wkt    TEXT,                      -- WKT geometry
    file_path        TEXT,                      -- Local download path
    file_size_mb     REAL,
    checksum_md5     TEXT,
    download_status  TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING, DOWNLOADING, DOWNLOADED, FAILED
    processing_status TEXT NOT NULL DEFAULT 'UNPROCESSED', -- UNPROCESSED, PROCESSING, PROCESSED, FAILED
    error_message    TEXT,
    source_api       TEXT DEFAULT 'CDSE',       -- CDSE, ASF, manual
    metadata_json    TEXT,                      -- Additional JSON metadata
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_acq_satellite_date ON acquisitions(satellite, acquisition_date);
CREATE INDEX IF NOT EXISTS idx_acq_status ON acquisitions(download_status, processing_status);

-- ============================================================
-- 2. InSAR Processing Pairs
-- ============================================================
CREATE TABLE IF NOT EXISTS insar_pairs (
    pair_id              TEXT PRIMARY KEY,      -- e.g., 'PAIR_20260805_20260817'
    reference_acq_id     TEXT NOT NULL,
    secondary_acq_id     TEXT NOT NULL,
    reference_date       TEXT NOT NULL,
    secondary_date       TEXT NOT NULL,
    temporal_baseline_days INTEGER NOT NULL,
    perpendicular_baseline_m REAL,
    processing_mode      TEXT NOT NULL,         -- 'hyp3', 'snap', 'manual'
    processing_status    TEXT NOT NULL DEFAULT 'PENDING',
    hyp3_job_id          TEXT,                  -- HyP3 cloud job ID if applicable
    los_disp_tif         TEXT,                  -- Path to LOS displacement GeoTIFF
    coherence_tif        TEXT,                  -- Path to coherence GeoTIFF
    phase_ref_lat        REAL,
    phase_ref_lon        REAL,
    valid_pixels         INTEGER,
    mean_coherence       REAL,
    quality_notes        TEXT,
    orbit_direction      TEXT,
    relative_orbit       INTEGER,
    orbit_compatibility  TEXT,
    spatial_overlap_percent REAL,
    quality_status       TEXT DEFAULT 'PENDING',
    selection_method     TEXT,
    output_archive       TEXT,
    error_message        TEXT,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(reference_acq_id)  REFERENCES acquisitions(acquisition_id),
    FOREIGN KEY(secondary_acq_id)  REFERENCES acquisitions(acquisition_id)
);

CREATE INDEX IF NOT EXISTS idx_pair_dates ON insar_pairs(reference_date, secondary_date);

CREATE TABLE IF NOT EXISTS temporal_insar_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cell_id TEXT NOT NULL,
    pair_id TEXT NOT NULL,
    reference_date TEXT NOT NULL,
    secondary_date TEXT NOT NULL,
    acquisition_date TEXT NOT NULL,
    los_displacement_m REAL,
    coherence REAL,
    quality_status TEXT NOT NULL DEFAULT 'NOT_TESTED',
    nodata_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    source_raster TEXT,
    processing_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(cell_id) REFERENCES spatial_evidence_grid(cell_id),
    FOREIGN KEY(pair_id) REFERENCES insar_pairs(pair_id),
    UNIQUE(cell_id, pair_id)
);

CREATE INDEX IF NOT EXISTS idx_temporal_insar_cell_date
    ON temporal_insar_observations(cell_id, acquisition_date);

CREATE TABLE IF NOT EXISTS hyp3_job_status_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    status_checked_at TIMESTAMP NOT NULL,
    error_message TEXT,
    payload_json TEXT,
    FOREIGN KEY(pair_id) REFERENCES insar_pairs(pair_id)
);

CREATE INDEX IF NOT EXISTS idx_hyp3_history_job_status
    ON hyp3_job_status_history(job_id, status_checked_at);

-- ============================================================
-- 3. Daily Rainfall Records
-- ============================================================
CREATE TABLE IF NOT EXISTS rainfall_records (
    record_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    record_date      TEXT NOT NULL UNIQUE,     -- 'YYYY-MM-DD'
    daily_mean_mm    REAL NOT NULL,
    daily_max_mm     REAL,
    daily_min_mm     REAL,
    rolling_1day_mm  REAL,
    rolling_3day_mm  REAL,
    rolling_7day_mm  REAL,
    rolling_14day_mm REAL,
    source_product   TEXT DEFAULT 'NASA GPM IMERG V07C',
    source_file      TEXT,                     -- Path to source GeoTIFF
    data_quality     TEXT DEFAULT 'FINAL',     -- FINAL, LATE (NRT), EARLY
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rain_date ON rainfall_records(record_date);

-- ============================================================
-- 4. Spatial Evidence Grid (Persistent Grid Cells)
-- ============================================================
CREATE TABLE IF NOT EXISTS spatial_evidence_grid (
    cell_id          TEXT PRIMARY KEY,         -- 'R{row}_C{col}'
    row_idx          INTEGER NOT NULL,
    col_idx          INTEGER NOT NULL,
    utm_easting      REAL NOT NULL,
    utm_northing     REAL NOT NULL,
    latitude         REAL NOT NULL,
    longitude        REAL NOT NULL,
    elevation_m      REAL NOT NULL,
    slope_deg        REAL NOT NULL,
    aspect_deg       REAL,
    dist_to_gsi_km   REAL,
    terrain_high_evidence INTEGER DEFAULT 0,   -- Boolean flag
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_grid_coords ON spatial_evidence_grid(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_grid_rc ON spatial_evidence_grid(row_idx, col_idx);

-- ============================================================
-- 5. Observation Snapshots (Time-stamped Evidence Per Cell)
-- ============================================================
CREATE TABLE IF NOT EXISTS observation_snapshots (
    snapshot_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    cell_id          TEXT NOT NULL,
    observation_date TEXT NOT NULL,            -- Date of the evidence snapshot
    pair_id          TEXT,                      -- InSAR pair used
    los_disp_m       REAL,
    coherence        REAL,
    los_change_m     REAL,                     -- Delta from previous pair
    rainfall_1day_mm REAL,
    rainfall_3day_mm REAL,
    rainfall_7day_mm REAL,
    rainfall_14day_mm REAL,
    ndvi             REAL,                     -- Sentinel-2 NDVI
    ndvi_change      REAL,                     -- NDVI delta from previous
    unet_confidence  REAL,                     -- U-Net prediction confidence
    unet_positive    INTEGER,                  -- Boolean: U-Net flagged
    risk_score       REAL NOT NULL DEFAULT 0,  -- 0-100
    risk_category    TEXT NOT NULL DEFAULT 'Low', -- Low, Medium, High
    insar_high_evidence INTEGER DEFAULT 0,
    temporal_evidence_flag INTEGER DEFAULT 0,
    data_quality     TEXT DEFAULT 'GOOD',      -- GOOD, PARTIAL, DEGRADED
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(cell_id) REFERENCES spatial_evidence_grid(cell_id),
    FOREIGN KEY(pair_id) REFERENCES insar_pairs(pair_id)
);

CREATE INDEX IF NOT EXISTS idx_obs_cell_date ON observation_snapshots(cell_id, observation_date);
CREATE INDEX IF NOT EXISTS idx_obs_date ON observation_snapshots(observation_date);
CREATE INDEX IF NOT EXISTS idx_obs_risk ON observation_snapshots(risk_category);
CREATE UNIQUE INDEX IF NOT EXISTS ux_observation_snapshot_cell_date
    ON observation_snapshots(cell_id, observation_date);

-- ============================================================
-- 6. Risk History (Aggregated Per Observation Date)
-- ============================================================
CREATE TABLE IF NOT EXISTS risk_history (
    history_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_date TEXT NOT NULL,
    total_cells      INTEGER NOT NULL,
    low_count        INTEGER NOT NULL DEFAULT 0,
    medium_count     INTEGER NOT NULL DEFAULT 0,
    high_count       INTEGER NOT NULL DEFAULT 0,
    mean_risk_score  REAL,
    max_risk_score   REAL,
    -- Transitions from previous observation
    low_to_medium    INTEGER DEFAULT 0,
    low_to_high      INTEGER DEFAULT 0,
    medium_to_high   INTEGER DEFAULT 0,
    medium_to_low    INTEGER DEFAULT 0,
    high_to_medium   INTEGER DEFAULT 0,
    high_to_low      INTEGER DEFAULT 0,
    persistent_high_cells INTEGER DEFAULT 0,
    notes            TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_hist_date ON risk_history(observation_date);

-- ============================================================
-- 7. Intelligent Decision-Support Alerts
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    alert_id         TEXT PRIMARY KEY,         -- UUID
    alert_timestamp  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    trigger_rule     TEXT NOT NULL,            -- Which rule triggered
    severity         TEXT NOT NULL DEFAULT 'INFO', -- INFO, WARNING, CRITICAL
    affected_cells   TEXT,                     -- JSON list of cell_ids
    affected_cells_count INTEGER NOT NULL,
    center_latitude  REAL NOT NULL,
    center_longitude REAL NOT NULL,
    max_risk_score   REAL NOT NULL,
    triggering_indicators TEXT,               -- JSON: which indicators triggered
    observation_date TEXT,
    data_quality     TEXT,
    summary_text     TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    verification_status TEXT DEFAULT 'PENDING', -- PENDING, VERIFIED, FALSE_ALARM, EXPIRED
    verified_by      TEXT,
    verified_at      TIMESTAMP,
    verification_notes TEXT,
    notification_sent INTEGER DEFAULT 0,       -- Boolean
    notification_channel TEXT,                 -- 'email', 'telegram', 'local'
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_status ON alerts(verification_status);
CREATE INDEX IF NOT EXISTS idx_alert_time ON alerts(alert_timestamp);
CREATE UNIQUE INDEX IF NOT EXISTS ux_alert_rule_observation
    ON alerts(trigger_rule, observation_date);

-- ============================================================
-- 8. Pipeline Execution Logs
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_logs (
    log_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL,            -- Unique pipeline run identifier
    stage_name       TEXT NOT NULL,            -- 'sentinel1_check', 'rainfall_download', etc.
    status           TEXT NOT NULL,            -- SUCCESS, WARNING, ERROR, SKIPPED
    started_at       TIMESTAMP,
    completed_at     TIMESTAMP,
    duration_seconds REAL,
    records_processed INTEGER DEFAULT 0,
    message          TEXT,
    error_traceback  TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_log_run ON pipeline_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_log_stage ON pipeline_logs(stage_name, status);

-- ============================================================
-- 9. Scheduler State
-- ============================================================
CREATE TABLE IF NOT EXISTS scheduler_state (
    job_name             TEXT PRIMARY KEY,      -- 'sentinel1_check', 'rainfall_check', etc.
    last_check_time      TIMESTAMP,
    last_success_time    TIMESTAMP,
    last_failure_time    TIMESTAMP,
    last_data_found_date TEXT,                  -- Latest acquisition date discovered
    next_scheduled_time  TIMESTAMP,
    consecutive_failures INTEGER DEFAULT 0,
    total_runs           INTEGER DEFAULT 0,
    total_successes      INTEGER DEFAULT 0,
    total_failures       INTEGER DEFAULT 0,
    is_enabled           INTEGER DEFAULT 1,     -- Boolean
    notes                TEXT,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 10. CesiumJS Layer Registry
-- ============================================================
CREATE TABLE IF NOT EXISTS cesium_layers (
    layer_id         TEXT PRIMARY KEY,
    layer_name       TEXT NOT NULL,
    layer_type       TEXT NOT NULL,            -- 'raster_overlay', 'geojson', 'glb_model', 'czml'
    observation_date TEXT,
    file_path        TEXT NOT NULL,
    bounds_json      TEXT,                     -- JSON: {west, south, east, north}
    metadata_json    TEXT,
    is_active        INTEGER DEFAULT 1,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 11. Sentinel-2 Vegetation Index History
-- ============================================================
CREATE TABLE IF NOT EXISTS vegetation_indices (
    record_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    acquisition_id   TEXT,
    observation_date TEXT NOT NULL,
    cell_id          TEXT NOT NULL,
    ndvi             REAL,
    ndwi             REAL,
    bare_soil_index  REAL,
    land_cover_class TEXT,
    cloud_free       INTEGER DEFAULT 1,       -- Boolean
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(acquisition_id) REFERENCES acquisitions(acquisition_id),
    FOREIGN KEY(cell_id) REFERENCES spatial_evidence_grid(cell_id)
);

CREATE INDEX IF NOT EXISTS idx_veg_cell_date ON vegetation_indices(cell_id, observation_date);

-- ============================================================
-- 12. Stage 5 Monitoring Discovery and Event History
-- ============================================================
CREATE TABLE IF NOT EXISTS monitoring_discovery_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    discovery_started_at TIMESTAMP NOT NULL,
    discovery_completed_at TIMESTAMP,
    status TEXT NOT NULL,
    satellite TEXT NOT NULL DEFAULT 'Sentinel-1',
    search_start TEXT,
    search_end TEXT,
    products_found INTEGER DEFAULT 0,
    duplicate_products INTEGER DEFAULT 0,
    new_acquisitions INTEGER DEFAULT 0,
    latest_acquisition_date TEXT,
    error_message TEXT,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monitoring_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    subject_id TEXT,
    message TEXT NOT NULL,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_monitoring_discovery_created
    ON monitoring_discovery_events(created_at);
CREATE INDEX IF NOT EXISTS idx_monitoring_events_type_created
    ON monitoring_events(event_type, created_at);

-- ============================================================
-- Stage 6 Checkpoint 4: Experimental Feature Engineering
-- ============================================================
CREATE TABLE IF NOT EXISTS environmental_feature_definitions (
    feature_key TEXT PRIMARY KEY,
    feature_name TEXT NOT NULL,
    data_source TEXT NOT NULL,
    spatial_temporal_grain TEXT NOT NULL,
    unit TEXT,
    availability_state TEXT NOT NULL,
    normalization_method TEXT,
    missing_data_rule TEXT NOT NULL,
    limitations TEXT,
    spec_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experimental_feature_runs (
    run_id TEXT PRIMARY KEY,
    run_status TEXT NOT NULL,
    run_date TEXT NOT NULL,
    observation_date TEXT,
    input_sources TEXT,
    result_status TEXT NOT NULL,
    result_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experimental_feature_values (
    run_id TEXT NOT NULL,
    cell_id TEXT NOT NULL,
    feature_key TEXT NOT NULL,
    feature_value REAL,
    quality_status TEXT NOT NULL,
    source_dataset TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(run_id, cell_id, feature_key),
    FOREIGN KEY(run_id) REFERENCES experimental_feature_runs(run_id),
    FOREIGN KEY(cell_id) REFERENCES spatial_evidence_grid(cell_id),
    FOREIGN KEY(feature_key) REFERENCES environmental_feature_definitions(feature_key)
);

-- ============================================================
-- 13. Stage 6 Environmental Data Integration
-- ============================================================
CREATE TABLE IF NOT EXISTS environmental_dataset_registry (
    dataset_key TEXT PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    source TEXT NOT NULL,
    dataset_type TEXT NOT NULL,
    observation_date TEXT,
    processing_date TEXT,
    crs TEXT,
    resolution_m REAL,
    coverage_type TEXT,
    file_path TEXT,
    quality_status TEXT NOT NULL DEFAULT 'NOT_TESTED',
    missing_data_percent REAL,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spatial_factor_availability (
    cell_id TEXT NOT NULL,
    observation_date TEXT,
    dem_available INTEGER NOT NULL DEFAULT 0,
    slope_available INTEGER NOT NULL DEFAULT 0,
    aspect_available INTEGER NOT NULL DEFAULT 0,
    rainfall_available INTEGER NOT NULL DEFAULT 0,
    gsi_available INTEGER NOT NULL DEFAULT 0,
    insar_los_available INTEGER NOT NULL DEFAULT 0,
    insar_coherence_available INTEGER NOT NULL DEFAULT 0,
    unet_available INTEGER NOT NULL DEFAULT 0,
    quality_status TEXT NOT NULL DEFAULT 'NOT_TESTED',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(cell_id, observation_date),
    FOREIGN KEY(cell_id) REFERENCES spatial_evidence_grid(cell_id)
);

CREATE TABLE IF NOT EXISTS rainfall_rollup_validation (
    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_date TEXT NOT NULL UNIQUE,
    daily_rainfall_mm REAL,
    recalculated_3day_mm REAL,
    stored_database_3day_mm REAL,
    recalculated_7day_mm REAL,
    stored_database_7day_mm REAL,
    recalculated_14day_mm REAL,
    stored_database_14day_mm REAL,
    status TEXT NOT NULL,
    discrepancy_mm REAL,
    source_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gsi_spatial_mapping (
    inventory_id TEXT PRIMARY KEY,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    cell_id TEXT,
    source TEXT NOT NULL,
    coordinate_quality TEXT NOT NULL,
    proximity_km REAL,
    quality_status TEXT NOT NULL,
    FOREIGN KEY(cell_id) REFERENCES spatial_evidence_grid(cell_id)
);
