"""Checkpoint 3: integrate existing audited environmental datasets."""

import argparse
import json
import sys
from pathlib import Path

import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS
from src.data.db import get_db
from src.environmental.spatial_integration import (
    validate_common_rasters,
    recalculate_rainfall_rollups,
    map_gsi_locations,
    register_environmental_datasets,
)


def run_integration(db=None) -> dict:
    db = db or get_db()
    raster_paths = {
        "dem": PATHS.dem_tif,
        "slope": PATHS.slope_tif,
        "aspect": PATHS.aspect_tif,
        "insar_los": (
            PATHS.processed_dinsar
            / "PAIR_20261109_20261121"
            / "tirumala_live_los_disp_80m.tif"
        ),
        "insar_coherence": (
            PATHS.processed_dinsar
            / "PAIR_20261109_20261121"
            / "tirumala_live_coherence_80m.tif"
        ),
    }
    raster_paths = {
        name: path for name, path in raster_paths.items()
        if Path(path).exists()
    }
    alignment = validate_common_rasters(raster_paths)

    rainfall_csv = (
        PATHS.processed_rainfall
        / "tirumala_daily_rainfall_20260801_20260829.csv"
    )
    if not rainfall_csv.exists():
        rainfall_csv = (
            PATHS.processed_rainfall
            / "tirumala_rainfall_features_20260801_20260829.csv"
        )
    rainfall = recalculate_rainfall_rollups(rainfall_csv, db)

    gsi_csv = (
        PATHS.root
        / "data/features/tirumala_gsi_validation_table.csv"
    )
    gsi = map_gsi_locations(db, gsi_csv)

    registry = register_environmental_datasets(db)

    dem_available = Path(PATHS.dem_tif).exists()
    slope_available = Path(PATHS.slope_tif).exists()
    aspect_available = Path(PATHS.aspect_tif).exists()
    los_available = (
        PATHS.processed_dinsar
        / "PAIR_20261109_20261121"
        / "tirumala_live_los_disp_80m.tif"
    ).exists()
    coherence_available = (
        PATHS.processed_dinsar
        / "PAIR_20261109_20261121"
        / "tirumala_live_coherence_80m.tif"
    ).exists()

    cells = db.get_all_grid_cells()
    for cell in cells:
        db.upsert_spatial_factor_availability(
            cell_id=cell["cell_id"],
            observation_date="2026-11-21",
            dem_available=int(dem_available),
            slope_available=int(slope_available),
            aspect_available=int(aspect_available),
            rainfall_available=1 if rainfall["record_count"] > 0 else 0,
            gsi_available=int(
                any(
                    record["cell_id"] == cell["cell_id"]
                    for record in gsi["records"]
                )
            ),
            insar_los_available=int(los_available),
            insar_coherence_available=int(coherence_available),
            unet_available=0,
            quality_status=(
                "PARTIAL"
                if alignment["valid"]
                else "ALIGNMENT_ERROR"
            ),
            notes=(
                "U-Net unavailable for georeferenced Tirumala cells; "
                "rainfall remains study-area aggregate."
            ),
        )

    return {
        "alignment": alignment,
        "rainfall": {
            "status": rainfall["status"],
            "record_count": rainfall["record_count"],
            "discrepancy_count": rainfall["discrepancy_count"],
        },
        "gsi": {
            "status": gsi["status"],
            "record_count": gsi["record_count"],
            "mapped_count": gsi["mapped_count"],
        },
        "registry": registry,
        "factor_availability_cells": len(cells),
    }


def main():
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Run Stage 6 Checkpoint 3 existing-data integration."
    )
    args = parser.parse_args()
    print(json.dumps(run_integration(), indent=2))


if __name__ == "__main__":
    main()
