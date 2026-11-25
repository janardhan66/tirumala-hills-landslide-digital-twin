"""Stage 6 Checkpoint 4 feature specification and quality framework.

This module defines experimental features and eligibility rules only. It does
not activate or calculate a new landslide risk formula.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


QUALITY_STATES = (
    "AVAILABLE",
    "AVAILABLE_WITH_LIMITATION",
    "INSUFFICIENT_QUALITY",
    "MISSING",
    "NOT_APPLICABLE",
    "REQUIRES_RECONCILIATION",
    "BLOCKED",
)


def quality_state(
    value_exists: bool,
    quality_passed: bool = True,
    reconciliation_required: bool = False,
    limitation: bool = False,
) -> str:
    if reconciliation_required:
        return "REQUIRES_RECONCILIATION"
    if not value_exists:
        return "MISSING"
    if not quality_passed:
        return "INSUFFICIENT_QUALITY"
    if limitation:
        return "AVAILABLE_WITH_LIMITATION"
    return "AVAILABLE"


def normalize_slope_percentile(values: np.ndarray) -> np.ndarray:
    finite = np.isfinite(values)
    out = np.full(values.shape, np.nan, dtype=np.float64)
    if not np.any(finite):
        return out
    series = pd.Series(values[finite])
    ranked = series.rank(pct=True).to_numpy() * 100.0
    out[finite] = ranked
    return out


def normalize_los_abs(values: np.ndarray) -> np.ndarray:
    """Optional exploratory absolute LOS normalization by the observed range."""
    finite = np.isfinite(values)
    out = np.full(values.shape, np.nan, dtype=np.float64)
    if not np.any(finite):
        return out
    absolute = np.abs(values[finite])
    minimum = float(absolute.min())
    maximum = float(absolute.max())
    if maximum - minimum < 1e-12:
        out[finite] = 0.0
    else:
        out[finite] = (absolute - minimum) / (maximum - minimum) * 100.0
    return out


def circular_aspect_components(
    aspect_degrees: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert aspect to sine/cosine; -1 is undefined and becomes NaN."""
    values = np.asarray(aspect_degrees, dtype=np.float64)
    defined = np.isfinite(values) & (values >= 0.0) & (values <= 360.0)
    radians = np.radians(values)
    east = np.full(values.shape, np.nan, dtype=np.float64)
    north = np.full(values.shape, np.nan, dtype=np.float64)
    east[defined] = np.sin(radians[defined])
    north[defined] = np.cos(radians[defined])
    return east, north


def independent_rainfall_rollups(
    daily_values: Dict[str, Optional[float]],
) -> Dict[str, Dict[str, Optional[float]]]:
    """Calculate D, D-2 and D-6/D-13 complete calendar windows."""
    records: Dict[str, Dict[str, Optional[float]]] = {}
    for date_text, daily in daily_values.items():
        current = datetime.strptime(date_text, "%Y-%m-%d").date()
        windows = {}
        for window in (3, 7, 14):
            dates = [
                (current - timedelta(days=offset)).isoformat()
                for offset in range(window - 1, -1, -1)
            ]
            window_values = [daily_values.get(day) for day in dates]
            complete = (
                len(window_values) == window
                and all(
                    value is not None and np.isfinite(float(value))
                    for value in window_values
                )
            )
            windows[f"rolling_{window}day_mm"] = (
                round(sum(float(value) for value in window_values), 2)
                if complete
                else None
            )
            windows[f"rolling_{window}day_complete"] = complete
        records[date_text] = windows
    return records


def define_environmental_features() -> List[Dict]:
    return [
        {
            "feature_key": "dem_elevation_m",
            "feature_name": "Elevation",
            "data_source": "Local aligned DEM",
            "spatial_temporal_grain": "spatial pixel/cell",
            "unit": "metres",
            "availability_state": "AVAILABLE",
            "normalization_method": "No new formula in this checkpoint; exploratory range reporting",
            "missing_data_rule": "Missing remains unavailable; DEM NoData 0.0 is screened.",
            "limitations": "Elevation is a terrain descriptor, not a direct landslide outcome.",
        },
        {
            "feature_key": "slope_deg",
            "feature_name": "Slope angle",
            "data_source": "Local aligned slope raster",
            "spatial_temporal_grain": "spatial pixel/cell",
            "unit": "degrees",
            "availability_state": "AVAILABLE",
            "normalization_method": "Optional study-area percentile",
            "missing_data_rule": "NoData or nonfinite values remain missing.",
            "limitations": "Any threshold is exploratory unless supported by local evidence.",
        },
        {
            "feature_key": "aspect_sin_cos",
            "feature_name": "Aspect circular components",
            "data_source": "Local aligned aspect raster",
            "spatial_temporal_grain": "spatial pixel/cell",
            "unit": "dimensionless sine/cosine",
            "availability_state": "AVAILABLE_WITH_LIMITATION",
            "normalization_method": "Circular sine/cosine; undefined -1 becomes missing",
            "missing_data_rule": "-1 and NoData remain missing.",
            "limitations": "Aspect circularity and slope interaction require local evaluation.",
        },
        {
            "feature_key": "insar_los_m",
            "feature_name": "Relative LOS displacement",
            "data_source": "PAIR_20261109_20261121 HyP3 LOS raster",
            "spatial_temporal_grain": "pair-specific spatial observation",
            "unit": "metres relative LOS",
            "availability_state": "AVAILABLE_WITH_LIMITATION",
            "normalization_method": "Optional absolute-range normalization for exploratory display only",
            "missing_data_rule": "NaN, NoData and low-quality cells remain missing.",
            "limitations": "Pair-specific phase reference; no vertical or velocity interpretation.",
        },
        {
            "feature_key": "insar_coherence",
            "feature_name": "InSAR coherence",
            "data_source": "PAIR_20261109_20261121 HyP3 coherence raster",
            "spatial_temporal_grain": "pair-specific spatial observation",
            "unit": "0-1",
            "availability_state": "AVAILABLE_WITH_LIMITATION",
            "normalization_method": "Direct 0-1 value; threshold is quality eligibility only",
            "missing_data_rule": "NaN/NoData remain missing.",
            "limitations": "Low coherence is unavailable evidence, not zero displacement.",
        },
        {
            "feature_key": "rainfall_3day_mm",
            "feature_name": "3-day rainfall accumulation",
            "data_source": "Existing GPM IMERG V07C-derived study-area CSV",
            "spatial_temporal_grain": "study-area temporal",
            "unit": "mm",
            "availability_state": "REQUIRES_RECONCILIATION",
            "normalization_method": "No per-cell normalization; complete D/D-1/D-2 sums only",
            "missing_data_rule": "Incomplete or discrepant windows remain unavailable.",
            "limitations": "Study-area aggregate, not local pixel rainfall.",
        },
        {
            "feature_key": "rainfall_7day_mm",
            "feature_name": "7-day rainfall accumulation",
            "data_source": "Existing GPM IMERG V07C-derived study-area records",
            "spatial_temporal_grain": "study-area temporal",
            "unit": "mm",
            "availability_state": "REQUIRES_RECONCILIATION",
            "normalization_method": "Complete D through D-6 sum only",
            "missing_data_rule": "Incomplete or discrepant windows remain unavailable.",
            "limitations": "Study-area aggregate.",
        },
        {
            "feature_key": "rainfall_14day_mm",
            "feature_name": "14-day rainfall accumulation",
            "data_source": "Existing GPM IMERG V07C-derived study-area records",
            "spatial_temporal_grain": "study-area temporal",
            "unit": "mm",
            "availability_state": "REQUIRES_RECONCILIATION",
            "normalization_method": "Complete D through D-13 sum only",
            "missing_data_rule": "Incomplete or discrepant windows remain unavailable.",
            "limitations": "Study-area aggregate.",
        },
        {
            "feature_key": "gsi_proximity_km",
            "feature_name": "GSI mapped location proximity",
            "data_source": "GSI Figure 3.2 map-derived coordinates",
            "spatial_temporal_grain": "spatial exploratory context",
            "unit": "km",
            "availability_state": "AVAILABLE_WITH_LIMITATION",
            "normalization_method": "Nearest approximate inventory point; exploratory inverse-distance only",
            "missing_data_rule": "Outside grid or missing coordinate remains unavailable.",
            "limitations": "Approximate map-derived locations are not surveyed ground truth.",
        },
        {
            "feature_key": "unet_benchmark",
            "feature_name": "Landslide4Sense U-Net benchmark",
            "data_source": "Landslide4Sense H5 benchmark dataset",
            "spatial_temporal_grain": "benchmark patch only",
            "unit": "non-georeferenced mask coverage",
            "availability_state": "BLOCKED",
            "normalization_method": "No Tirumala normalization or georeferencing",
            "missing_data_rule": "No valid georeferenced Tirumala input exists.",
            "limitations": "No local accuracy claim; checkpoint is benchmark-only.",
        },
    ]


def build_feature_definition_records() -> List[Dict]:
    records = []
    for spec in define_environmental_features():
        records.append({
            "feature_key": spec["feature_key"],
            "feature_name": spec["feature_name"],
            "data_source": spec["data_source"],
            "spatial_temporal_grain": spec["spatial_temporal_grain"],
            "unit": spec["unit"],
            "availability_state": spec["availability_state"],
            "normalization_method": spec["normalization_method"],
            "missing_data_rule": spec["missing_data_rule"],
            "limitations": spec["limitations"],
            "spec_json": json.dumps(spec, sort_keys=True),
        })
    return records


def build_explainability_schema() -> Dict:
    return {
        "cell_id": "Spatial 69x110 grid identifier",
        "current_assessment": "Existing empirical evidence result only",
        "previous_assessment": "Previous observation date and category",
        "available_factors": "Factors with quality-eligible values",
        "missing_factors": "Factors with MISSING or NOT_APPLICABLE state",
        "insufficient_factors": "Factors with INSUFFICIENT_QUALITY state",
        "factor_contributions": "Descriptive contribution, not a calibrated percentage",
        "change_reason": "Data change, quality change or unavailable data",
        "limitation_text": "Source and phase/reference limitation",
        "calibration_status": "NOT_CALIBRATED",
    }
