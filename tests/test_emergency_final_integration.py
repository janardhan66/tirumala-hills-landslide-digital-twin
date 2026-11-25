import json
from pathlib import Path

import pandas as pd

from config.settings import PATHS
from src.monitoring.final_integration import export_final_status, load_unified_status
from src.risk_assessment import build_spatial_risk, explain_risk_row


def test_final_status_exports_real_persistence_and_limitations():
    payload = export_final_status()
    assert payload["overall_status"] == "DEMONSTRATION_READY_WITH_LIMITATIONS"
    assert payload["project"]["temporal_inversion"] == "NOT_RELIABLE_WITH_SINGLE_PAIR"
    assert payload["project"]["risk_model"] == "EMPIRICAL_EVIDENCE_INDEX"
    assert payload["preservation"]["acquisitions"] == 20
    assert payload["preservation"]["insar_pairs"] == 3
    assert payload["preservation"]["rainfall_records"] == 29
    assert payload["preservation"]["observation_snapshots"] > 0
    assert payload["preservation"]["temporal_insar_observations"] == 7590
    assert "No real cumulative LOS displacement or velocity" in payload["limitations"][0]

    destination = PATHS.viewer_data / "master_final_status.json"
    assert destination.is_file()
    json.dumps(json.loads(destination.read_text(encoding="utf-8")), allow_nan=False)


def test_existing_empirical_risk_formula_is_preserved():
    frame = pd.DataFrame({
        "cell_id": ["low", "high"],
        "slope_deg": [5.0, 40.0],
        "terrain_high_evidence": [0, 1],
        "insar_high_evidence": [0, 1],
        "temporal_evidence_flag": [0, 1],
    })
    scored, summary = build_spatial_risk(frame)
    assert scored["risk_score"].tolist() == [20.0, 100.0]
    assert summary["category"] in {"Low", "Medium", "High"}
    explained = explain_risk_row(scored.iloc[0])
    assert explained["disclaimer"].startswith("This is a relative empirical evidence index")
    assert "factor_availability" in explained


def test_missing_factor_is_excluded_not_zeroed():
    frame = pd.DataFrame({
        "cell_id": ["A"],
        "slope_deg": [20.0],
    })
    scored, _ = build_spatial_risk(frame)
    assert scored.loc[0, "risk_evidence_coverage"] == 40.0

    explained = explain_risk_row(scored.iloc[0])
    assert explained["factor_availability"]["terrain_component"] is False
    assert explained["factor_availability"]["insar_component"] is False
    assert explained["factor_availability"]["temporal_component"] is False


def test_cesium_manifest_preserves_real_assets_and_status_metadata():
    manifest_path = PATHS.viewer_cesium / "layers_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["terrain"]["base_elevation_m"] == 180.02676391601562
    layer_ids = {layer["id"] for layer in manifest["layers"]}
    assert {"elevation", "slope", "aspect", "los", "coherence", "risk_zones"} <= layer_ids
    pair_ids = {pair["pair_id"] for pair in manifest["temporal"]["insar_pairs"]}
    assert "PAIR_20261109_20261121" in pair_ids
    risk = next(layer for layer in manifest["layers"] if layer["id"] == "risk_zones")
    assert risk["quality_status"] == "EMPIRICAL_EVIDENCE_NOT_CALIBRATED"


def test_missing_rainfall_never_generates_a_rainfall_alert():
    from src.agent.alert_engine import AlertRulesEngine

    engine = AlertRulesEngine()
    alerts = engine.evaluate_all_rules(
        pd.DataFrame({"cell_id": ["A"], "slope_deg": [40.0], "risk_score": [80.0]}),
        rainfall_3day_mm=None,
        observation_date="2026-11-21",
    )
    assert all(alert.trigger_rule != "RULE_1_RAINFALL_SLOPE" for alert in alerts)
