"""Stage 5 monitoring orchestration and unified status export."""

from __future__ import annotations

import json
import os
import psutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from config.settings import CREDENTIALS, PATHS
from src.analysis.temporal_insar import build_interferogram_network
from src.data.db import get_db


def run_discovery_dry_run(db=None) -> Dict:
    """Discover CDSE products without downloading or registering duplicates."""
    db = db or get_db()
    from scripts.download_sentinel1 import Sentinel1Downloader

    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = (datetime.now(timezone.utc) - timedelta(days=24)).strftime("%Y-%m-%d")
    started = datetime.now(timezone.utc).isoformat()
    try:
        downloader = Sentinel1Downloader(dry_run=True)
        products = downloader.search_products(start, end)
        parsed = [downloader._parse_product(product) for product in products]
        new_ids = [
            acquisition["acquisition_id"]
            for acquisition in parsed
            if not db.acquisition_exists(acquisition["acquisition_id"])
        ]
        latest_date = max(
            (
                acquisition["acquisition_date"]
                for acquisition in parsed
                if acquisition.get("acquisition_date")
            ),
            default=None,
        )
        status = "WAITING_FOR_NEW_DATA" if not new_ids else "NEW_ACQUISITIONS_FOUND"
        payload = {
            "products_found": len(parsed),
            "duplicate_product_ids": [
                acquisition["acquisition_id"]
                for acquisition in parsed
                if db.acquisition_exists(acquisition["acquisition_id"])
            ],
            "new_acquisition_ids": new_ids,
        }
        db.record_discovery_event(
            status=status,
            search_start=start,
            search_end=end,
            products_found=len(parsed),
            duplicate_products=len(parsed) - len(new_ids),
            new_acquisitions=len(new_ids),
            latest_acquisition_date=latest_date,
            payload=payload,
        )
        db.record_monitoring_event(
            "sentinel1_discovery",
            status,
            (
                f"Found {len(parsed)} products; "
                f"{len(new_ids)} genuine new acquisitions."
            ),
            payload=payload,
        )
        return {
            "status": status,
            "started_at": started,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "search_start": start,
            "search_end": end,
            "products_found": len(parsed),
            "duplicate_products": len(parsed) - len(new_ids),
            "new_acquisitions": len(new_ids),
            "new_acquisition_ids": new_ids,
            "latest_acquisition_date": latest_date,
            "error": None,
        }
    except Exception as exc:
        status = "DISCOVERY_FAILED"
        db.record_discovery_event(
            status=status,
            search_start=start,
            search_end=end,
            error_message=str(exc),
            payload={"exception_type": type(exc).__name__},
        )
        db.record_monitoring_event(
            "sentinel1_discovery",
            status,
            f"Sentinel-1 discovery failed: {exc}",
            payload={"exception_type": type(exc).__name__},
        )
        return {
            "status": status,
            "started_at": started,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "search_start": start,
            "search_end": end,
            "products_found": 0,
            "duplicate_products": 0,
            "new_acquisitions": 0,
            "new_acquisition_ids": [],
            "latest_acquisition_date": None,
            "error": str(exc),
        }


def _read_scheduler_health() -> Dict:
    status_path = PATHS.logs_dir / "scheduler_status.json"
    lock_path = PATHS.logs_dir / "scheduler.lock"
    if not status_path.is_file():
        return {
            "status": "NOT_RUNNING",
            "running": False,
            "pid": None,
            "next_execution": None,
            "updated_at": None,
        }
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        pid = int(status.get("pid", 0))
        lock_pid = None
        if lock_path.is_file():
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock_pid = int(lock.get("pid", 0))
        process_running = pid > 0 and psutil.pid_exists(pid) and (
            lock_pid is None or lock_pid == pid
        )
        return {
            "status": "RUNNING" if process_running else "NOT_RUNNING",
            "running": process_running,
            "pid": pid if process_running else None,
            "next_execution": status.get("next_pipeline_run"),
            "updated_at": status.get("updated_at"),
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "status": "UNKNOWN",
            "running": False,
            "pid": None,
            "next_execution": None,
            "updated_at": None,
        }


def export_stage5_status(db=None) -> Dict:
    db = db or get_db()
    pairs = db.get_insar_pairs()
    network = build_interferogram_network(pairs)
    temporal = db.get_temporal_insar_observations()
    valid_temporal = sum(
        1 for row in temporal
        if row["quality_status"] == "VALID"
        and row["los_displacement_m"] is not None
    )
    discovery_events = db.get_discovery_events(limit=1)
    latest_discovery = discovery_events[0] if discovery_events else None
    scheduler = _read_scheduler_health()

    with db.cursor() as cur:
        latest_acquisition = cur.execute(
            "SELECT MAX(acquisition_date) FROM acquisitions "
            "WHERE satellite='Sentinel-1'"
        ).fetchone()[0]
        latest_processed = cur.execute(
            "SELECT MAX(secondary_date) FROM insar_pairs "
            "WHERE processing_status='PROCESSED'"
        ).fetchone()[0]
        completed_jobs = cur.execute(
            "SELECT COUNT(*) FROM hyp3_job_status_history "
            "WHERE status='SUCCEEDED'"
        ).fetchone()[0]
        failed_jobs = cur.execute(
            "SELECT COUNT(*) FROM hyp3_job_status_history "
            "WHERE status='FAILED'"
        ).fetchone()[0]
        last_pipeline = cur.execute(
            "SELECT run_id, stage_name, status, completed_at, message "
            "FROM pipeline_logs ORDER BY log_id DESC LIMIT 1"
        ).fetchone()

    candidate_pairs = sum(
        1 for pair in pairs
        if pair.get("processing_status") in {"CANDIDATE", "SUBMITTED"}
    )
    sbas_ready = len(network["valid_edges"]) >= 2
    latest_observation = latest_processed
    overall_status = "WAITING_FOR_NEW_DATA"
    if not scheduler["running"]:
        overall_status = "SCHEDULER_NOT_RUNNING"
    elif latest_discovery and latest_discovery["status"] == "DISCOVERY_FAILED":
        overall_status = "DISCOVERY_PARTIAL"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": "5",
        "overall_status": overall_status,
        "discovery": {
            "status": (
                latest_discovery["status"]
                if latest_discovery
                else "NOT_TESTED"
            ),
            "last_discovery": (
                latest_discovery["discovery_completed_at"]
                if latest_discovery
                else None
            ),
            "latest_acquisition": latest_acquisition,
            "products_found": (
                latest_discovery["products_found"]
                if latest_discovery
                else 0
            ),
            "duplicate_products": (
                latest_discovery["duplicate_products"]
                if latest_discovery
                else 0
            ),
            "new_acquisitions": (
                latest_discovery["new_acquisitions"]
                if latest_discovery
                else 0
            ),
            "error": (
                latest_discovery["error_message"]
                if latest_discovery
                else None
            ),
        },
        "scheduler": scheduler,
        "processing": {
            "candidate_pairs": candidate_pairs,
            "completed_hyp3_jobs": completed_jobs,
            "failed_hyp3_jobs": failed_jobs,
            "latest_processed_acquisition": latest_processed,
            "last_pipeline_run": dict(last_pipeline) if last_pipeline else None,
        },
        "network": {
            "node_count": len(network["nodes"]),
            "edge_count": len(network["edges"]),
            "valid_edge_count": len(network["valid_edges"]),
            "connected_components": network["connected_components"],
            "component_sizes": network["component_sizes"],
        },
        "sbas": {
            "real_ready": sbas_ready,
            "cumulative_displacement": "AVAILABLE" if sbas_ready else "INSUFFICIENT_DATA",
            "velocity": "AVAILABLE" if sbas_ready else "VELOCITY_NOT_AVAILABLE",
            "reference_consistency": "NOT_ESTABLISHED_ACROSS_PAIRS",
            "temporal_observation_count": len(temporal),
            "valid_temporal_observation_count": valid_temporal,
        },
        "digital_twin": {
            "status": "AVAILABLE",
            "latest_valid_observation": latest_observation,
            "terrain": "EXISTING_REAL_PROJECT_DEM",
            "existing_live_pair": "PAIR_20261109_20261121",
        },
        "data_freshness": {
            "latest_discovered_acquisition": latest_acquisition,
            "latest_processed_acquisition": latest_processed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    out = PATHS.viewer_data / "stage5_monitoring_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(out.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(out)

    db.record_monitoring_event(
        "stage5_status_export",
        payload["overall_status"],
        "Generated unified Stage 5 monitoring status.",
        payload=payload,
    )
    return payload
