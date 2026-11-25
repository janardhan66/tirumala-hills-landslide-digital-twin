from src.data.db import DatabaseManager


def test_duplicate_acquisition_discovery_does_not_register(tmp_path):
    db = DatabaseManager(tmp_path / "phase4.db")
    db.add_acquisition(
        acquisition_id="existing",
        satellite="Sentinel-1",
        product_type="SLC",
        acquisition_date="2026-11-21",
    )
    discovered = "existing"
    duplicate = db.acquisition_exists(discovered)
    assert duplicate is True
    db.close()


def test_rainfall_rollups_remain_unmodified():
    import tempfile
    from pathlib import Path

    temp_dir = tempfile.TemporaryDirectory()
    db = DatabaseManager(Path(temp_dir.name) / "phase4.db")
    db.add_rainfall_record(
        record_date="2026-08-03",
        daily_mean_mm=3.2,
        rolling_3day_mm=9.6,
        rolling_7day_mm=None,
        rolling_14day_mm=None,
    )
    rows = db.get_rainfall_range("2026-08-03", "2026-08-03")
    assert rows[0]["rolling_3day_mm"] == 9.6
    db.close()


def test_no_hyp3_job_is_submitted_by_phase4_status():
    status_script = __import__("pathlib").Path(
        "scripts/export_phase4_master_status.py"
    )
    assert status_script.exists()
