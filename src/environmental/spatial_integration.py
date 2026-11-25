"""Integrate audited environmental data into the common Tirumala grid."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from config.settings import PATHS


GRID_CRS = "EPSG:32644"
GRID_SHAPE = (69, 110)
GRID_RESOLUTION_M = 80.0


def validate_common_rasters(paths: Dict[str, Path]) -> Dict:
    opened = {}
    result = {"valid": True, "datasets": {}, "errors": []}
    reference = None

    for name, path in paths.items():
        try:
            source = rasterio.open(path)
            opened[name] = source
            profile = {
                "crs": str(source.crs),
                "shape": list(source.shape),
                "resolution": list(source.res),
                "bounds": list(source.bounds),
                "nodata": (
                    None
                    if source.nodata is None
                    or not np.isfinite(float(source.nodata))
                    else float(source.nodata)
                ),
            }
            data = source.read(1, masked=True)
            profile["valid_cells"] = int(np.count_nonzero(~data.mask))
            profile["missing_cells"] = int(np.count_nonzero(data.mask))
            profile["missing_percent"] = round(
                100.0 * profile["missing_cells"] / data.size,
                3,
            )
            result["datasets"][name] = profile

            if reference is None:
                reference = source
            elif (
                str(source.crs) != str(reference.crs)
                or source.shape != reference.shape
                or tuple(source.res) != tuple(reference.res)
                or tuple(source.bounds) != tuple(reference.bounds)
                or source.transform != reference.transform
            ):
                result["valid"] = False
                result["errors"].append(f"{name} is not aligned to the reference raster.")
        except Exception as exc:
            result["valid"] = False
            result["errors"].append(f"{name}: {exc}")

    for source in opened.values():
        source.close()
    return result


def recalculate_rainfall_rollups(
    daily_csv: Path,
    db=None,
) -> Dict:
    frame = pd.read_csv(daily_csv)
    date_column = "date"
    if date_column not in frame.columns:
        raise ValueError("Rainfall CSV has no date column.")
    values = {}
    records = []

    for _, row in frame.iterrows():
        date = str(row[date_column])[:10]
        daily = row.get("rainfall_mean_mm")
        daily_value = (
            float(daily)
            if pd.notna(daily) and np.isfinite(float(daily))
            else None
        )
        values[date] = daily_value

    for date_text, daily_value in values.items():
        current = datetime.strptime(date_text, "%Y-%m-%d").date()
        recalculated = {}
        for window in (3, 7, 14):
            window_dates = [
                (current - timedelta(days=offset)).isoformat()
                for offset in range(window - 1, -1, -1)
            ]
            window_values = [values.get(day) for day in window_dates]
            recalculated[window] = (
                round(sum(window_values), 2)
                if len(window_values) == window
                and all(value is not None for value in window_values)
                else None
            )

        stored = {}
        if db is not None:
            record = db.get_rainfall_range(date_text, date_text)
            if record:
                stored = record[0]

        discrepancies = []
        for window in (3, 7, 14):
            stored_value = (
                stored.get(f"rolling_{window}day_mm")
                if stored
                else None
            )
            recalculated_value = recalculated[window]
            if (
                recalculated_value is not None
                and stored_value is not None
                and not np.isclose(
                    float(recalculated_value),
                    float(stored_value),
                    rtol=0,
                    atol=0.01,
                )
            ):
                discrepancies.append(
                    f"{window}-day: recalculated={recalculated_value:.2f}, "
                    f"stored={float(stored_value):.2f}"
                )

        status = "REQUIRES_RECONCILIATION" if discrepancies else "MATCHED"
        max_discrepancy = None
        if discrepancies:
            numeric = []
            for window in (3, 7, 14):
                recalculated_value = recalculated[window]
                stored_value = (
                    stored.get(f"rolling_{window}day_mm")
                    if stored
                    else None
                )
                if recalculated_value is not None and stored_value is not None:
                    numeric.append(
                        abs(float(recalculated_value) - float(stored_value))
                    )
            max_discrepancy = max(numeric) if numeric else None

        records.append({
            "record_date": date_text,
            "daily_rainfall_mm": daily_value,
            "recalculated_3day_mm": recalculated[3],
            "stored_database_3day_mm": (
                stored.get("rolling_3day_mm") if stored else None
            ),
            "recalculated_7day_mm": recalculated[7],
            "stored_database_7day_mm": (
                stored.get("rolling_7day_mm") if stored else None
            ),
            "recalculated_14day_mm": recalculated[14],
            "stored_database_14day_mm": (
                stored.get("rolling_14day_mm") if stored else None
            ),
            "status": status,
            "discrepancy_mm": max_discrepancy,
            "source_json": json.dumps({
                "source": "NASA GPM IMERG V07C-derived CSV",
                "file": str(daily_csv),
                "discrepancies": discrepancies,
            }, sort_keys=True),
        })

    if db is not None:
        for record in records:
            db.upsert_rainfall_rollup_validation(**record)
    return {
        "status": (
            "REQUIRES_RECONCILIATION"
            if any(record["status"] == "REQUIRES_RECONCILIATION" for record in records)
            else "MATCHED"
        ),
        "record_count": len(records),
        "discrepancy_count": sum(
            record["status"] == "REQUIRES_RECONCILIATION"
            for record in records
        ),
        "records": records,
    }


def map_gsi_locations(db, inventory_csv: Path) -> Dict:
    frame = pd.read_csv(inventory_csv)
    required = {"inventory_id", "latitude", "longitude", "source", "coordinate_quality"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            "GSI inventory missing columns: " + ", ".join(sorted(missing))
        )

    dem_path = PATHS.dem_tif
    with rasterio.open(dem_path) as dem:
        transform = dem.transform
        transformer = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True)
        records = []
        for _, row in frame.iterrows():
            longitude = float(row["longitude"])
            latitude = float(row["latitude"])
            easting, northing = transformer.transform(longitude, latitude)
            col, row_index = ~transform * (easting, northing)
            col = int(np.floor(col))
            row_index = int(np.floor(row_index))
            cell_id = None
            proximity_km = None
            if 0 <= row_index < 69 and 0 <= col < 110:
                cell_id = f"R{row_index}_C{col}"
                cell_easting, cell_northing = (
                    transform * (col + 0.5, row_index + 0.5)
                )
                proximity_km = round(
                    float(
                        np.hypot(
                            easting - cell_easting,
                            northing - cell_northing,
                        )
                        / 1000.0
                    ),
                    3,
                )

            record = {
                "inventory_id": str(row["inventory_id"]),
                "latitude": latitude,
                "longitude": longitude,
                "cell_id": cell_id,
                "source": str(row["source"]),
                "coordinate_quality": str(row["coordinate_quality"]),
                "proximity_km": proximity_km,
                "quality_status": (
                    "MAPPED_APPROXIMATE"
                    if cell_id is not None
                    else "OUTSIDE_GRID"
                ),
            }
            db.upsert_gsi_spatial_mapping(**record)
            records.append(record)

    return {
        "status": "PASS",
        "record_count": len(records),
        "mapped_count": sum(record["cell_id"] is not None for record in records),
        "approximate_count": sum(
            record["coordinate_quality"] == "map-derived approximate"
            for record in records
        ),
        "records": records,
    }


def register_environmental_datasets(db) -> Dict:
    processing_date = datetime.now(timezone.utc).isoformat()
    datasets = [
        {
            "dataset_key": "dem",
            "dataset_name": "Tirumala DEM",
            "source": "Local Copernicus-derived raster",
            "dataset_type": "terrain",
            "observation_date": None,
            "processing_date": processing_date,
            "crs": GRID_CRS,
            "resolution_m": GRID_RESOLUTION_M,
            "coverage_type": "69x110 AOI grid",
            "file_path": str(PATHS.dem_tif),
            "quality_status": "READY",
            "metadata_json": json.dumps({"nodata": 0.0}, sort_keys=True),
        },
        {
            "dataset_key": "slope",
            "dataset_name": "Tirumala Slope",
            "source": "Local DEM-derived raster",
            "dataset_type": "terrain",
            "observation_date": None,
            "processing_date": processing_date,
            "crs": GRID_CRS,
            "resolution_m": GRID_RESOLUTION_M,
            "coverage_type": "69x110 AOI grid",
            "file_path": str(PATHS.slope_tif),
            "quality_status": "READY",
            "metadata_json": json.dumps({"nodata": 0.0}, sort_keys=True),
        },
        {
            "dataset_key": "aspect",
            "dataset_name": "Tirumala Aspect",
            "source": "Local DEM-derived raster",
            "dataset_type": "terrain",
            "observation_date": None,
            "processing_date": processing_date,
            "crs": GRID_CRS,
            "resolution_m": GRID_RESOLUTION_M,
            "coverage_type": "69x110 AOI grid",
            "file_path": str(PATHS.aspect_tif),
            "quality_status": "READY",
            "metadata_json": json.dumps({"nodata": -9999.0}, sort_keys=True),
        },
        {
            "dataset_key": "rainfall",
            "dataset_name": "Tirumala GPM rainfall",
            "source": "NASA GPM IMERG V07C-derived records",
            "dataset_type": "rainfall",
            "observation_date": "2026-08-01/2026-08-29",
            "processing_date": processing_date,
            "crs": "WGS84/study-area aggregate",
            "resolution_m": None,
            "coverage_type": "study-area aggregate",
            "file_path": str(PATHS.processed_rainfall / "tirumala_daily_rainfall_20260801_20260829.csv"),
            "quality_status": "REQUIRES_ROLLUP_RECONCILIATION",
            "metadata_json": json.dumps({
                "unit": "mm",
                "spatial_type": "aggregate",
                "record_count": 29,
            }, sort_keys=True),
        },
        {
            "dataset_key": "gsi_inventory",
            "dataset_name": "GSI Tirumala historical inventory",
            "source": "GSI Figure 3.2",
            "dataset_type": "historical_inventory",
            "observation_date": None,
            "processing_date": processing_date,
            "crs": "EPSG:4326",
            "resolution_m": None,
            "coverage_type": "15 map-derived points",
            "file_path": str(PATHS.root / "data/features/tirumala_gsi_validation_table.csv"),
            "quality_status": "READY_WITH_PROVENANCE_LIMITATION",
            "metadata_json": json.dumps({
                "coordinate_quality": "map-derived approximate",
                "record_count": 15,
            }, sort_keys=True),
        },
        {
            "dataset_key": "insar_los",
            "dataset_name": "Tirumala live LOS displacement",
            "source": "ASF HyP3 GAMMA",
            "dataset_type": "insar",
            "observation_date": "2026-11-21",
            "processing_date": "2026-11-22",
            "crs": GRID_CRS,
            "resolution_m": GRID_RESOLUTION_M,
            "coverage_type": "69x110 AOI grid",
            "file_path": str(PATHS.processed_dinsar / "PAIR_20261109_20261121/tirumala_live_los_disp_80m.tif"),
            "quality_status": "VALID_WITH_REFERENCE_LIMITATION",
            "missing_data_percent": 4.611,
            "metadata_json": json.dumps({
                "pair_id": "PAIR_20261109_20261121",
                "unit": "metres",
                "interpretation": "relative LOS",
            }, sort_keys=True),
        },
        {
            "dataset_key": "insar_coherence",
            "dataset_name": "Tirumala live InSAR coherence",
            "source": "ASF HyP3 GAMMA",
            "dataset_type": "insar_quality",
            "observation_date": "2026-11-21",
            "processing_date": "2026-11-22",
            "crs": GRID_CRS,
            "resolution_m": GRID_RESOLUTION_M,
            "coverage_type": "69x110 AOI grid",
            "file_path": str(PATHS.processed_dinsar / "PAIR_20261109_20261121/tirumala_live_coherence_80m.tif"),
            "quality_status": "VALID",
            "missing_data_percent": 4.545,
            "metadata_json": json.dumps({"range": "0-1"}, sort_keys=True),
        },
        {
            "dataset_key": "unet_benchmark",
            "dataset_name": "Landslide4Sense U-Net benchmark metadata",
            "source": "Landslide4Sense H5 benchmark",
            "dataset_type": "model_benchmark",
            "observation_date": None,
            "processing_date": processing_date,
            "crs": None,
            "resolution_m": None,
            "coverage_type": "3799 H5 image/mask patches",
            "file_path": str(PATHS.unet_checkpoint),
            "quality_status": "SOFTWARE_READY_LOCAL_VALIDATION_BLOCKED",
            "metadata_json": json.dumps({
                "image_shape": [128, 128, 14],
                "mask_shape": [128, 128],
                "channel_layout": "HWC source, CHW inference",
                "image_count": 3799,
                "mask_count": 3799,
                "prediction_not_georeferenced": True,
            }, sort_keys=True),
        },
    ]
    for dataset in datasets:
        db.register_environmental_dataset(**dataset)
    return {
        "status": "PASS",
        "registered_count": len(datasets),
        "datasets": [dataset["dataset_key"] for dataset in datasets],
    }
