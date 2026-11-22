"""
Batch Risk Calculator — CLI

Loads spatial evidence data, runs the risk engine, compares with previous
observations, and updates the database.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS, setup_logging
from src.features.risk_engine import run_risk_assessment, save_risk_to_database

logger = setup_logging("calculate_risk")


def load_evidence_data(csv_path: str = None) -> pd.DataFrame:
    """Load spatial evidence from CSV or database."""
    if csv_path and Path(csv_path).exists():
        df = pd.read_csv(csv_path)
        logger.info("Loaded %d records from %s.", len(df), Path(csv_path).name)
        return df

    # Try default path
    default = PATHS.spatial_evidence_csv
    if default.exists():
        df = pd.read_csv(default)
        logger.info("Loaded %d records from %s.", len(df), default.name)
        return df

    # Try database
    try:
        from src.data.db import get_db
        db = get_db()
        cells = db.get_all_grid_cells()
        if cells:
            df = pd.DataFrame(cells)
            logger.info("Loaded %d records from database.", len(df))
            return df
    except Exception as e:
        logger.warning("Database load failed: %s", e)

    logger.error("No evidence data found.")
    return pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description="Calculate landslide risk for Tirumala grid.")
    parser.add_argument(
        "--observation-date",
        help="Observation date (YYYY-MM-DD); defaults to the latest processed InSAR pair.",
    )
    parser.add_argument("--input-csv", default=None, help="Input evidence CSV.")
    parser.add_argument("--compare-with-date", default=None, help="Previous observation date.")
    parser.add_argument("--output-csv", default=None, help="Output risk CSV.")
    parser.add_argument("--save-db", action="store_true", default=True)
    args = parser.parse_args()

    from src.data.db import get_db

    db = get_db()
    observation_date = args.observation_date
    if observation_date is None:
        observation_date = db.get_latest_processed_insar_date()
        if observation_date is None:
            parser.error("No processed InSAR pair date is available; pass --observation-date explicitly.")

    # Load current data
    current_data = load_evidence_data(args.input_csv)
    if current_data.empty:
        return

    prior_dates = [
        date for date in db.get_observation_dates()
        if date < observation_date
    ]
    comparison_date = args.compare_with_date
    if comparison_date is not None:
        if comparison_date >= observation_date:
            parser.error("--compare-with-date must precede --observation-date.")
        if comparison_date not in prior_dates:
            parser.error(f"No stored observation exists for {comparison_date}.")
    elif prior_dates:
        comparison_date = prior_dates[-1]

    historical_observations = []
    previous_data = None
    if comparison_date is not None:
        rows = db.get_observations_for_date(comparison_date)
        if rows:
            previous_data = pd.DataFrame(rows)
            historical_observations.append(previous_data)
            logger.info(
                "Loaded %d previous risk snapshots for %s.",
                len(previous_data),
                comparison_date,
            )

    # Run assessment
    result = run_risk_assessment(
        current_data=current_data,
        observation_date=observation_date,
        previous_data=previous_data,
        historical_observations=historical_observations,
    )

    # Save to database
    if args.save_db:
        save_risk_to_database(result, db)

    # Export CSV
    if result.scored_df is not None and not result.scored_df.empty:
        out_path = args.output_csv or str(
            PATHS.data_features / f"tirumala_risk_{observation_date}.csv"
        )
        result.scored_df.to_csv(out_path, index=False)
        logger.info("Risk CSV exported: %s", out_path)

    # Print summary
    summary = {
        "observation_date": result.observation_date,
        "total_cells": result.total_cells,
        "low": result.low_count,
        "medium": result.medium_count,
        "high": result.high_count,
        "mean_score": result.mean_score,
        "max_score": result.max_score,
        "transitions": result.transitions,
        "persistent_hotspots": result.persistent_high_cells,
        "newly_elevated": result.newly_elevated_cells,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
