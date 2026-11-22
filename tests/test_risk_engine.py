import pandas as pd
import pytest

from src.data.db import DatabaseManager
from src.features.risk_engine import (
    identify_newly_elevated,
    identify_persistent_hotspots,
    run_risk_assessment,
    save_risk_to_database,
)
from src.risk_assessment import build_spatial_risk


def test_newly_elevated_requires_matching_cell_in_previous_observation():
    current = pd.DataFrame({
        "cell_id": ["existing", "new"],
        "risk_category": ["High", "High"],
    })
    previous = pd.DataFrame({
        "cell_id": ["existing"],
        "risk_category": ["Low"],
    })

    assert identify_newly_elevated(current, previous) == ["existing"]


def test_hotspots_must_be_high_in_consecutive_observations():
    high = pd.DataFrame({"cell_id": ["A"], "risk_category": ["High"]})
    low = pd.DataFrame({"cell_id": ["A"], "risk_category": ["Low"]})

    assert identify_persistent_hotspots([high, low, high]) == []
    assert identify_persistent_hotspots([low, high, high]) == ["A"]


def test_duplicate_cell_keys_are_rejected_in_hotspot_history():
    duplicated = pd.DataFrame({
        "cell_id": ["A", "A"],
        "risk_category": ["High", "High"],
    })

    with pytest.raises(ValueError, match="Duplicate spatial cell keys"):
        identify_persistent_hotspots([duplicated, duplicated])


def test_risk_assessment_rejects_noncanonical_dates():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        run_risk_assessment(
            pd.DataFrame({"cell_id": ["A"], "slope_deg": [10]}),
            "2026-8-29",
        )


def test_custom_sensitivity_weights_recalculate_real_spatial_evidence():
    frame = pd.DataFrame({
        "cell_id": ["low", "high"],
        "slope_deg": [5.0, 40.0],
        "terrain_high_evidence": [0, 1],
        "insar_high_evidence": [0, 1],
        "temporal_evidence_flag": [0, 1],
    })

    standard, _ = build_spatial_risk(frame)
    slope_only, _ = build_spatial_risk(frame, {
        "slope_component": 1.0,
        "terrain_component": 0.0,
        "insar_component": 0.0,
        "temporal_component": 0.0,
    })

    assert standard["risk_score"].tolist() != slope_only["risk_score"].tolist()
    assert slope_only["risk_score"].tolist() == [50.0, 100.0]


def test_custom_sensitivity_weights_reject_invalid_values():
    with pytest.raises(ValueError, match="non-negative"):
        build_spatial_risk(pd.DataFrame({"slope_deg": [10]}), {
            "slope_component": -1.0,
            "terrain_component": 1.0,
            "insar_component": 0.0,
            "temporal_component": 0.0,
        })


def test_alert_persistence_deduplicates_rule_and_observation(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import patch

    from src.agent.alert_engine import AlertPayload, save_alerts_to_db

    db = DatabaseManager(tmp_path / "alerts.db")
    alert = AlertPayload(
        trigger_rule="RULE_TEST",
        observation_date="2026-08-29",
        summary="Test evidence requiring review.",
        recommended_action="Review the evidence.",
    )
    empty_credentials = SimpleNamespace(
        telegram_bot_token="",
        telegram_chat_id="",
        smtp_username="",
        smtp_password="",
        alert_email_to="",
    )

    with (
        patch("src.agent.alert_engine.get_db", return_value=db),
        patch("src.agent.alert_engine.CREDENTIALS", empty_credentials),
        patch("src.agent.alert_engine.export_alerts_geojson"),
    ):
        assert save_alerts_to_db([alert]) == 1
        assert save_alerts_to_db([alert]) == 0

    with db.cursor() as cursor:
        count = cursor.execute(
            "SELECT COUNT(*) FROM alerts WHERE trigger_rule = 'RULE_TEST' "
            "AND observation_date = '2026-08-29'"
        ).fetchone()[0]
    assert count == 1
    db.close()


def test_database_managers_keep_connections_to_their_own_files(tmp_path):
    first = DatabaseManager(tmp_path / "first.db")
    second = DatabaseManager(tmp_path / "second.db")
    first.add_acquisition(
        acquisition_id="first-only",
        satellite="Sentinel-1",
        product_type="SLC",
        acquisition_date="2026-08-17",
    )

    assert first.get_acquisition("first-only") is not None
    assert second.get_acquisition("first-only") is None

    first.close()
    second.close()


def test_latest_processed_insar_date_excludes_unprocessed_pairs(tmp_path):
    db = DatabaseManager(tmp_path / "pairs.db")
    for acquisition_id, date in [
        ("ref-1", "2026-08-05"),
        ("sec-1", "2026-08-17"),
        ("ref-2", "2026-08-17"),
        ("sec-2", "2026-08-29"),
    ]:
        db.add_acquisition(
            acquisition_id=acquisition_id,
            satellite="Sentinel-1",
            product_type="SLC",
            acquisition_date=date,
        )
    db.add_insar_pair(
        pair_id="processed",
        reference_acq_id="ref-1",
        secondary_acq_id="sec-1",
        reference_date="2026-08-05",
        secondary_date="2026-08-17",
        temporal_baseline_days=12,
        processing_mode="hyp3",
        processing_status="PROCESSED",
    )
    db.add_insar_pair(
        pair_id="pending",
        reference_acq_id="ref-2",
        secondary_acq_id="sec-2",
        reference_date="2026-08-17",
        secondary_date="2026-08-29",
        temporal_baseline_days=12,
        processing_mode="hyp3",
        processing_status="SUBMITTED",
    )

    assert db.get_latest_processed_insar_date() == "2026-08-17"
    db.close()


def test_saving_same_assessment_twice_updates_snapshots_and_history(tmp_path):
    db = DatabaseManager(tmp_path / "risk.db")
    db.populate_spatial_grid([{
        "cell_id": "R0_C0",
        "row_idx": 0,
        "col_idx": 0,
        "utm_easting": 0,
        "utm_northing": 0,
        "latitude": 13.6,
        "longitude": 79.3,
        "elevation_m": 100,
        "slope_deg": 20,
    }])
    result = run_risk_assessment(
        pd.DataFrame({
            "cell_id": ["R0_C0"],
            "slope_deg": [20],
            "terrain_high_evidence": [0],
        }),
        "2026-08-29",
    )

    save_risk_to_database(result, db)
    save_risk_to_database(result, db)

    with db.cursor() as cursor:
        snapshot_count = cursor.execute(
            "SELECT COUNT(*) FROM observation_snapshots "
            "WHERE cell_id = 'R0_C0' AND observation_date = '2026-08-29'"
        ).fetchone()[0]
        history_count = cursor.execute(
            "SELECT COUNT(*) FROM risk_history WHERE observation_date = '2026-08-29'"
        ).fetchone()[0]

    assert snapshot_count == 1
    assert history_count == 1
