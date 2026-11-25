"""Master Phase 5 satellite download and preprocessing status orchestration."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import CREDENTIALS, PATHS
from scripts.download_sentinel1 import Sentinel1Downloader
from src.data.db import get_db


def _tool_versions() -> Dict:
    tools = {}
    for name in ("gdalinfo", "snappy", "isce2", "isce3", "snap"):
        tools[name] = shutil.which(name)
    try:
        import rasterio
        tools["rasterio"] = rasterio.__version__
    except Exception:
        tools["rasterio"] = None
    try:
        import pyproj
        tools["pyproj"] = pyproj.__version__
    except Exception:
        tools["pyproj"] = None
    try:
        import numpy
        tools["numpy"] = numpy.__version__
    except Exception:
        tools["numpy"] = None
    return tools


def inspect_cdse_credentials() -> Dict:
    configured = bool(CREDENTIALS.cdse_username and CREDENTIALS.cdse_password)
    if not configured:
        return {
            "status": "BLOCKED",
            "configured": False,
            "result": "CDSE_USERNAME and CDSE_PASSWORD are not configured.",
        }
    try:
        auth = Sentinel1Downloader(dry_run=True).auth
        auth.get_token()
        return {
            "status": "PASS",
            "configured": True,
            "result": "CDSE OAuth token acquired; token value was not logged.",
        }
    except Exception as exc:
        safe_message = str(exc).replace(
            CREDENTIALS.cdse_password,
            "[REDACTED]",
        ) if CREDENTIALS.cdse_password else str(exc)
        return {
            "status": "BLOCKED",
            "configured": True,
            "result": f"CDSE authentication failed: {safe_message}",
        }


def discover_new_products(db=None, days: int = 24) -> Dict:
    db = db or get_db()
    downloader = Sentinel1Downloader(dry_run=True)
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        products = downloader.search_products(start, end)
        parsed = [downloader._parse_product(product) for product in products]
        existing_ids = {
            row["acquisition_id"]
            for row in db.get_acquisitions_by_status("Sentinel-1")
        }
        new = []
        duplicates = []
        for meta in parsed:
            if meta["acquisition_id"] in existing_ids:
                duplicates.append(meta)
            else:
                new.append(meta)

        status = "WAITING_FOR_NEW_DATA" if not new else "PASS_WITH_LIMITATIONS"
        payload = {
            "products_found": len(products),
            "duplicate_products": len(duplicates),
            "new_acquisitions": len(new),
            "selected_products": [],
            "products": [
                {
                    "acquisition_id": row["acquisition_id"],
                    "acquisition_date": row["acquisition_date"],
                    "relative_orbit": row["relative_orbit"],
                    "orbit_direction": row["orbit_direction"],
                    "polarisation": row["polarisation"],
                    "product_type": row["product_type"],
                    "sensor_mode": row["sensor_mode"],
                }
                for row in new
            ],
        }
        db.record_discovery_event(
            status=status,
            search_start=start,
            search_end=end,
            products_found=len(products),
            duplicate_products=len(duplicates),
            new_acquisitions=len(new),
            latest_acquisition_date=(
                max((row["acquisition_date"] for row in parsed), default=None)
            ),
            payload=payload,
        )
        return {
            "status": status,
            "search_start": start,
            "search_end": end,
            **payload,
        }
    except Exception as exc:
        db.record_discovery_event(
            status="BLOCKED",
            search_start=start,
            search_end=end,
            error_message=str(exc),
            payload={"error": str(exc)},
        )
        return {
            "status": "BLOCKED",
            "search_start": start,
            "search_end": end,
            "products_found": 0,
            "duplicate_products": 0,
            "new_acquisitions": 0,
            "selected_products": [],
            "error": str(exc),
        }


def export_phase5_status(db=None) -> Dict:
    db = db or get_db()
    discovery = discover_new_products(db=db)
    auth = inspect_cdse_credentials()
    tools = _tool_versions()

    latest_download = None
    with db.cursor() as cur:
        row = cur.execute(
            "SELECT acquisition_id, acquisition_date, file_path, download_status "
            "FROM acquisitions "
            "WHERE download_status='DOWNLOADED' "
            "ORDER BY acquisition_date DESC LIMIT 1"
        ).fetchone()
        if row:
            latest_download = dict(row)

        download_jobs = cur.execute(
            "SELECT state, COUNT(*) AS count FROM sentinel_download_jobs "
            "GROUP BY state"
        ).fetchall()
        download_states = {r["state"]: r["count"] for r in download_jobs}

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": 5,
        "overall_status": (
            "WAITING_FOR_NEW_DATA"
            if discovery["status"] == "WAITING_FOR_NEW_DATA"
            else discovery["status"]
        ),
        "cdse": auth,
        "discovery": discovery,
        "download": {
            "status": "WAITING_FOR_NEW_DATA" if not discovery["new_acquisitions"] else "BLOCKED",
            "automatic_download": "DISABLED",
            "explicit_download_approval": "REQUIRED",
            "download_states": download_states,
            "latest_download": latest_download,
        },
        "preprocessing": {
            "status": "NOT_TESTED",
            "ready_product_count": 0,
            "interferogram_created": False,
            "los_raster_created": False,
            "coherence_raster_created": False,
            "tools": tools,
        },
        "preservation": db.get_table_counts(),
        "hyp3": {
            "new_jobs_submitted": 0,
            "credits_consumed_in_phase": 0,
            "existing_job_id": "3889d809-88a3-4a93-89a5-258821932737",
        },
    }

    destination = PATHS.viewer_data / "master_phase5_status.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return payload
