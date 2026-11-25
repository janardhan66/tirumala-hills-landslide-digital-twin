"""Unified status export for the emergency final integration sprint."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import PATHS
from src.data.db import get_db
from src.risk_assessment import build_spatial_risk


def load_unified_status(db=None) -> Dict:
    db = db or get_db()
    counts = db.get_table_counts()

    spatial_path = PATHS.spatial_evidence_csv
    risk = {"count": 0, "category": "Unavailable", "score": None, "distribution": {}}
    factor_availability = {
        "dem": "AVAILABLE",
        "slope": "AVAILABLE",
        "aspect": "AVAILABLE",
        "insar_los": "AVAILABLE_WITH_REFERENCE_LIMITATION",
        "insar_coherence": "AVAILABLE",
        "gsi_history": "AVAILABLE_AS_APPROXIMATE_LOCATIONS",
        "rainfall": "AVAILABLE_AGGREGATE_WITH_RECONCILIATION_LIMITATION",
        "unet": "BENCHMARK_METADATA_ONLY",
    }

    if spatial_path.is_file():
        frame = pd.read_csv(spatial_path)
        scored, summary = build_spatial_risk(frame)
        if not scored.empty:
            distribution = (
                scored["risk_category"]
                .fillna("Unavailable")
                .value_counts()
                .to_dict()
            )
            risk = {
                "count": int(len(scored)),
                "category": summary["category"],
                "score": summary["score"],
                "distribution": distribution,
            }

    with db.cursor() as cur:
        latest_acquisition = cur.execute(
            "SELECT MAX(acquisition_date) FROM acquisitions "
            "WHERE satellite='Sentinel-1'"
        ).fetchone()[0]
        latest_processed = cur.execute(
            "SELECT MAX(secondary_date) FROM insar_pairs "
            "WHERE processing_status='PROCESSED'"
        ).fetchone()[0]
        latest_discovery = cur.execute(
            "SELECT discovery_completed_at,status,products_found,"
            "duplicate_products,new_acquisitions "
            "FROM monitoring_discovery_events "
            "ORDER BY event_id DESC LIMIT 1"
        ).fetchone()
        latest_risk = cur.execute(
            "SELECT observation_date,mean_risk_score,max_risk_score,low_count,"
            "medium_count,high_count "
            "FROM risk_history ORDER BY observation_date DESC LIMIT 1"
        ).fetchone()
        alert_count = cur.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]

    discovery = dict(latest_discovery) if latest_discovery else None
    risk_history = dict(latest_risk) if latest_risk else None

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": "DEMONSTRATION_READY_WITH_LIMITATIONS",
        "project": {
            "satellite_monitoring": "WAITING_FOR_NEW_DATA",
            "temporal_inversion": "NOT_RELIABLE_WITH_SINGLE_PAIR",
            "risk_model": "EMPIRICAL_EVIDENCE_INDEX",
            "alert_delivery": "LOCAL_EVIDENCE_ALERTS_NOT_EXTERNALLY_VERIFIED",
            "u_net": "BENCHMARK_ONLY_NO_LOCAL_VALIDATION",
        },
        "risk": risk,
        "factor_availability": factor_availability,
        "monitoring_history": {
            "latest_discovered_acquisition": latest_acquisition,
            "latest_processed_acquisition": latest_processed,
            "latest_discovery_event": discovery,
            "latest_risk_history": risk_history,
            "alert_count": int(alert_count),
        },
        "preservation": counts,
        "limitations": [
            "No real cumulative LOS displacement or velocity is shown.",
            "No missing rainfall or InSAR data is treated as zero.",
            "GES DISC rainfall access remains blocked.",
            "Telegram and SMTP delivery are not verified.",
            "U-Net benchmark metadata is not local Tirumala validation.",
            "GSI coordinates are approximate map-derived locations.",
        ],
    }
    return payload


def export_final_status(db=None) -> Dict:
    payload = load_unified_status(db)
    destination = PATHS.viewer_data / "master_final_status.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return payload
