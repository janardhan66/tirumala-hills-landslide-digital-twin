import shutil
import tempfile
from pathlib import Path

import pytest

from config.settings import STUDY_AREA
from scripts.migrate_multi_temporal import create_backup, migrate
from src.data.db import DatabaseManager
from src.data.multi_temporal import (
    PairManager,
    calculate_temporal_baseline,
    orbit_compatible,
)


def test_duplicate_acquisition_prevention(tmp_path):
    db = DatabaseManager(tmp_path / "acquisitions.db")
    acquisition = {
        "acquisition_id": "S1_TEST_1",
        "satellite": "Sentinel-1",
        "product_type": "SLC",
        "sensor_mode": "IW",
        "orbit_direction": "DESCENDING",
        "relative_orbit": 92,
        "acquisition_date": "2026-11-09",
        "footprint_wkt": STUDY_AREA.wkt_polygon,
    }

    db.add_acquisition(**acquisition)
    db.add_acquisition(**acquisition)

    assert db.get_acquisition("S1_TEST_1") is not None
    with db.cursor() as cursor:
        count = cursor.execute(
            "SELECT COUNT(*) FROM acquisitions WHERE acquisition_id = 'S1_TEST_1'"
        ).fetchone()[0]
    assert count == 1
    db.close()


def test_duplicate_pair_prevention(tmp_path):
    db = DatabaseManager(tmp_path / "pairs.db")
    for acq_id, date in [
        ("REF", "2026-11-09"),
        ("SEC", "2026-11-21"),
    ]:
        db.add_acquisition(
            acquisition_id=acq_id,
            satellite="Sentinel-1",
            product_type="SLC",
            sensor_mode="IW",
            orbit_direction="DESCENDING",
            relative_orbit=92,
            acquisition_date=date,
        )

    db.add_insar_pair(
        pair_id="PAIR_TEST",
        reference_acq_id="REF",
        secondary_acq_id="SEC",
        reference_date="2026-11-09",
        secondary_date="2026-11-21",
        temporal_baseline_days=12,
        processing_mode="hyp3",
        processing_status="CANDIDATE",
    )
    db.add_insar_pair(
        pair_id="PAIR_TEST",
        reference_acq_id="REF",
        secondary_acq_id="SEC",
        reference_date="2026-11-09",
        secondary_date="2026-11-21",
        temporal_baseline_days=12,
        processing_mode="hyp3",
        processing_status="CANDIDATE",
    )

    with db.cursor() as cursor:
        count = cursor.execute(
            "SELECT COUNT(*) FROM insar_pairs WHERE pair_id = 'PAIR_TEST'"
        ).fetchone()[0]
    assert count == 1
    db.close()


def test_orbit_and_temporal_compatibility():
    descending_92 = {
        "orbit_direction": "DESCENDING",
        "relative_orbit": 92,
        "sensor_mode": "IW",
    }
    assert orbit_compatible(
        descending_92,
        {
            "orbit_direction": "descending",
            "relative_orbit": 92,
            "sensor_mode": "IW",
        },
    )
    assert not orbit_compatible(
        descending_92,
        {
            "orbit_direction": "ASCENDING",
            "relative_orbit": 92,
            "sensor_mode": "IW",
        },
    )
    assert not orbit_compatible(
        descending_92,
        {
            "orbit_direction": "DESCENDING",
            "relative_orbit": 12,
            "sensor_mode": "IW",
        },
    )
    assert calculate_temporal_baseline("2026-11-09", "2026-11-21") == 12
    with pytest.raises(ValueError, match="follow"):
        calculate_temporal_baseline("2026-11-21", "2026-11-09")


def test_pair_selection_rejects_duplicate_and_out_of_baseline_pairs(tmp_path):
    db = DatabaseManager(tmp_path / "selection.db")
    valid_archives = []
    for name in ("A.zip", "B.zip"):
        archive_path = tmp_path / name
        import zipfile
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("manifest.safe", "test")
        valid_archives.append(str(archive_path))
    acquisitions = [
        {
            "acquisition_id": "A",
            "satellite": "Sentinel-1",
            "product_type": "SLC",
            "sensor_mode": "IW",
            "orbit_direction": "DESCENDING",
            "relative_orbit": 92,
            "acquisition_date": "2026-11-09",
            "footprint_wkt": "POLYGON((79.337 13.639,79.423 13.639,79.423 13.693,79.337 13.693,79.337 13.639))",
            "download_status": "DOWNLOADED",
            "file_path": valid_archives[0],
        },
        {
            "acquisition_id": "B",
            "satellite": "Sentinel-1",
            "product_type": "SLC",
            "sensor_mode": "IW",
            "orbit_direction": "DESCENDING",
            "relative_orbit": 92,
            "acquisition_date": "2026-11-21",
            "footprint_wkt": "POLYGON((79.337 13.639,79.423 13.639,79.423 13.693,79.337 13.693,79.337 13.639))",
            "download_status": "DOWNLOADED",
            "file_path": valid_archives[1],
        },
    ]
    for acquisition in acquisitions:
        db.add_acquisition(**acquisition)
    manager = PairManager(
        db,
        minimum_baseline_days=6,
        maximum_baseline_days=36,
        minimum_overlap_percent=90.0,
    )
    candidates = manager.select_next_connected_pairs(
        acquisitions,
        STUDY_AREA.wkt_polygon,
        maximum_pairs=1,
    )
    assert len(candidates) == 1
    assert candidates[0].temporal_baseline_days == 12

    manager.register_selected_pair(candidates[0])
    assert manager.existing_pair_exists("A", "B")
    assert len(manager.select_next_connected_pairs(
        acquisitions,
        STUDY_AREA.wkt_polygon,
        maximum_pairs=1,
    )) == 0
    db.close()


def test_existing_live_pair_migration_preserves_core_fields(tmp_path):
    db_path = tmp_path / "monitoring.db"
    db = DatabaseManager(db_path)
    db.add_acquisition(
        acquisition_id="220f79ba-248d-4e02-81ad-1f9f10d202ed",
        satellite="Sentinel-1",
        product_type="SLC",
        acquisition_date="2026-11-09",
        sensor_mode="IW",
        orbit_direction="DESCENDING",
        relative_orbit=92,
    )
    db.add_acquisition(
        acquisition_id="b69aeace-3306-4e9b-94f3-a6d643296386",
        satellite="Sentinel-1",
        product_type="SLC",
        acquisition_date="2026-11-21",
        sensor_mode="IW",
        orbit_direction="DESCENDING",
        relative_orbit=92,
    )
    db.add_insar_pair(
        pair_id="PAIR_20261109_20261121",
        reference_acq_id="220f79ba-248d-4e02-81ad-1f9f10d202ed",
        secondary_acq_id="b69aeace-3306-4e9b-94f3-a6d643296386",
        reference_date="2026-11-09",
        secondary_date="2026-11-21",
        temporal_baseline_days=12,
        processing_mode="hyp3",
        processing_status="PROCESSED",
        hyp3_job_id="3889d809-88a3-4a93-89a5-258821932737",
    )
    db.close()

    backup = create_backup(db_path)
    assert backup.exists()
    result = migrate(db_path)
    assert result["pair_preserved"]
    assert result["pair_status"] == "PROCESSED"

    migrated = DatabaseManager(db_path)
    pair = [
        row for row in migrated.get_insar_pairs()
        if row["pair_id"] == "PAIR_20261109_20261121"
    ][0]
    assert pair["hyp3_job_id"] == "3889d809-88a3-4a93-89a5-258821932737"
    assert pair["processing_status"] == "PROCESSED"
    migrated.close()
