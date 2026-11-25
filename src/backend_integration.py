"""Read-only backend integration for verified project data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import rasterio

from config.settings import PATHS
from src.agent.alert_engine import AlertRulesEngine
from src.risk_assessment import build_spatial_risk, explain_risk_row


def get_acquisition_history(db) -> List[Dict]:
    with db.cursor() as cur:
        rows = cur.execute(
            "SELECT acquisition_id,satellite,product_type,sensor_mode,"
            "beam_mode,orbit_direction,relative_orbit,acquisition_date,"
            "acquisition_timestamp,download_status,processing_status,"
            "file_path,error_message,updated_at "
            "FROM acquisitions "
            "WHERE satellite='Sentinel-1' "
            "ORDER BY acquisition_date DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_pair_history(db) -> List[Dict]:
    pairs = db.get_insar_pairs()
    return [
        {
            "pair_id": pair["pair_id"],
            "reference_date": pair["reference_date"],
            "secondary_date": pair["secondary_date"],
            "temporal_baseline_days": pair["temporal_baseline_days"],
            "relative_orbit": pair.get("relative_orbit"),
            "orbit_direction": pair.get("orbit_direction"),
            "processing_status": pair["processing_status"],
            "quality_status": pair["quality_status"],
            "valid_pixels": pair.get("valid_pixels"),
            "mean_coherence": pair.get("mean_coherence"),
            "los_disp_tif": pair.get("los_disp_tif"),
            "coherence_tif": pair.get("coherence_tif"),
            "hyp3_job_id": pair.get("hyp3_job_id"),
            "submitted_at": pair.get("submitted_at"),
            "last_status_check_at": pair.get("last_status_check_at"),
            "output_validation_status": pair.get("output_validation_status"),
            "scientific_status": (
                "REAL_PAIR_WITH_PAIR_SPECIFIC_PHASE_REFERENCE"
                if pair["pair_id"] == "PAIR_20261109_20261121"
                else "HISTORICAL_PAIR_NOT_RECALCULATED"
            ),
        }
        for pair in pairs
    ]


def build_risk_explanation(db, limit: Optional[int] = None) -> Dict:
    observations = db.get_observations_for_date(
        db.get_latest_processed_insar_date()
        if db.get_latest_processed_insar_date()
        else ""
    )
    if not observations:
        with db.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM observation_snapshots "
                "ORDER BY observation_date DESC, snapshot_id"
            ).fetchall()
            observations = [dict(row) for row in rows]

    if not observations:
        frame = pd.DataFrame()
    else:
        frame = pd.DataFrame(observations)

    scored, summary = build_spatial_risk(frame)
    explanations = []
    if not scored.empty:
        selected = scored.head(limit) if limit else scored
        for _, row in selected.iterrows():
            explanations.append(explain_risk_row(row))

    return {
        "calibration_status": "NOT_CALIBRATED",
        "formula": {
            "slope_component": 0.40,
            "terrain_component": 0.25,
            "insar_component": 0.20,
            "temporal_component": 0.15,
        },
        "summary": summary,
        "distribution": (
            scored["risk_category"].fillna("Unavailable").value_counts().to_dict()
            if not scored.empty
            else {}
        ),
        "rows": explanations,
        "limitations": [
            "Missing factors are excluded, not replaced with zero.",
            "Rainfall is study-area aggregate context, not per-cell evidence.",
            "LOS is pair-specific relative line-of-sight displacement.",
            "No cumulative displacement or velocity is calculated.",
            "This is an empirical evidence index, not calibrated probability.",
        ],
    }


def validate_rasters() -> Dict:
    dem = PATHS.dem_tif
    paths = {
        "dem": dem,
        "slope": PATHS.slope_tif,
        "aspect": PATHS.aspect_tif,
        "insar_los": Path(
            str(PATHS.processed_dinsar)
            + "/PAIR_20261109_20261121/tirumala_live_los_disp_80m.tif"
        ),
        "insar_coherence": Path(
            str(PATHS.processed_dinsar)
            + "/PAIR_20261109_20261121/tirumala_live_coherence_80m.tif"
        ),
    }
    datasets = {}
    reference_profile = None
    errors = []

    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"{name}: missing file")
            continue
        try:
            with rasterio.open(path) as source:
                profile = {
                    "crs": str(source.crs),
                    "shape": [source.height, source.width],
                    "resolution": [float(source.res[0]), float(source.res[1])],
                    "bounds": [float(v) for v in source.bounds],
                    "nodata": (
                        None
                        if source.nodata is None
                        or not __import__("numpy").isfinite(float(source.nodata))
                        else float(source.nodata)
                    ),
                }
                data = source.read(1, masked=True)
                profile["valid_cells"] = int((~data.mask).sum())
                profile["missing_cells"] = int(data.mask.sum())
                profile["source_unchanged"] = True
                datasets[name] = profile

                current = (
                    profile["crs"],
                    profile["shape"],
                    profile["resolution"],
                    profile["bounds"],
                )
                if reference_profile is None:
                    reference_profile = current
                elif current != reference_profile:
                    errors.append(f"{name}: spatial alignment mismatch")
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    return {
        "valid": not errors,
        "datasets": datasets,
        "errors": errors,
    }


def build_actual_alert_payload(db) -> Dict:
    observations = []
    latest_date = db.get_latest_processed_insar_date()
    if latest_date:
        observations = db.get_observations_for_date(latest_date)

    frame = pd.DataFrame(observations)
    if "risk_score" not in frame.columns and not frame.empty:
        frame, _ = build_spatial_risk(frame)

    rainfall_3day = None
    rainfall_status = "UNAVAILABLE"
    rainfall_date = db.get_latest_rainfall_date()
    if rainfall_date:
        validation = [
            row for row in db.get_rainfall_rollup_validation()
            if row["record_date"] == rainfall_date
        ]
        status = validation[0]["status"] if validation else "UNAVAILABLE"
        if status == "MATCHED":
            records = db.get_rainfall_range(rainfall_date, rainfall_date)
            if records:
                rainfall_3day = records[0].get("rolling_3day_mm")
                rainfall_status = "MATCHED"
        elif status:
            rainfall_status = status

    alerts = []
    if not frame.empty:
        alerts = AlertRulesEngine().evaluate_all_rules(
            frame,
            rainfall_3day_mm=rainfall_3day,
            observation_date=latest_date or "",
        )

    serialized = [
        {
            "trigger_rule": alert.trigger_rule,
            "severity": alert.severity,
            "warning_level": alert.warning_level,
            "affected_cells_count": alert.affected_cells_count,
            "observation_date": alert.observation_date,
            "data_quality": alert.data_quality,
            "summary": alert.summary,
            "recommended_action": alert.recommended_action,
            "disclaimer": alert.disclaimer,
            "indicators": alert.indicators,
        }
        for alert in alerts
    ]
    return {
        "observation_date": latest_date,
        "rainfall_status": rainfall_status,
        "rainfall_3day_mm": rainfall_3day,
        "actual_database_alert_records": db.get_all_alerts(limit=100),
        "evaluated_alerts": serialized,
        "delivery_status": "NOT_TESTED_EXTERNAL_DELIVERY",
    }


def build_backend_status(db) -> Dict:
    discovery = db.get_discovery_events(limit=1)
    pair_history = get_pair_history(db)
    acquisition_history = get_acquisition_history(db)
    latest_acquisition = (
        max(
            (row["acquisition_date"] for row in acquisition_history if row["acquisition_date"]),
            default=None,
        )
    )
    latest_rainfall = db.get_latest_rainfall_date()
    latest_processed = db.get_latest_processed_insar_date()
    pipeline = db.get_latest_pipeline_run()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "BACKEND_INTEGRATED_WITH_LIMITATIONS",
        "calibration_status": "NOT_CALIBRATED",
        "acquisitions": {
            "history": acquisition_history,
            "latest_acquisition_date": latest_acquisition,
        },
        "pairs": {
            "history": pair_history,
            "latest_processed_acquisition_date": latest_processed,
            "temporal_inversion_status": "NOT_RELIABLE_WITH_SINGLE_PAIR",
        },
        "data_freshness": {
            "latest_sentinel1_acquisition": latest_acquisition,
            "latest_rainfall_observation": latest_rainfall,
            "latest_processed_insar": latest_processed,
            "latest_discovery_event": discovery[0] if discovery else None,
            "latest_pipeline_run": pipeline,
        },
        "risk": build_risk_explanation(db, limit=100),
        "raster_validation": validate_rasters(),
        "alerts": build_actual_alert_payload(db),
        "environmental_datasets": db.get_environmental_datasets(),
        "feature_definitions": db.get_feature_definitions(),
        "rainfall_rollup_validation": db.get_rainfall_rollup_validation(),
        "risk_history": db.get_risk_history(),
        "database_counts": db.get_table_counts(),
        "blocked": [
            "No genuine new Sentinel-1 data.",
            "No paid HyP3 submission.",
            "No real cumulative displacement or velocity.",
            "GES DISC rainfall 401 remains unresolved.",
            "U-Net is benchmark-only.",
            "External notification delivery not verified.",
        ],
    }


def export_backend_status(db, output_path: Optional[Path] = None) -> Dict:
    payload = build_backend_status(db)
    destination = output_path or (
        PATHS.root / "outputs" / "backend" / "backend_integration_status.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(destination)
    return payload
