"""
Database Population and Synchronization Script

Loads existing project CSV data into the SQLite database:
  - data/features/tirumala_final_agent_evidence.csv -> spatial_evidence_grid & observation_snapshots
  - data/features/tirumala_temporal_insar_features.csv -> temporal_insar_history / insar_pairs
  - data/processed/rainfall/tirumala/*.csv -> rainfall_records
  - registers historical GSI inventory points and InSAR acquisitions
  - generates initial risk_history aggregated records
  - exports spatial_grid_lookup.json and temporal_registry.json for the 3D viewer
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.transform import xy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS, setup_logging
from src.data.db import get_db

logger = setup_logging("update_database")


def grid_cell_center_wgs84(transform, transformer, row: int, col: int):
    """Return a raster cell center as (easting, northing, latitude, longitude)."""
    x, y = xy(transform, row, col, offset="center")
    longitude, latitude = transformer.transform(x, y)
    return float(x), float(y), float(latitude), float(longitude)


def read_quality_masked_los_pair(los_path: Path, coherence_path: Path, reference_path: Path):
    """Read an aligned LOS/coherence pair and mask nodata and coherence below 0.5."""
    for path in (los_path, coherence_path, reference_path):
        if not path.exists():
            raise FileNotFoundError(f"Required temporal raster not found: {path}")

    with (
        rasterio.open(reference_path) as reference,
        rasterio.open(los_path) as los_source,
        rasterio.open(coherence_path) as coherence_source,
    ):
        for source in (los_source, coherence_source):
            if (
                source.shape != reference.shape
                or source.crs != reference.crs
                or source.transform != reference.transform
            ):
                raise ValueError(
                    f"{source.name} is not aligned with the reference DEM {reference.name}."
                )

        los = los_source.read(1).astype(np.float32)
        coherence = coherence_source.read(1).astype(np.float32)
        valid = (
            (los_source.read_masks(1) > 0)
            & (coherence_source.read_masks(1) > 0)
            & np.isfinite(los)
            & np.isfinite(coherence)
            & (coherence >= 0.5)
        )
    return los, coherence, valid


def populate_spatial_grid_and_snapshots(db, evidence_csv: Path):
    if not evidence_csv.exists():
        logger.warning("Evidence file not found: %s", evidence_csv)
        return 0, 0

    df = pd.read_csv(evidence_csv)
    logger.info("Reading %d rows from %s", len(df), evidence_csv.name)

    grid_records = []
    snapshot_records = []
    obs_date = "2026-08-29"  # End of Pair 2 (Aug 17 - Aug 29)

    if not PATHS.dem_tif.exists():
        raise FileNotFoundError(f"Reference DEM not found: {PATHS.dem_tif}")
    with rasterio.open(PATHS.dem_tif) as dem:
        transformer = Transformer.from_crs(dem.crs, "EPSG:4326", always_xy=True)
        for _, row in df.iterrows():
            r = int(row["row"])
            c = int(row["col"])
            if not (0 <= r < dem.height and 0 <= c < dem.width):
                raise ValueError(f"Evidence grid cell ({r}, {c}) is outside the reference DEM.")
            easting, northing, latitude, longitude = grid_cell_center_wgs84(
                dem.transform, transformer, r, c
            )
            cell_id = f"R{r}_C{c}"

            elev = float(row.get("elevation_m", 0.0))
            slope = float(row.get("slope_deg", 0.0))
            aspect = float(row.get("aspect_deg", np.nan)) if "aspect_deg" in row else None
            if aspect is not None and np.isnan(aspect):
                aspect = None

            dist_gsi = float(row.get("dist_to_gsi_km", 999.0))
            terrain_flag = int(row.get("terrain_high_evidence", 0))

            grid_records.append({
                "cell_id": cell_id,
                "row_idx": r,
                "col_idx": c,
                "utm_easting": easting,
                "utm_northing": northing,
                "latitude": latitude,
                "longitude": longitude,
                "elevation_m": round(elev, 2),
                "slope_deg": round(slope, 2),
                "aspect_deg": round(aspect, 1) if aspect is not None else None,
                "dist_to_gsi_km": round(dist_gsi, 3),
                "terrain_high_evidence": terrain_flag,
            })

            los = float(row.get("los_disp_m", np.nan))
            corr = float(row.get("correlation", np.nan))
            score = float(row.get("agent_evidence_score", row.get("risk_score", 0.0)))
            cat = str(row.get("agent_evidence_category", row.get("risk_category", "Low")))
            insar_flag = int(row.get("insar_high_evidence", 0))

            snapshot_records.append({
                "cell_id": cell_id,
                "observation_date": obs_date,
                "pair_id": "PAIR_20260817_20260829",
                "los_disp_m": None if np.isnan(los) else round(los, 6),
                "coherence": None if np.isnan(corr) else round(corr, 4),
                "los_change_m": None,
                "rainfall_1day_mm": None,
                "rainfall_3day_mm": None,
                "rainfall_7day_mm": None,
                "rainfall_14day_mm": None,
                "ndvi": None,
                "ndvi_change": None,
                "unet_confidence": None,
                "unet_positive": 0,
                "risk_score": round(score, 2),
                "risk_category": cat,
                "insar_high_evidence": insar_flag,
                "temporal_evidence_flag": 0,
                "data_quality": "GOOD",
            })

    db.populate_spatial_grid(grid_records)
    db.bulk_add_observation_snapshots(snapshot_records)
    logger.info("Inserted %d grid cells and %d initial observation snapshots", len(grid_records), len(snapshot_records))
    return len(grid_records), len(snapshot_records)


def populate_rainfall(db, rain_csv: Path):
    if not rain_csv.exists():
        logger.warning("Rainfall CSV not found: %s", rain_csv)
        return 0

    df = pd.read_csv(rain_csv)
    date_col = [c for c in df.columns if "date" in c.lower()][0]
    mean_col = [c for c in df.columns if "mean" in c.lower() or "precip" in c.lower() or "daily" in c.lower()][0]

    count = 0
    for _, row in df.iterrows():
        date_str = str(row[date_col])[:10]
        daily_val = float(row[mean_col]) if pd.notna(row[mean_col]) else 0.0
        r1 = float(row.get("rolling_1day_mm", row.get("precip_1d", daily_val)))
        r3 = float(row.get("rolling_3day_mm", row.get("precip_3d", daily_val * 3)))
        r7 = float(row.get("rolling_7day_mm", row.get("precip_7d", daily_val * 7)))
        r14 = float(row.get("rolling_14day_mm", row.get("precip_14d", daily_val * 14)))

        db.add_rainfall_record(
            record_date=date_str,
            daily_mean_mm=round(daily_val, 2),
            daily_max_mm=round(daily_val, 2),
            daily_min_mm=0.0,
            rolling_1day_mm=round(r1, 2),
            rolling_3day_mm=round(r3, 2),
            rolling_7day_mm=round(r7, 2),
            rolling_14day_mm=round(r14, 2),
            source_product="NASA GPM IMERG V07C",
        )
        count += 1
    logger.info("Imported %d rainfall records into SQLite", count)
    return count


def register_known_insar_pairs(db):
    # Pair 1: 05 Aug 2026 - 17 Aug 2026
    # Pair 2: 17 Aug 2026 - 29 Aug 2026
    pair1 = {
        "pair_id": "PAIR_20260805_20260817",
        "reference_acq_id": "S1D_IW_SLC__1SDV_20260805",
        "secondary_acq_id": "S1D_IW_SLC__1SDV_20260817",
        "reference_date": "2026-08-05",
        "secondary_date": "2026-08-17",
        "temporal_baseline_days": 12,
        "perpendicular_baseline_m": -14.39,
        "processing_mode": "hyp3",
        "processing_status": "PROCESSED",
        "valid_pixels": 3085,
        "mean_coherence": 0.62,
        "quality_notes": "ASF HyP3 GLO-30 DEM, adf 0.6, MCF unwrapped",
    }
    pair2 = {
        "pair_id": "PAIR_20260817_20260829",
        "reference_acq_id": "S1D_IW_SLC__1SDV_20260817",
        "secondary_acq_id": "S1D_IW_SLC__1SDV_20260829",
        "reference_date": "2026-08-17",
        "secondary_date": "2026-08-29",
        "temporal_baseline_days": 12,
        "perpendicular_baseline_m": 66.97,
        "processing_mode": "hyp3",
        "processing_status": "PROCESSED",
        "valid_pixels": 2957,
        "mean_coherence": 0.68,
        "quality_notes": "ASF HyP3 GLO-30 DEM, adf 0.6, MCF unwrapped",
    }

    db.add_acquisition(
        acquisition_id="S1D_IW_SLC__1SDV_20260805",
        satellite="Sentinel-1",
        product_type="SLC",
        sensor_mode="IW",
        orbit_direction="DESCENDING",
        acquisition_date="2026-08-05",
        polarisation="VV+VH",
        download_status="DOWNLOADED",
        processing_status="PROCESSED",
    )
    db.add_acquisition(
        acquisition_id="S1D_IW_SLC__1SDV_20260817",
        satellite="Sentinel-1",
        product_type="SLC",
        sensor_mode="IW",
        orbit_direction="DESCENDING",
        acquisition_date="2026-08-17",
        polarisation="VV+VH",
        download_status="DOWNLOADED",
        processing_status="PROCESSED",
    )
    db.add_acquisition(
        acquisition_id="S1D_IW_SLC__1SDV_20260829",
        satellite="Sentinel-1",
        product_type="SLC",
        sensor_mode="IW",
        orbit_direction="DESCENDING",
        acquisition_date="2026-08-29",
        polarisation="VV+VH",
        download_status="DOWNLOADED",
        processing_status="PROCESSED",
    )

    db.add_insar_pair(**pair1)
    db.add_insar_pair(**pair2)
    logger.info("Registered Sentinel-1 acquisitions and Pair 1 / Pair 2 in database")


def export_cesium_lookups(db):
    """Exports spatial_grid_lookup.json, temporal_registry.json, and sync_status.json for CesiumJS HUD."""
    from src.features.temporal_registry import TemporalRegistry
    reg = TemporalRegistry()
    reg.export_for_cesium()

    cells = db.get_all_grid_cells()
    if not cells:
        logger.warning("No grid cells to export for Cesium")
        return {"status": "NO_GRID", "total_cells": 0}

    latest_obs_date = db.get_latest_processed_insar_date()
    obs_list = db.get_observations_for_date(latest_obs_date) if latest_obs_date else []
    obs_map = {o["cell_id"]: o for o in obs_list}

    pair1_dir = PATHS.processed_dinsar / "pair_05_17"
    pair_raster_paths = {
        "PAIR_20260805_20260817": (
            pair1_dir / "tirumala_los_disp_80m_gsi_aoi_pair_05_17.tif",
            pair1_dir / "tirumala_corr_80m_gsi_aoi_pair_05_17.tif",
        ),
        "PAIR_20260817_20260829": (PATHS.los_tif, PATHS.corr_tif),
        "PAIR_20261109_20261121": (
            PATHS.processed_dinsar / "PAIR_20261109_20261121" / "tirumala_live_los_disp_80m.tif",
            PATHS.processed_dinsar / "PAIR_20261109_20261121" / "tirumala_live_coherence_80m.tif",
        ),
    }
    temporal_pair_data = {}
    for pair_id, (los_path, coherence_path) in pair_raster_paths.items():
        if not los_path.exists() and not coherence_path.exists():
            continue
        temporal_pair_data[pair_id] = read_quality_masked_los_pair(
            los_path, coherence_path, PATHS.dem_tif
        )

    # Latest rainfall for context dynamically
    latest_rain_date = db.get_latest_rainfall_date()
    rain = db.get_rainfall_range(latest_rain_date, latest_rain_date) if latest_rain_date else []
    rain_3d = rain[0].get("rolling_3day_mm") if rain else None

    lookup_data = []
    if not PATHS.dem_tif.exists():
        raise FileNotFoundError(f"Reference DEM not found: {PATHS.dem_tif}")
    with rasterio.open(PATHS.dem_tif) as dem:
        transformer = Transformer.from_crs(dem.crs, "EPSG:4326", always_xy=True)
        for c in cells:
            row_idx = int(c["row_idx"])
            col_idx = int(c["col_idx"])
            if not (0 <= row_idx < dem.height and 0 <= col_idx < dem.width):
                raise ValueError(
                    f"Database grid cell ({row_idx}, {col_idx}) is outside the reference DEM."
                )
            _, _, latitude, longitude = grid_cell_center_wgs84(
                dem.transform, transformer, row_idx, col_idx
            )
            cid = c["cell_id"]
            obs = obs_map.get(cid, {})
            pair1_data = temporal_pair_data.get("PAIR_20260805_20260817")
            pair2_data = temporal_pair_data.get("PAIR_20260817_20260829")
            pair1_valid = pair1_data is not None and pair1_data[2][row_idx, col_idx]
            pair2_valid = pair2_data is not None and pair2_data[2][row_idx, col_idx]
            pair3_data = temporal_pair_data.get("PAIR_20261109_20261121")
            pair3_valid = pair3_data is not None and pair3_data[2][row_idx, col_idx]
            lookup_data.append({
                "id": cid,
                "row": row_idx,
                "col": col_idx,
                "lat": latitude,
                "lon": longitude,
                "elev": c["elevation_m"],
                "slope": c["slope_deg"],
                "los": obs.get("los_disp_m", None),
                "corr": obs.get("coherence", None),
                "los_pair_05_17_m": float(pair1_data[0][row_idx, col_idx]) if pair1_valid else None,
                "los_pair_17_29_m": float(pair2_data[0][row_idx, col_idx]) if pair2_valid else None,
                "corr_pair_05_17": float(pair1_data[1][row_idx, col_idx]) if pair1_valid else None,
                "corr_pair_17_29": float(pair2_data[1][row_idx, col_idx]) if pair2_valid else None,
                "los_pair_20261109_20261121_m": float(pair3_data[0][row_idx, col_idx]) if pair3_valid else None,
                "corr_pair_20261109_20261121": float(pair3_data[1][row_idx, col_idx]) if pair3_valid else None,
                "rain_3d": rain_3d,
                "score": obs.get("risk_score"),
                "category": obs.get("risk_category"),
            })

    out_file = PATHS.viewer_data / "spatial_grid_lookup.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = out_file.with_suffix(out_file.suffix + ".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(lookup_data, f)
    os.replace(temp_file, out_file)
    logger.info("Exported Cesium raycast lookup with %d cells to %s", len(lookup_data), out_file)

    # Export dynamic sync status for CesiumJS live auto-refresh
    active_alerts = db.get_active_alerts() if hasattr(db, "get_active_alerts") else []
    sync_status = {
        "last_sync_utc": datetime.now(timezone.utc).isoformat(),
        "latest_observation_date": latest_obs_date,
        "latest_rainfall_date": latest_rain_date,
        "total_cells": len(lookup_data),
        "observed_cells": len(obs_map),
        "active_alerts_count": len(active_alerts),
        "status": "SYNCHRONIZED" if latest_obs_date and obs_map else "NO_VALID_OBSERVATION",
    }
    sync_file = PATHS.viewer_data / "sync_status.json"
    temp_file = sync_file.with_suffix(sync_file.suffix + ".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(sync_status, f, indent=2)
    os.replace(temp_file, sync_file)
    logger.info("Exported Cesium sync status: %s", sync_status)
    return sync_status


def initialize_all():
    db = get_db()
    logger.info("Starting comprehensive database population...")
    register_known_insar_pairs(db)
    populate_spatial_grid_and_snapshots(db, PATHS.spatial_evidence_csv)
    populate_rainfall(db, PATHS.rainfall_features_csv)

    # Risk history entry
    from src.features.risk_engine import run_risk_assessment, save_risk_to_database
    if PATHS.spatial_evidence_csv.exists():
        df = pd.read_csv(PATHS.spatial_evidence_csv)
        res = run_risk_assessment(df, "2026-08-29")
        save_risk_to_database(res)

    export_cesium_lookups(db)
    counts = db.get_table_counts()
    logger.info("Current DB Table Counts: %s", counts)
    return counts


def main():
    parser = argparse.ArgumentParser(description="Populate and synchronize SQLite monitoring database.")
    parser.add_argument("--init", action="store_true", help="Initialize database with all existing project data.")
    parser.add_argument("--export-cesium", action="store_true", help="Export CesiumJS JSON lookups.")
    args = parser.parse_args()

    if args.export_cesium:
        db = get_db()
        export_cesium_lookups(db)
    else:
        counts = initialize_all()
        print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
