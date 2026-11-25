from pathlib import Path

import pandas as pd
import h5py
import glob
from pathlib import Path

from config.settings import PATHS
from src.data.db import DatabaseManager
from src.environmental.spatial_integration import (
    validate_common_rasters,
    recalculate_rainfall_rollups,
)
from src.risk_assessment import WEIGHTS


def test_real_aligned_environmental_rasters():
    result = validate_common_rasters({
        "dem": PATHS.dem_tif,
        "slope": PATHS.slope_tif,
        "aspect": PATHS.aspect_tif,
    })
    assert result["valid"] is True
    assert result["errors"] == []
    for profile in result["datasets"].values():
        assert profile["crs"] == "EPSG:32644"
        assert profile["shape"] == [69, 110]
        assert profile["resolution"] == [80.0, 80.0]


def test_rainfall_rollups_are_recalculated_and_discrepancies_are_flagged(tmp_path):
    csv_path = tmp_path / "rainfall.csv"
    pd.DataFrame({
        "date": ["2026-08-01", "2026-08-02", "2026-08-03"],
        "rainfall_mean_mm": [5.5, 6.1, 3.2],
    }).to_csv(csv_path, index=False)

    db = DatabaseManager(tmp_path / "rainfall.db")
    db.add_rainfall_record(
        record_date="2026-08-03",
        daily_mean_mm=3.2,
        rolling_3day_mm=9.6,
        rolling_7day_mm=None,
        rolling_14day_mm=None,
    )
    result = recalculate_rainfall_rollups(csv_path, db)
    assert result["record_count"] == 3
    assert result["status"] == "REQUIRES_RECONCILIATION"
    validations = db.get_rainfall_rollup_validation()
    reconciled = [row for row in validations if row["record_date"] == "2026-08-03"][0]
    assert reconciled["recalculated_3day_mm"] == 14.8
    assert reconciled["stored_database_3day_mm"] == 9.6
    assert reconciled["status"] == "REQUIRES_RECONCILIATION"
    db.close()


def test_stage6_database_migration_preserves_existing_tables(tmp_path):
    db = DatabaseManager(tmp_path / "stage6.db")
    db.add_acquisition(
        acquisition_id="existing-acquisition",
        satellite="Sentinel-1",
        product_type="SLC",
        acquisition_date="2026-11-21",
    )
    db.register_environmental_dataset(
        dataset_key="dem",
        dataset_name="DEM",
        source="Local",
        dataset_type="terrain",
        crs="EPSG:32644",
        resolution_m=80.0,
        quality_status="READY",
    )
    assert db.get_acquisition("existing-acquisition") is not None
    assert len(db.get_environmental_datasets()) == 1
    db.close()


def test_existing_risk_formula_weights_are_not_changed():
    assert WEIGHTS == {
        "slope_component": 0.40,
        "terrain_component": 0.25,
        "insar_component": 0.20,
        "temporal_component": 0.15,
    }


def test_gsi_inventory_keeps_approximate_coordinate_status():
    frame = pd.read_csv(PATHS.root / "data/features/tirumala_gsi_validation_table.csv")
    assert len(frame) == 15
    assert frame[["latitude", "longitude"]].isna().sum().sum() == 0
    assert frame["coordinate_quality"].eq("map-derived approximate").all()


def test_unet_h5_metadata_matches_existing_model_shape():
    image_files = glob.glob(
        str(PATHS.root / "data/raw/landslide4sense/TrainData/img/*.h5")
    )
    mask_files = glob.glob(
        str(PATHS.root / "data/raw/landslide4sense/TrainData/mask/*.h5")
    )
    assert len(image_files) == 3799
    assert len(mask_files) == 3799
    with h5py.File(image_files[0], "r") as image_file:
        assert image_file["img"].shape == (128, 128, 14)
    with h5py.File(mask_files[0], "r") as mask_file:
        assert mask_file["mask"].shape == (128, 128)
