"""
Enhanced Risk Assessment Engine with Temporal Comparison

Extends the existing weighted evidence scoring (src/risk_assessment.py) with:
- Historical comparison between observation dates
- Transition matrix calculation
- Persistent hotspot detection
- Database integration
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import setup_logging
from src.risk_assessment import build_spatial_risk

logger = setup_logging("risk_engine")


@dataclass
class RiskAssessmentResult:
    """Complete result from a risk assessment cycle."""
    observation_date: str
    total_cells: int = 0
    low_count: int = 0
    medium_count: int = 0
    high_count: int = 0
    mean_score: float = 0.0
    max_score: float = 0.0
    # Transitions (compared with previous observation)
    transitions: Dict[str, int] = field(default_factory=dict)
    persistent_high_cells: int = 0
    newly_elevated_cells: int = 0
    # Data
    scored_df: Optional[pd.DataFrame] = None
    area_summary: Optional[Dict] = None


def calculate_risk_scores(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """
    Calculate risk scores using the existing weighted evidence method.
    
    Returns (scored_dataframe, area_summary_dict).
    """
    scored_df, summary = build_spatial_risk(df)
    return scored_df, summary


def compute_transitions(
    current_df: pd.DataFrame, previous_df: pd.DataFrame,
    cell_key: str = "cell_id",
) -> Dict[str, int]:
    """
    Compute risk category transitions between two observation dates.
    
    Returns dict with keys like 'Low→Medium', 'Medium→High', etc.
    """
    if current_df.empty or previous_df.empty:
        return {}

    if "risk_category" not in current_df.columns or "risk_category" not in previous_df.columns:
        return {}

    def categories_by_cell(frame: pd.DataFrame) -> Optional[Dict[str, str]]:
        if cell_key in frame.columns:
            keys = frame[cell_key].astype(str)
        elif "row" in frame.columns and "col" in frame.columns:
            keys = frame["row"].astype(str) + "_" + frame["col"].astype(str)
        else:
            return None
        if keys.duplicated().any():
            raise ValueError(f"Duplicate spatial cell keys found for {cell_key}.")
        return dict(zip(keys, frame["risk_category"].astype(str)))

    current_categories = categories_by_cell(current_df)
    previous_categories = categories_by_cell(previous_df)
    if current_categories is None or previous_categories is None:
        logger.warning("No matching cell key column found for transition comparison.")
        return {}
    transitions = {
        "Low→Medium": 0, "Low→High": 0,
        "Medium→Low": 0, "Medium→High": 0,
        "High→Low": 0, "High→Medium": 0,
        "Unchanged": 0,
    }

    for cell_id in current_categories.keys() & previous_categories.keys():
        prev = previous_categories[cell_id]
        curr = current_categories[cell_id]
        key = f"{prev}→{curr}"
        if key in transitions:
            transitions[key] += 1
        elif prev == curr:
            transitions["Unchanged"] += 1

    return transitions


def identify_persistent_hotspots(
    observations: List[pd.DataFrame],
    threshold_category: str = "High",
    min_consecutive: int = 2,
) -> List[str]:
    """
    Identify cells that have been classified as High risk across
    multiple consecutive observation dates.
    
    Returns list of cell identifiers.
    """
    if min_consecutive < 1:
        raise ValueError("min_consecutive must be a positive integer.")
    if len(observations) < min_consecutive:
        return []

    consecutive = observations[-min_consecutive:]
    high_cell_sets = []
    for observation in consecutive:
        if "risk_category" not in observation.columns:
            return []
        if "cell_id" in observation.columns:
            keys = observation["cell_id"].astype(str)
        elif "row" in observation.columns and "col" in observation.columns:
            keys = observation["row"].astype(str) + "_" + observation["col"].astype(str)
        else:
            return []
        if keys.duplicated().any():
            raise ValueError("Duplicate spatial cell keys found in risk history.")
        high_cell_sets.append(
            set(keys[observation["risk_category"] == threshold_category])
        )

    persistent = set.intersection(*high_cell_sets) if high_cell_sets else set()
    return sorted(persistent)


def identify_newly_elevated(
    current_df: pd.DataFrame, previous_df: pd.DataFrame,
) -> List[str]:
    """
    Identify cells that transitioned to High risk in the current observation.
    """
    if "risk_category" not in current_df.columns or "risk_category" not in previous_df.columns:
        return []

    def categories_by_cell(frame: pd.DataFrame) -> Optional[Dict[str, str]]:
        if "cell_id" in frame.columns:
            keys = frame["cell_id"].astype(str)
        elif "row" in frame.columns and "col" in frame.columns:
            keys = frame["row"].astype(str) + "_" + frame["col"].astype(str)
        else:
            return None
        if keys.duplicated().any():
            raise ValueError("Duplicate spatial cell keys found in risk history.")
        return dict(zip(keys, frame["risk_category"].astype(str)))

    current_categories = categories_by_cell(current_df)
    previous_categories = categories_by_cell(previous_df)
    if current_categories is None or previous_categories is None:
        return []
    return sorted(
        cell_id
        for cell_id, category in current_categories.items()
        if category == "High"
        and cell_id in previous_categories
        and previous_categories[cell_id] != "High"
    )


def run_risk_assessment(
    current_data: pd.DataFrame,
    observation_date: str,
    previous_data: Optional[pd.DataFrame] = None,
    historical_observations: Optional[List[pd.DataFrame]] = None,
) -> RiskAssessmentResult:
    """
    Execute a full risk assessment cycle.
    
    Parameters
    ----------
    current_data : DataFrame
        Current spatial evidence with slope, elevation, InSAR columns.
    observation_date : str
        Date string for this assessment.
    previous_data : DataFrame, optional
        Previous observation for transition analysis.
    historical_observations : list of DataFrames, optional
        Multiple past observations for hotspot detection.
    """
    try:
        parsed_date = datetime.strptime(observation_date, "%Y-%m-%d")
        if parsed_date.strftime("%Y-%m-%d") != observation_date:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("Risk observation date must use YYYY-MM-DD format.") from exc

    result = RiskAssessmentResult(observation_date=observation_date)

    # Step 1: Calculate risk scores
    scored_df, summary = calculate_risk_scores(current_data)
    result.scored_df = scored_df
    result.area_summary = summary
    result.total_cells = len(scored_df) if not scored_df.empty else 0

    if scored_df.empty:
        logger.warning("No valid cells for risk assessment.")
        return result

    # Count categories
    cats = scored_df["risk_category"].value_counts()
    result.low_count = int(cats.get("Low", 0))
    result.medium_count = int(cats.get("Medium", 0))
    result.high_count = int(cats.get("High", 0))

    scores = scored_df["risk_score"].dropna()
    result.mean_score = round(float(scores.mean()), 2) if not scores.empty else 0
    result.max_score = round(float(scores.max()), 2) if not scores.empty else 0

    logger.info(
        "Risk assessment (%s): %d cells — L:%d, M:%d, H:%d (mean=%.1f, max=%.1f)",
        observation_date, result.total_cells,
        result.low_count, result.medium_count, result.high_count,
        result.mean_score, result.max_score,
    )

    # Step 2: Transitions
    if previous_data is not None and not previous_data.empty:
        if {"risk_score", "risk_category"}.issubset(previous_data.columns):
            prev_scored = previous_data
        else:
            prev_scored, _ = calculate_risk_scores(previous_data)
        result.transitions = compute_transitions(scored_df, prev_scored)
        result.newly_elevated_cells = len(identify_newly_elevated(scored_df, prev_scored))
        logger.info("Transitions: %s", result.transitions)

    # Step 3: Persistent hotspots
    if historical_observations:
        all_obs = historical_observations + [scored_df]
        hotspots = identify_persistent_hotspots(all_obs)
        result.persistent_high_cells = len(hotspots)
        logger.info("Persistent high-evidence hotspots: %d cells.", result.persistent_high_cells)

    return result


def save_risk_to_database(result: RiskAssessmentResult, db=None):
    """Save risk assessment results to the database."""
    if db is None:
        from src.data.db import get_db
        db = get_db()

    if result.scored_df is not None and not result.scored_df.empty:
        if "cell_id" not in result.scored_df.columns:
            if "row" in result.scored_df.columns and "col" in result.scored_df.columns:
                result.scored_df["cell_id"] = [
                    f"R{int(r)}_C{int(c)}"
                    for r, c in zip(result.scored_df["row"], result.scored_df["col"])
                ]
            elif "row_idx" in result.scored_df.columns and "col_idx" in result.scored_df.columns:
                result.scored_df["cell_id"] = [
                    f"R{int(r)}_C{int(c)}"
                    for r, c in zip(result.scored_df["row_idx"], result.scored_df["col_idx"])
                ]
            elif "id" in result.scored_df.columns:
                result.scored_df["cell_id"] = result.scored_df["id"]
            else:
                result.scored_df["cell_id"] = [f"CELL_{i:05d}" for i in range(len(result.scored_df))]

        required = {"cell_id", "risk_score", "risk_category"}
        missing = required - set(result.scored_df.columns)
        if missing:
            raise ValueError(
                "Per-cell risk results cannot be saved; missing columns: "
                + ", ".join(sorted(missing))
            )
        snapshots = result.scored_df[
            ["cell_id", "risk_score", "risk_category"]
        ].copy()
        snapshots["observation_date"] = result.observation_date

        with db.cursor() as cur:
            rows = cur.execute("SELECT cell_id FROM spatial_evidence_grid").fetchall()
            valid_ids = {r[0] for r in rows}

        valid_snapshots = snapshots[snapshots["cell_id"].isin(valid_ids)]
        if not valid_snapshots.empty:
            db.bulk_add_observation_snapshots(
                valid_snapshots.to_dict(orient="records")
            )

    db.upsert_risk_history(
        observation_date=result.observation_date,
        total_cells=result.total_cells,
        low_count=result.low_count,
        medium_count=result.medium_count,
        high_count=result.high_count,
        mean_risk_score=result.mean_score,
        max_risk_score=result.max_score,
        low_to_medium=result.transitions.get("Low→Medium", 0),
        low_to_high=result.transitions.get("Low→High", 0),
        medium_to_high=result.transitions.get("Medium→High", 0),
        medium_to_low=result.transitions.get("Medium→Low", 0),
        high_to_medium=result.transitions.get("High→Medium", 0),
        high_to_low=result.transitions.get("High→Low", 0),
        persistent_high_cells=result.persistent_high_cells,
    )
    logger.info("Risk history saved to database for %s.", result.observation_date)
