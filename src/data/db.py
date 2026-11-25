"""
Tirumala Hills Landslide Digital Twin — Database Connection Manager

Provides thread-safe SQLite database access with schema initialization,
CRUD helpers, and query utilities for all monitoring tables.
"""

import sqlite3
import json
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import PATHS, setup_logging

logger = setup_logging("db")

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "database" / "schema.sql"


def _safe_timestamp_converter(val: bytes) -> str:
    try:
        return val.decode("utf-8")
    except Exception:
        return str(val)

sqlite3.register_converter("timestamp", _safe_timestamp_converter)
sqlite3.register_converter("TIMESTAMP", _safe_timestamp_converter)
sqlite3.register_converter("datetime", _safe_timestamp_converter)
sqlite3.register_converter("DATETIME", _safe_timestamp_converter)
sqlite3.register_converter("date", _safe_timestamp_converter)
sqlite3.register_converter("DATE", _safe_timestamp_converter)


class DatabaseManager:
    """Thread-safe SQLite database manager with schema auto-initialization."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or PATHS.database_file
        self._local = threading.local()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                timeout=30,
            )
            self._local.connection.row_factory = sqlite3.Row
            self._local.connection.execute("PRAGMA journal_mode = WAL")
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection

    @contextmanager
    def connection(self):
        """Context manager for a database connection."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @contextmanager
    def cursor(self):
        """Context manager for a database cursor."""
        with self.connection() as conn:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    def _init_schema(self):
        """Initialize database schema from schema.sql if tables don't exist."""
        with self.connection() as conn:
            # Check if already initialized
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            existing = {row["name"] for row in tables}

            if "acquisitions" not in existing:
                logger.info("Initializing database schema from %s", SCHEMA_FILE)
                if SCHEMA_FILE.exists():
                    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
                    conn.executescript(schema_sql)
                    logger.info("Database schema initialized successfully.")
                else:
                    logger.warning("Schema file not found: %s", SCHEMA_FILE)
            else:
                logger.debug("Database schema already exists (%d tables).", len(existing))
        self._apply_multi_temporal_migrations()

    def _apply_multi_temporal_migrations(self):
        """Add Stage 1 multi-temporal columns without replacing existing data."""
        migrations = {
            "acquisitions": {
                "acquisition_timestamp": "TEXT",
                "beam_mode": "TEXT",
                "spatial_coverage": "TEXT",
            },
            "insar_pairs": {
                "orbit_direction": "TEXT",
                "relative_orbit": "INTEGER",
                "orbit_compatibility": "TEXT",
                "spatial_overlap_percent": "REAL",
                "quality_status": "TEXT DEFAULT 'PENDING'",
                "selection_method": "TEXT",
                "output_archive": "TEXT",
                "submitted_at": "TEXT",
                "last_status_check_at": "TEXT",
                "job_config_json": "TEXT",
                "expected_credit_cost": "INTEGER",
                "output_validation_status": "TEXT DEFAULT 'NOT_TESTED'",
                "submitted_at": "TEXT",
                "last_status_check_at": "TEXT",
                "job_config_json": "TEXT",
                "expected_credit_cost": "INTEGER",
                "output_validation_status": "TEXT DEFAULT 'NOT_TESTED'",
            },
        }
        with self.connection() as conn:
            for table_name, columns in migrations.items():
                existing_columns = {
                    row["name"]
                    for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                }
                for column_name, column_type in columns.items():
                    if column_name not in existing_columns:
                        conn.execute(
                            f"ALTER TABLE {table_name} "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                        logger.info(
                            "Added migration column %s.%s",
                            table_name,
                            column_name,
                        )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hyp3_job_status_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    status_checked_at TIMESTAMP NOT NULL,
                    error_message TEXT,
                    payload_json TEXT,
                    FOREIGN KEY(pair_id) REFERENCES insar_pairs(pair_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hyp3_history_job_status "
                "ON hyp3_job_status_history(job_id, status_checked_at)"
            )
            conn.execute(
                """
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
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_temporal_insar_cell_date "
                "ON temporal_insar_observations(cell_id, acquisition_date)"
            )
            conn.execute(
                """
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
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS monitoring_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    subject_id TEXT,
                    message TEXT NOT NULL,
                    payload_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sentinel_download_jobs (
                    job_id TEXT PRIMARY KEY,
                    acquisition_id TEXT NOT NULL,
                    product_name TEXT,
                    state TEXT NOT NULL DEFAULT 'DISCOVERED',
                    download_limit_bytes INTEGER,
                    file_path TEXT,
                    file_size_bytes INTEGER,
                    checksum_sha256 TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    failure_message TEXT,
                    manifest_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(acquisition_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sentinel_download_attempts (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    acquisition_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    http_status INTEGER,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    bytes_downloaded INTEGER DEFAULT 0,
                    resume_offset_bytes INTEGER DEFAULT 0,
                    state TEXT NOT NULL,
                    error_message TEXT,
                    FOREIGN KEY(job_id) REFERENCES sentinel_download_jobs(job_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sentinel_archive_validation (
                    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    acquisition_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    is_zip INTEGER NOT NULL DEFAULT 0,
                    zip_integrity INTEGER NOT NULL DEFAULT 0,
                    safe_structure INTEGER NOT NULL DEFAULT 0,
                    manifest_present INTEGER NOT NULL DEFAULT 0,
                    measurement_present INTEGER NOT NULL DEFAULT 0,
                    annotation_present INTEGER NOT NULL DEFAULT 0,
                    orbit_metadata_present INTEGER NOT NULL DEFAULT 0,
                    product_id_match INTEGER NOT NULL DEFAULT 0,
                    checksum_sha256 TEXT,
                    validation_status TEXT NOT NULL,
                    failure_details TEXT,
                    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(acquisition_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sentinel_preprocessing_readiness (
                    readiness_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    acquisition_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    safe_path TEXT,
                    measurement_files INTEGER DEFAULT 0,
                    annotation_files INTEGER DEFAULT 0,
                    orbit_files INTEGER DEFAULT 0,
                    available_tools TEXT,
                    missing_requirements TEXT,
                    disk_requirements TEXT,
                    report_json TEXT,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(acquisition_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sentinel_product_inventory (
                    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    acquisition_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size_bytes INTEGER,
                    checksum_sha256 TEXT,
                    member_count INTEGER,
                    state TEXT NOT NULL,
                    discovered_at TIMESTAMP,
                    downloaded_at TIMESTAMP,
                    validated_at TIMESTAMP,
                    metadata_json TEXT,
                    UNIQUE(acquisition_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    message TEXT,
                    response_detail TEXT,
                    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    acknowledged_at TIMESTAMP,
                    FOREIGN KEY(event_id) REFERENCES monitoring_events(event_id),
                    UNIQUE(event_id, channel)
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_notification_event_channel "
                "ON notification_deliveries(event_id, channel)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS insar_processing_runs (
                    run_id TEXT PRIMARY KEY,
                    pair_id TEXT NOT NULL,
                    processing_method TEXT NOT NULL,
                    processing_date TIMESTAMP NOT NULL,
                    software_versions TEXT,
                    input_files TEXT,
                    output_files TEXT,
                    quality_threshold REAL,
                    reference_metadata TEXT,
                    crs TEXT,
                    grid_shape TEXT,
                    nodata_convention TEXT,
                    validation_status TEXT NOT NULL,
                    limitations TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS insar_raster_validation (
                    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    pair_id TEXT NOT NULL,
                    raster_type TEXT NOT NULL,
                    raster_path TEXT NOT NULL,
                    crs TEXT,
                    shape TEXT,
                    resolution_m REAL,
                    bounds TEXT,
                    nodata_value TEXT,
                    valid_pixel_count INTEGER,
                    low_quality_pixel_count INTEGER,
                    minimum_value REAL,
                    maximum_value REAL,
                    mean_value REAL,
                    quality_status TEXT NOT NULL,
                    notes TEXT,
                    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(run_id) REFERENCES insar_processing_runs(run_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS insar_temporal_network (
                    network_id TEXT PRIMARY KEY,
                    node_count INTEGER NOT NULL,
                    edge_count INTEGER NOT NULL,
                    valid_edge_count INTEGER NOT NULL,
                    connected_components INTEGER NOT NULL,
                    matrix_rank INTEGER,
                    reference_consistency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    network_json TEXT,
                    assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS insar_inversion_runs (
                    run_id TEXT PRIMARY KEY,
                    network_id TEXT,
                    run_status TEXT NOT NULL,
                    cumulative_displacement_status TEXT NOT NULL,
                    velocity_status TEXT NOT NULL,
                    residual_norm REAL,
                    uncertainty_summary TEXT,
                    result_status TEXT NOT NULL,
                    limitations TEXT,
                    result_json TEXT,
                    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(network_id) REFERENCES insar_temporal_network(network_id)
                )
                """
            )
            conn.execute(
                """
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
                )
                """
            )
            conn.execute(
                """
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
                    PRIMARY KEY(cell_id, observation_date)
                )
                """
            )
            conn.execute(
                """
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
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gsi_spatial_mapping (
                    inventory_id TEXT PRIMARY KEY,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    cell_id TEXT,
                    source TEXT NOT NULL,
                    coordinate_quality TEXT NOT NULL,
                    proximity_km REAL,
                    quality_status TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
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
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS experimental_feature_runs (
                    run_id TEXT PRIMARY KEY,
                    run_status TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    observation_date TEXT,
                    input_sources TEXT,
                    result_status TEXT NOT NULL,
                    result_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
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
                )
                """
            )

            # Preserve the latest row for records that were historically upserted
            # by full-table inserts rather than a uniqueness constraint.
            conn.execute(
                """
                DELETE FROM risk_history
                WHERE history_id NOT IN (
                    SELECT MAX(history_id)
                    FROM risk_history
                    GROUP BY observation_date
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_risk_history_observation_date "
                "ON risk_history(observation_date)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_acquisition_satellite_product "
                "ON acquisitions(satellite, acquisition_date, acquisition_id)"
            )
            conn.execute(
                """
                DELETE FROM observation_snapshots
                WHERE snapshot_id NOT IN (
                    SELECT MAX(snapshot_id)
                    FROM observation_snapshots
                    GROUP BY cell_id, observation_date
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_observation_snapshot_cell_date "
                "ON observation_snapshots(cell_id, observation_date)"
            )
            conn.execute(
                """
                DELETE FROM alerts
                WHERE rowid NOT IN (
                    SELECT MAX(rowid)
                    FROM alerts
                    GROUP BY trigger_rule, observation_date
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_alert_rule_observation "
                "ON alerts(trigger_rule, observation_date)"
            )

    # ── Acquisition CRUD ──────────────────────────────────────

    def add_acquisition(self, **kwargs) -> str:
        """Insert a satellite product acquisition record."""
        acq_id = kwargs.get("acquisition_id", str(uuid.uuid4()))
        kwargs["acquisition_id"] = acq_id
        kwargs.setdefault("download_status", "PENDING")
        kwargs.setdefault("processing_status", "UNPROCESSED")

        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))

        with self.cursor() as cur:
            cur.execute(
                f"INSERT OR IGNORE INTO acquisitions ({cols}) VALUES ({placeholders})",
                list(kwargs.values()),
            )
        return acq_id

    def get_acquisition(self, acquisition_id: str) -> Optional[Dict]:
        """Get a single acquisition by ID."""
        with self.cursor() as cur:
            row = cur.execute(
                "SELECT * FROM acquisitions WHERE acquisition_id = ?",
                (acquisition_id,),
            ).fetchone()
            return dict(row) if row else None

    def acquisition_exists(self, acquisition_id: str) -> bool:
        """Check if an acquisition already exists (duplicate detection)."""
        with self.cursor() as cur:
            row = cur.execute(
                "SELECT 1 FROM acquisitions WHERE acquisition_id = ?",
                (acquisition_id,),
            ).fetchone()
            return row is not None

    def update_acquisition_status(
        self, acquisition_id: str, download_status: Optional[str] = None,
        processing_status: Optional[str] = None, **kwargs
    ):
        """Update acquisition download/processing status."""
        updates = {
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        }
        if download_status:
            updates["download_status"] = download_status
        if processing_status:
            updates["processing_status"] = processing_status
        updates.update(kwargs)

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        with self.cursor() as cur:
            cur.execute(
                f"UPDATE acquisitions SET {set_clause} WHERE acquisition_id = ?",
                list(updates.values()) + [acquisition_id],
            )

    def get_acquisitions_by_status(
        self, satellite: str, download_status: Optional[str] = None,
        processing_status: Optional[str] = None
    ) -> List[Dict]:
        """Query acquisitions by satellite and status."""
        query = "SELECT * FROM acquisitions WHERE satellite = ?"
        params: list = [satellite]
        if download_status:
            query += " AND download_status = ?"
            params.append(download_status)
        if processing_status:
            query += " AND processing_status = ?"
            params.append(processing_status)
        query += " ORDER BY acquisition_date DESC"

        with self.cursor() as cur:
            rows = cur.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_latest_acquisition_date(self, satellite: str) -> Optional[str]:
        """Get the most recent acquisition date for a satellite."""
        with self.cursor() as cur:
            row = cur.execute(
                "SELECT MAX(acquisition_date) as latest FROM acquisitions "
                "WHERE satellite = ? AND download_status = 'DOWNLOADED'",
                (satellite,),
            ).fetchone()
            return row["latest"] if row else None

    # ── InSAR Pair CRUD ───────────────────────────────────────

    def add_insar_pair(self, **kwargs) -> str:
        """Insert an InSAR processing pair record."""
        pair_id = kwargs.get("pair_id")
        if not pair_id:
            ref = kwargs.get("reference_date", "unknown")
            sec = kwargs.get("secondary_date", "unknown")
            pair_id = f"PAIR_{ref.replace('-', '')}_{sec.replace('-', '')}"
            kwargs["pair_id"] = pair_id

        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))

        with self.cursor() as cur:
            cur.execute(
                f"INSERT OR IGNORE INTO insar_pairs ({cols}) VALUES ({placeholders})",
                list(kwargs.values()),
            )
        return pair_id

    def get_insar_pairs(self, status: Optional[str] = None) -> List[Dict]:
        """Get InSAR pairs, optionally filtered by processing status."""
        query = "SELECT * FROM insar_pairs"
        params: list = []
        if status:
            query += " WHERE processing_status = ?"
            params.append(status)
        query += " ORDER BY secondary_date DESC"

        with self.cursor() as cur:
            rows = cur.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_latest_processed_insar_date(self) -> Optional[str]:
        """Return the latest secondary acquisition date for a processed pair."""
        with self.cursor() as cur:
            row = cur.execute(
                "SELECT MAX(secondary_date) AS latest FROM insar_pairs "
                "WHERE processing_status = 'PROCESSED'"
            ).fetchone()
            return row["latest"] if row else None

    def update_insar_pair(
        self, pair_id: str, processing_status: Optional[str] = None, **kwargs
    ):
        """Update an InSAR pair's processing state and output metadata."""
        updates = {
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        }
        if processing_status is not None:
            updates["processing_status"] = processing_status
        updates.update(kwargs)
        set_clause = ", ".join(f"{column} = ?" for column in updates)
        with self.cursor() as cur:
            cur.execute(
                f"UPDATE insar_pairs SET {set_clause} WHERE pair_id = ?",
                [*updates.values(), pair_id],
            )
            if cur.rowcount != 1:
                raise KeyError(f"InSAR pair not found: {pair_id}")

    def record_hyp3_status(
        self,
        pair_id: str,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
        payload: Optional[dict] = None,
    ):
        """Persist a job status change and update pair status timestamps."""
        checked_at = datetime.now(timezone.utc).isoformat()
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO hyp3_job_status_history "
                "(pair_id, job_id, status, status_checked_at, error_message, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    pair_id,
                    job_id,
                    status,
                    checked_at,
                    error_message,
                    json.dumps(payload, sort_keys=True) if payload is not None else None,
                ),
            )
        pair_status = status
        if status == "SUCCEEDED":
            pair_status = "SUCCEEDED"
        elif status in {"PENDING", "RUNNING"}:
            pair_status = "SUBMITTED"
        elif status == "FAILED":
            pair_status = "FAILED"
        self.update_insar_pair(
            pair_id,
            processing_status=pair_status,
            last_status_check_at=checked_at,
            error_message=error_message,
        )

    def get_hyp3_status_history(self, job_id: Optional[str] = None) -> List[Dict]:
        query = "SELECT * FROM hyp3_job_status_history"
        params: List = []
        if job_id:
            query += " WHERE job_id = ?"
            params.append(job_id)
        query += " ORDER BY status_checked_at, history_id"
        with self.cursor() as cur:
            rows = cur.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def record_discovery_event(
        self,
        status: str,
        search_start: Optional[str] = None,
        search_end: Optional[str] = None,
        products_found: int = 0,
        duplicate_products: int = 0,
        new_acquisitions: int = 0,
        latest_acquisition_date: Optional[str] = None,
        error_message: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> int:
        started_at = datetime.now(timezone.utc).isoformat()
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO monitoring_discovery_events "
                "(discovery_started_at, discovery_completed_at, status, satellite, "
                "search_start, search_end, products_found, duplicate_products, "
                "new_acquisitions, latest_acquisition_date, error_message, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    started_at,
                    datetime.now(timezone.utc).isoformat(),
                    status,
                    "Sentinel-1",
                    search_start,
                    search_end,
                    products_found,
                    duplicate_products,
                    new_acquisitions,
                    latest_acquisition_date,
                    error_message,
                    json.dumps(payload, sort_keys=True) if payload is not None else None,
                ),
            )
            return int(cur.lastrowid)

    def get_discovery_events(self, limit: int = 50) -> List[Dict]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM monitoring_discovery_events "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def record_monitoring_event(
        self,
        event_type: str,
        status: str,
        message: str,
        subject_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> int:
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO monitoring_events "
                "(event_type, status, subject_id, message, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    event_type,
                    status,
                    subject_id,
                    message,
                    json.dumps(payload, sort_keys=True) if payload is not None else None,
                ),
            )
            return int(cur.lastrowid)

    def get_monitoring_events(self, limit: int = 50) -> List[Dict]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM monitoring_events "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def upsert_temporal_insar_observation(self, **kwargs):
        """Insert or update one traceable cell/pair LOS observation."""
        required = {
            "cell_id",
            "pair_id",
            "reference_date",
            "secondary_date",
            "acquisition_date",
        }
        missing = required - set(kwargs)
        if missing:
            raise ValueError(
                "Temporal InSAR observation missing fields: "
                + ", ".join(sorted(missing))
            )

        mutable = {
            key: value for key, value in kwargs.items()
            if key not in {"cell_id", "pair_id"}
        }
        with self.cursor() as cur:
            cur.execute(
                "UPDATE temporal_insar_observations SET "
                + ", ".join(f"{key} = ?" for key in mutable)
                + " WHERE cell_id = ? AND pair_id = ?",
                [*mutable.values(), kwargs["cell_id"], kwargs["pair_id"]],
            )
            if cur.rowcount == 0:
                cols = list(kwargs)
                cur.execute(
                    f"INSERT INTO temporal_insar_observations "
                    f"({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
                    [kwargs[column] for column in cols],
                )

    def bulk_upsert_temporal_insar_observations(self, records: List[Dict]) -> int:
        count = 0
        for record in records:
            self.upsert_temporal_insar_observation(**record)
            count += 1
        return count

    def get_temporal_insar_observations(
        self,
        pair_id: Optional[str] = None,
        cell_id: Optional[str] = None,
    ) -> List[Dict]:
        query = "SELECT * FROM temporal_insar_observations"
        params: List = []
        clauses = []
        if pair_id:
            clauses.append("pair_id = ?")
            params.append(pair_id)
        if cell_id:
            clauses.append("cell_id = ?")
            params.append(cell_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY acquisition_date, cell_id"
        with self.cursor() as cur:
            rows = cur.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def register_environmental_dataset(self, **kwargs):
        """Upsert source/environmental dataset registry metadata."""
        required = {"dataset_key", "dataset_name", "source", "dataset_type"}
        missing = required - set(kwargs)
        if missing:
            raise ValueError(
                "Environmental dataset missing fields: "
                + ", ".join(sorted(missing))
            )
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        cols = list(kwargs)
        placeholders = ", ".join(["?"] * len(cols))
        update_clause = ", ".join(
            f"{column} = excluded.{column}"
            for column in cols
            if column != "dataset_key"
        )
        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO environmental_dataset_registry "
                f"({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT(dataset_key) DO UPDATE SET {update_clause}",
                [kwargs[column] for column in cols],
            )

    def get_environmental_datasets(self) -> List[Dict]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM environmental_dataset_registry "
                "ORDER BY dataset_type, dataset_name"
            ).fetchall()
            return [dict(row) for row in rows]

    def upsert_spatial_factor_availability(self, **kwargs):
        required = {"cell_id", "observation_date"}
        missing = required - set(kwargs)
        if missing:
            raise ValueError(
                "Spatial factor availability missing fields: "
                + ", ".join(sorted(missing))
            )
        cols = list(kwargs)
        placeholders = ", ".join(["?"] * len(cols))
        update_clause = ", ".join(
            f"{column} = excluded.{column}"
            for column in cols
            if column not in {"cell_id", "observation_date"}
        )
        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO spatial_factor_availability "
                f"({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT(cell_id, observation_date) DO UPDATE SET "
                f"{update_clause}",
                [kwargs[column] for column in cols],
            )

    def get_spatial_factor_availability(
        self,
        observation_date: Optional[str] = None,
    ) -> List[Dict]:
        query = "SELECT * FROM spatial_factor_availability"
        params: List = []
        if observation_date:
            query += " WHERE observation_date = ?"
            params.append(observation_date)
        query += " ORDER BY cell_id"
        with self.cursor() as cur:
            rows = cur.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def upsert_rainfall_rollup_validation(self, **kwargs):
        required = {"record_date", "status"}
        missing = required - set(kwargs)
        if missing:
            raise ValueError(
                "Rainfall rollup validation missing fields: "
                + ", ".join(sorted(missing))
            )
        cols = list(kwargs)
        placeholders = ", ".join(["?"] * len(cols))
        update_clause = ", ".join(
            f"{column} = excluded.{column}"
            for column in cols
            if column != "record_date"
        )
        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO rainfall_rollup_validation "
                f"({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT(record_date) DO UPDATE SET {update_clause}",
                [kwargs[column] for column in cols],
            )

    def get_rainfall_rollup_validation(self) -> List[Dict]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM rainfall_rollup_validation "
                "ORDER BY record_date"
            ).fetchall()
            return [dict(row) for row in rows]

    def upsert_gsi_spatial_mapping(self, **kwargs):
        required = {
            "inventory_id",
            "latitude",
            "longitude",
            "source",
            "coordinate_quality",
            "quality_status",
        }
        missing = required - set(kwargs)
        if missing:
            raise ValueError(
                "GSI spatial mapping missing fields: "
                + ", ".join(sorted(missing))
            )
        cols = list(kwargs)
        placeholders = ", ".join(["?"] * len(cols))
        update_clause = ", ".join(
            f"{column} = excluded.{column}"
            for column in cols
            if column != "inventory_id"
        )
        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO gsi_spatial_mapping "
                f"({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT(inventory_id) DO UPDATE SET {update_clause}",
                [kwargs[column] for column in cols],
            )

    def get_gsi_spatial_mapping(self) -> List[Dict]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM gsi_spatial_mapping "
                "ORDER BY inventory_id"
            ).fetchall()
            return [dict(row) for row in rows]

    def register_feature_definition(self, **kwargs):
        required = {
            "feature_key",
            "feature_name",
            "data_source",
            "spatial_temporal_grain",
            "availability_state",
            "missing_data_rule",
        }
        missing = required - set(kwargs)
        if missing:
            raise ValueError(
                "Feature definition missing fields: "
                + ", ".join(sorted(missing))
            )
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        cols = list(kwargs)
        placeholders = ", ".join(["?"] * len(cols))
        update_clause = ", ".join(
            f"{column} = excluded.{column}"
            for column in cols
            if column != "feature_key"
        )
        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO environmental_feature_definitions "
                f"({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT(feature_key) DO UPDATE SET {update_clause}",
                [kwargs[column] for column in cols],
            )

    def get_feature_definitions(self) -> List[Dict]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM environmental_feature_definitions "
                "ORDER BY feature_key"
            ).fetchall()
            return [dict(row) for row in rows]

    def create_experimental_feature_run(self, **kwargs):
        required = {"run_id", "run_status", "run_date", "result_status"}
        missing = required - set(kwargs)
        if missing:
            raise ValueError(
                "Experimental feature run missing fields: "
                + ", ".join(sorted(missing))
            )
        cols = list(kwargs)
        placeholders = ", ".join(["?"] * len(cols))
        with self.cursor() as cur:
            cur.execute(
                f"INSERT OR IGNORE INTO experimental_feature_runs "
                f"({', '.join(cols)}) VALUES ({placeholders})",
                [kwargs[column] for column in cols],
            )

    def get_experimental_feature_runs(self) -> List[Dict]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM experimental_feature_runs "
                "ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    # ── Rainfall CRUD ─────────────────────────────────────────

    def add_rainfall_record(self, **kwargs):
        """Insert a daily rainfall record (upsert)."""
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        update_clause = ", ".join(
            f"{k} = excluded.{k}" for k in kwargs.keys() if k != "record_date"
        )

        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO rainfall_records ({cols}) VALUES ({placeholders}) "
                f"ON CONFLICT(record_date) DO UPDATE SET {update_clause}",
                list(kwargs.values()),
            )

    def get_rainfall_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get rainfall records for a date range."""
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM rainfall_records WHERE record_date BETWEEN ? AND ? "
                "ORDER BY record_date",
                (start_date, end_date),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_rainfall_date(self) -> Optional[str]:
        """Get the most recent rainfall record date."""
        with self.cursor() as cur:
            row = cur.execute(
                "SELECT MAX(record_date) as latest FROM rainfall_records"
            ).fetchone()
            return row["latest"] if row else None

    # ── Spatial Evidence Grid ─────────────────────────────────

    def populate_spatial_grid(self, records: List[Dict]):
        """Bulk insert spatial grid cells (initial population)."""
        if not records:
            return
        cols = list(records[0].keys())
        col_str = ", ".join(cols)
        placeholders = ", ".join(["?"] * len(cols))

        with self.cursor() as cur:
            cur.executemany(
                f"INSERT OR IGNORE INTO spatial_evidence_grid ({col_str}) VALUES ({placeholders})",
                [tuple(r[c] for c in cols) for r in records],
            )
        logger.info("Populated spatial grid with %d cells.", len(records))

    def get_grid_cell(self, cell_id: str) -> Optional[Dict]:
        """Get a grid cell by ID."""
        with self.cursor() as cur:
            row = cur.execute(
                "SELECT * FROM spatial_evidence_grid WHERE cell_id = ?",
                (cell_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_all_grid_cells(self) -> List[Dict]:
        """Get all spatial grid cells."""
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM spatial_evidence_grid ORDER BY row_idx, col_idx"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Observation Snapshots ─────────────────────────────────

    def add_observation_snapshot(self, **kwargs):
        """Insert a time-stamped observation for a grid cell."""
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))

        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO observation_snapshots ({cols}) VALUES ({placeholders})",
                list(kwargs.values()),
            )

    def bulk_add_observation_snapshots(self, records: List[Dict]):
        """Insert or update snapshots by cell and observation date."""
        if not records:
            return
        cols = list(records[0].keys())
        if "cell_id" not in cols or "observation_date" not in cols:
            raise ValueError("Observation snapshots require cell_id and observation_date.")
        mutable_cols = [
            column for column in cols
            if column not in {"cell_id", "observation_date"}
        ]
        insert_sql = (
            f"INSERT INTO observation_snapshots ({', '.join(cols)}) "
            f"VALUES ({', '.join(['?'] * len(cols))})"
        )
        update_sql = (
            f"UPDATE observation_snapshots SET "
            f"{', '.join(f'{column} = ?' for column in mutable_cols)} "
            "WHERE cell_id = ? AND observation_date = ?"
        ) if mutable_cols else None

        with self.cursor() as cur:
            for record in records:
                updated = False
                if update_sql:
                    cur.execute(
                        update_sql,
                        [record[column] for column in mutable_cols]
                        + [record["cell_id"], record["observation_date"]],
                    )
                    updated = cur.rowcount > 0
                if not updated:
                    cur.execute(insert_sql, [record[column] for column in cols])
        logger.info("Upserted %d observation snapshots.", len(records))

    def get_observations_for_date(self, observation_date: str) -> List[Dict]:
        """Get all observation snapshots for a specific date."""
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM observation_snapshots WHERE observation_date = ? "
                "ORDER BY snapshot_id",
                (observation_date,),
            ).fetchall()
            latest_by_cell = {row["cell_id"]: dict(row) for row in rows}
            return [latest_by_cell[cell_id] for cell_id in sorted(latest_by_cell)]

    def get_observation_dates(self) -> List[str]:
        """Get all distinct observation dates."""
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT DISTINCT observation_date FROM observation_snapshots "
                "ORDER BY observation_date"
            ).fetchall()
            return [row["observation_date"] for row in rows]

    def get_cell_history(self, cell_id: str) -> List[Dict]:
        """Get all observation snapshots for a specific cell across time."""
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM observation_snapshots WHERE cell_id = ? "
                "ORDER BY observation_date",
                (cell_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Risk History ──────────────────────────────────────────

    def add_risk_history(self, **kwargs):
        """Insert an aggregated risk history record."""
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))

        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO risk_history ({cols}) VALUES ({placeholders})",
                list(kwargs.values()),
            )

    def upsert_risk_history(self, **kwargs):
        """Insert or replace the aggregate risk record for an observation date."""
        observation_date = kwargs.get("observation_date")
        if not observation_date:
            raise ValueError("Risk history requires an observation_date.")
        mutable = {
            key: value for key, value in kwargs.items()
            if key != "observation_date"
        }
        with self.cursor() as cur:
            cur.execute(
                "UPDATE risk_history SET "
                + ", ".join(f"{key} = ?" for key in mutable)
                + " WHERE observation_date = ?",
                [*mutable.values(), observation_date],
            )
            if cur.rowcount == 0:
                cols = list(kwargs)
                cur.execute(
                    f"INSERT INTO risk_history ({', '.join(cols)}) "
                    f"VALUES ({', '.join(['?'] * len(cols))})",
                    [kwargs[column] for column in cols],
                )

    def get_risk_history(self) -> List[Dict]:
        """Get all risk history records."""
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM risk_history ORDER BY observation_date"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_risk_summary(self) -> Dict:
        """Get the latest risk assessment summary with percentage breakdowns."""
        history = self.get_risk_history()
        if not history:
            return {"high_pct": 0.0, "medium_pct": 0.0, "low_pct": 0.0,
                    "total_cells": 0, "high_count": 0, "medium_count": 0, "low_count": 0}
        latest = history[-1]
        total = latest.get("total_cells", 1) or 1
        high = latest.get("high_count", 0) or 0
        med = latest.get("medium_count", 0) or 0
        low = latest.get("low_count", 0) or 0
        return {
            "high_pct": round(high / total * 100, 1),
            "medium_pct": round(med / total * 100, 1),
            "low_pct": round(low / total * 100, 1),
            "total_cells": total,
            "high_count": high,
            "medium_count": med,
            "low_count": low,
            "observation_date": latest.get("observation_date", ""),
            "mean_risk_score": latest.get("mean_risk_score", 0.0),
        }

    # ── Alerts ────────────────────────────────────────────────

    def add_alert(self, **kwargs) -> str:
        """Insert a decision-support alert."""
        alert_id = kwargs.get("alert_id", str(uuid.uuid4()))
        kwargs["alert_id"] = alert_id
        kwargs.setdefault("alert_timestamp", datetime.now(timezone.utc).isoformat())

        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))

        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO alerts ({cols}) VALUES ({placeholders})",
                list(kwargs.values()),
            )
        return alert_id

    def update_alert_status(
        self, alert_id: str, verification_status: str,
        verified_by: Optional[str] = None, notes: Optional[str] = None
    ):
        """Update alert verification status."""
        with self.cursor() as cur:
            cur.execute(
                "UPDATE alerts SET verification_status = ?, verified_by = ?, "
                "verified_at = ?, verification_notes = ? WHERE alert_id = ?",
                (verification_status, verified_by,
                 datetime.now(timezone.utc).isoformat(), notes, alert_id),
            )

    def get_active_alerts(self) -> List[Dict]:
        """Get all pending alerts."""
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM alerts WHERE verification_status = 'PENDING' "
                "ORDER BY alert_timestamp DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_alerts(self, limit: int = 100) -> List[Dict]:
        """Get recent alerts (all statuses)."""
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM alerts ORDER BY alert_timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Pipeline Logs ─────────────────────────────────────────

    def log_pipeline_stage(
        self, run_id: str, stage_name: str, status: str,
        duration_seconds: float = 0.0, records_processed: int = 0,
        message: str = "", error_traceback: str = ""
    ):
        """Log a pipeline execution stage."""
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO pipeline_logs "
                "(run_id, stage_name, status, started_at, completed_at, "
                "duration_seconds, records_processed, message, error_traceback) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, stage_name, status,
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                    duration_seconds, records_processed,
                    message, error_traceback,
                ),
            )

    def get_pipeline_logs(self, run_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get pipeline execution logs."""
        if isinstance(run_id, int):
            limit = run_id
            run_id = None
        if run_id:
            query = "SELECT * FROM pipeline_logs WHERE run_id = ? ORDER BY created_at"
            params: list = [run_id]
        else:
            query = "SELECT * FROM pipeline_logs ORDER BY created_at DESC LIMIT ?"
            params = [limit]

        with self.cursor() as cur:
            rows = cur.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_latest_pipeline_run(self) -> Optional[Dict]:
        """Get the most recent pipeline run summary."""
        with self.cursor() as cur:
            row = cur.execute(
                "SELECT run_id, MIN(started_at) as started, MAX(completed_at) as completed, "
                "GROUP_CONCAT(stage_name || ':' || status, '; ') as stages "
                "FROM pipeline_logs GROUP BY run_id ORDER BY started DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    # ── Scheduler State ───────────────────────────────────────

    def update_scheduler_state(self, job_name: str, **kwargs):
        """Update or insert scheduler job state."""
        kwargs["job_name"] = job_name
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()

        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        update_clause = ", ".join(
            f"{k} = excluded.{k}" for k in kwargs.keys() if k != "job_name"
        )

        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO scheduler_state ({cols}) VALUES ({placeholders}) "
                f"ON CONFLICT(job_name) DO UPDATE SET {update_clause}",
                list(kwargs.values()),
            )

    def get_scheduler_state(self) -> List[Dict]:
        """Get all scheduler job states."""
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM scheduler_state ORDER BY job_name"
            ).fetchall()
            return [dict(r) for r in rows]

    # ── CesiumJS Layer Registry ───────────────────────────────

    def register_cesium_layer(self, **kwargs):
        """Register or update a CesiumJS viewer layer."""
        cols = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?"] * len(kwargs))
        update_clause = ", ".join(
            f"{k} = excluded.{k}" for k in kwargs.keys() if k != "layer_id"
        )

        with self.cursor() as cur:
            cur.execute(
                f"INSERT INTO cesium_layers ({cols}) VALUES ({placeholders}) "
                f"ON CONFLICT(layer_id) DO UPDATE SET {update_clause}",
                list(kwargs.values()),
            )

    # ── Utility ───────────────────────────────────────────────

    def get_table_counts(self) -> Dict[str, int]:
        """Get row counts for all tables (dashboard health check)."""
        tables = [
            "acquisitions", "insar_pairs", "rainfall_records",
            "spatial_evidence_grid", "observation_snapshots",
            "risk_history", "alerts", "pipeline_logs",
            "scheduler_state", "cesium_layers", "vegetation_indices",
            "monitoring_discovery_events", "monitoring_events",
            "temporal_insar_observations", "hyp3_job_status_history",
            "sentinel_download_jobs", "sentinel_download_attempts",
            "sentinel_archive_validation", "sentinel_preprocessing_readiness",
            "sentinel_product_inventory",
            "insar_processing_runs", "insar_raster_validation",
            "insar_temporal_network", "insar_inversion_runs",
        ]
        counts = {}
        with self.cursor() as cur:
            for table in tables:
                try:
                    row = cur.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
                    counts[table] = row["cnt"]
                except sqlite3.OperationalError:
                    counts[table] = -1  # Table missing
        return counts

    def close(self):
        """Close the thread-local connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# ── Module-Level Singleton ────────────────────────────────────
_db_instance: Optional[DatabaseManager] = None


def get_db(db_path: Optional[Path] = None) -> DatabaseManager:
    """Get or create the singleton DatabaseManager."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager(db_path)
    return _db_instance
