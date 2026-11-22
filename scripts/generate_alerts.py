"""
Alert Generator CLI — Runs alert rules and dispatches notifications.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS, setup_logging
from src.agent.alert_engine import (
    AlertRulesEngine, save_alerts_to_db,
    send_telegram_notification, send_email_notification,
)

logger = setup_logging("generate_alerts")


def main():
    parser = argparse.ArgumentParser(description="Generate and dispatch landslide alerts.")
    parser.add_argument(
        "--observation-date",
        help="Observation date (YYYY-MM-DD); defaults to the latest processed InSAR pair.",
    )
    parser.add_argument("--input-csv", default=None)
    parser.add_argument(
        "--rainfall-3day",
        type=float,
        default=None,
        help="Explicit 3-day accumulated rainfall in mm; otherwise use database data for the observation date.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--notify", action="store_true",
                        help="Send Telegram/email notifications if configured.")
    args = parser.parse_args()

    from src.data.db import get_db

    db = get_db()
    observation_date = args.observation_date
    if observation_date is None:
        observation_date = db.get_latest_processed_insar_date()
        if observation_date is None:
            parser.error("No processed InSAR pair date is available; pass --observation-date explicitly.")

    # Load evidence data
    csv_path = args.input_csv or str(PATHS.spatial_evidence_csv)
    if not Path(csv_path).exists():
        logger.error("Evidence file not found: %s", csv_path)
        return

    df = pd.read_csv(csv_path)
    logger.info("Loaded %d evidence records from %s.", len(df), Path(csv_path).name)

    # Get rainfall from database if not provided
    rainfall = args.rainfall_3day
    if rainfall is None:
        records = db.get_rainfall_range("0001-01-01", observation_date)
        if records:
            rainfall = records[-1].get("rolling_3day_mm")
            if rainfall is not None:
                logger.info(
                    "Using database rainfall: %.1f mm (3-day) on %s.",
                    rainfall,
                    records[-1]["record_date"],
                )

    # Run alert engine
    engine = AlertRulesEngine()
    alerts = engine.evaluate_all_rules(df, rainfall, observation_date)

    if not alerts:
        logger.info("No alert conditions triggered.")
        print(json.dumps({"alerts": 0, "message": "No conditions triggered."}))
        return

    # Display alerts
    for alert in alerts:
        logger.info(
            "ALERT [%s] %s: %s (%d cells, max score %.1f)",
            alert.severity, alert.trigger_rule, alert.summary[:60],
            alert.affected_cells_count, alert.max_risk_score,
        )

    if args.dry_run:
        logger.info("[DRY RUN] Would save %d alerts.", len(alerts))
        result = [{"rule": a.trigger_rule, "severity": a.severity,
                   "cells": a.affected_cells_count, "summary": a.summary} for a in alerts]
        print(json.dumps({"alerts": len(alerts), "dry_run": True, "details": result}, indent=2))
        return

    # Save to database
    save_alerts_to_db(alerts)

    # Send notifications if configured
    if args.notify:
        for alert in alerts:
            if alert.severity in ("WARNING", "CRITICAL"):
                sent_tg = send_telegram_notification(alert)
                sent_em = send_email_notification(alert)
                logger.info("Notifications: Telegram=%s, Email=%s", sent_tg, sent_em)

    result = {
        "alerts": len(alerts),
        "details": [{"rule": a.trigger_rule, "severity": a.severity,
                     "cells": a.affected_cells_count} for a in alerts],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
