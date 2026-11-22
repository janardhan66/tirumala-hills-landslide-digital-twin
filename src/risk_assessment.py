"""Transparent, relative landslide evidence index for the Tirumala dashboard.

This is NOT a calibrated landslide probability or operational warning model.
It uses only available spatial evidence columns and omits unavailable features.
Study-area rainfall is deliberately kept as contextual information because the
current rainfall file is not a pixel/location-specific spatial predictor.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

WEIGHTS = {
    "slope_component": 0.40,
    "terrain_component": 0.25,
    "insar_component": 0.20,
    "temporal_component": 0.15,
}


def _numeric_column(frame: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    for name in candidates:
        if name in frame.columns:
            values = pd.to_numeric(frame[name], errors="coerce")
            if values.notna().any():
                return values
    return None


def _binary_column(frame: pd.DataFrame, candidates: list[str]) -> pd.Series | None:
    for name in candidates:
        if name in frame.columns:
            raw = frame[name]
            numeric = pd.to_numeric(raw, errors="coerce")
            if numeric.notna().any():
                return numeric.where(numeric.isin([0, 1])) * 100.0
            text = raw.astype(str).str.strip().str.lower()
            mapped = text.map({
                "true": 100.0, "yes": 100.0, "1": 100.0, "high": 100.0,
                "false": 0.0, "no": 0.0, "0": 0.0, "low": 0.0,
            })
            if mapped.notna().any():
                return mapped
    return None


def classify_score(score: float) -> str:
    if score < 33.3333:
        return "Low"
    if score < 66.6667:
        return "Medium"
    return "High"


def build_spatial_risk(
    frame: pd.DataFrame,
    weights: Mapping[str, float] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Return relative evidence scores, optionally using sensitivity weights."""
    selected_weights = dict(WEIGHTS if weights is None else weights)
    if set(selected_weights) != set(WEIGHTS):
        raise ValueError(f"Weights must contain exactly: {', '.join(WEIGHTS)}.")
    if any(not np.isfinite(value) or value < 0 for value in selected_weights.values()):
        raise ValueError("Risk weights must be finite and non-negative.")
    total_weight = sum(selected_weights.values())
    if total_weight <= 0:
        raise ValueError("At least one risk weight must be greater than zero.")

    if frame is None or frame.empty:
        return pd.DataFrame(), {"score": None, "category": "Unavailable", "count": 0}

    out = frame.copy()
    components: dict[str, pd.Series] = {}

    slope = _numeric_column(out, ["slope_deg", "slope", "mean_slope_deg"])
    if slope is not None:
        # Relative percentile within the current study-area observations.
        components["slope_component"] = slope.rank(pct=True) * 100.0

    terrain = _binary_column(out, ["terrain_high_evidence", "terrain_high_flag"])
    if terrain is not None:
        components["terrain_component"] = terrain

    insar = _binary_column(out, ["insar_high_evidence", "insar_high_flag"])
    if insar is not None:
        components["insar_component"] = insar

    temporal = _binary_column(out, ["temporal_evidence_flag"])
    if temporal is not None:
        components["temporal_component"] = temporal

    if not components:
        return pd.DataFrame(), {"score": None, "category": "Unavailable", "count": 0}

    weighted_sum = pd.Series(0.0, index=out.index)
    available_weight = pd.Series(0.0, index=out.index)
    for name, values in components.items():
        weight = selected_weights[name]
        valid = values.notna()
        weighted_sum.loc[valid] += values.loc[valid] * weight
        available_weight.loc[valid] += weight
        out[name] = values

    out["risk_score"] = (weighted_sum / available_weight.replace(0, np.nan)).round(2)
    out["risk_category"] = out["risk_score"].apply(
        lambda value: classify_score(float(value)) if pd.notna(value) else "Unavailable"
    )
    out["risk_evidence_coverage"] = (available_weight / total_weight * 100).round(1)

    valid_scores = out["risk_score"].dropna()
    if valid_scores.empty:
        summary = {"score": None, "category": "Unavailable", "count": 0}
    else:
        # Median prevents a small number of extreme points dominating the area summary.
        area_score = round(float(valid_scores.median()), 2)
        summary = {
            "score": area_score,
            "category": classify_score(area_score),
            "count": int(valid_scores.size),
        }
    return out, summary
