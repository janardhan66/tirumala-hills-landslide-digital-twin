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
        kwargs.setdefault("alert_timestamp", datetime.utcnow().isoformat())

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
                 datetime.utcnow().isoformat(), notes, alert_id),
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
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
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
        kwargs["updated_at"] = datetime.utcnow().isoformat()

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
