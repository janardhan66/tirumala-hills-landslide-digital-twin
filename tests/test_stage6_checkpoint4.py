import numpy as np

from src.environmental.feature_engineering import (
    QUALITY_STATES,
    quality_state,
    normalize_slope_percentile,
    normalize_los_abs,
    circular_aspect_components,
    independent_rainfall_rollups,
    define_environmental_features,
)
from src.risk_assessment import WEIGHTS


def test_aspect_minus_one_is_undefined_not_direction():
    east, north = circular_aspect_components(np.array([-1.0, 0.0, 90.0]))
    assert np.isnan(east[0])
    assert np.isnan(north[0])
    assert east[1] == 0.0
    assert north[1] == 1.0


def test_slope_percentile_normalization_preserves_missing():
    result = normalize_slope_percentile(np.array([10.0, np.nan, 20.0]))
    assert np.isnan(result[1])
    assert result[0] == 50.0
    assert result[2] == 100.0


def test_los_abs_normalization_preserves_missing():
    result = normalize_los_abs(np.array([-0.02, np.nan, -0.04]))
    assert np.isnan(result[1])
    assert result[0] == 0.0
    assert result[2] == 100.0


def test_quality_states_are_distinguishable():
    assert quality_state(False) == "MISSING"
    assert quality_state(True, False) == "INSUFFICIENT_QUALITY"
    assert quality_state(True, True, True) == "REQUIRES_RECONCILIATION"
    assert quality_state(True, True, False, True) == "AVAILABLE_WITH_LIMITATION"
    assert quality_state(True) == "AVAILABLE"
    assert set(QUALITY_STATES) == {
        "AVAILABLE",
        "AVAILABLE_WITH_LIMITATION",
        "INSUFFICIENT_QUALITY",
        "MISSING",
        "NOT_APPLICABLE",
        "REQUIRES_RECONCILIATION",
        "BLOCKED",
    }


def test_independent_rainfall_rollups_require_complete_calendar_windows():
    values = {
        "2026-08-01": 5.5,
        "2026-08-02": 6.1,
        "2026-08-03": 3.2,
        "2026-08-04": None,
        "2026-08-05": 1.3,
    }
    result = independent_rainfall_rollups(values)
    assert result["2026-08-03"]["rolling_3day_mm"] == 14.8
    assert result["2026-08-04"]["rolling_3day_complete"] is False
    assert result["2026-08-04"]["rolling_3day_mm"] is None
    assert result["2026-08-05"]["rolling_7day_complete"] is False
    assert result["2026-08-05"]["rolling_7day_mm"] is None


def test_feature_specification_does_not_activate_risk_or_unet():
    features = define_environmental_features()
    keys = {feature["feature_key"] for feature in features}
    assert "slope_deg" in keys
    assert "insar_los_m" in keys
    assert "rainfall_3day_mm" in keys
    assert "unet_benchmark" in keys
    unet = next(feature for feature in features if feature["feature_key"] == "unet_benchmark")
    assert unet["availability_state"] == "BLOCKED"


def test_existing_risk_weights_are_unchanged():
    from src.risk_assessment import WEIGHTS

    assert WEIGHTS == {
        "slope_component": 0.40,
        "terrain_component": 0.25,
        "insar_component": 0.20,
        "temporal_component": 0.15,
    }
