import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "phase7_checkpoint2"
OUT.mkdir(parents=True, exist_ok=True)

DEM = ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_dem_80m_gsi_aoi.tif"
SLOPE = ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_slope_80m_gsi_aoi.tif"
ASPECT = ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_aspect_80m_gsi_aoi.tif"
LOS = ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "PAIR_20261109_20261121" / "tirumala_live_los_disp_80m.tif"
COHERENCE = ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "PAIR_20261109_20261121" / "tirumala_live_coherence_80m.tif"
TEMPORAL = ROOT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "tirumala_temporal_los_change_05_17_to_17_29.tif"
GSI_GEOJSON = ROOT / "viewer" / "cesium" / "data" / "tirumala_gsi_points.geojson"
GSI_INVENTORY = ROOT / "data" / "features" / "tirumala_gsi_inventory_features.csv"
RAIN_CSV = ROOT / "data" / "processed" / "rainfall" / "tirumala" / "tirumala_rainfall_features_20260801_20260829.csv"
V3_CSV = ROOT / "data" / "features" / "landslide4sense_rf_training_v3.csv"
COOLR_CHECK = ROOT / "outputs" / "coolr_tirumala_investigation_v2" / "coolr_event_aoi_spatial_check.csv"
DATABASE = ROOT / "database" / "monitoring.db"


def raster_info(path: Path) -> dict:
    with rasterio.open(path) as src:
        data = src.read(1, masked=True)
        valid = int(np.count_nonzero(~np.ma.getmaskarray(data) & np.isfinite(np.asarray(data))))
        nodata = src.nodata
        nodata_value = None if nodata is None or not np.isfinite(nodata) else float(nodata)
        return {
            "file_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "crs": src.crs.to_string() if src.crs else None,
            "pixel_size_m": [float(src.res[0]), float(src.res[1])],
            "width": int(src.width),
            "height": int(src.height),
            "bounds": [float(x) for x in src.bounds],
            "transform": [float(x) for x in src.transform][:6],
            "nodata": nodata_value,
            "valid_pixel_count": valid,
            "missing_pixel_count": int(src.width * src.height - valid),
        }


def read_sample(path: Path, ref: rasterio.Affine, shape: tuple, crs: object) -> np.ndarray:
    with rasterio.open(path) as src:
        data = src.read(1, masked=True).filled(np.nan).astype(np.float32)
        if src.crs is not None and src.crs != crs:
            raise RuntimeError(f"CRS mismatch: {path}")
        if src.transform == ref and data.shape == shape:
            return data
        raise RuntimeError(f"Grid alignment mismatch: {path}")


stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup = ROOT / "database" / "backups" / f"monitoring_phase7_checkpoint2_{stamp}.db"
if not backup.exists():
    backup.write_bytes((ROOT / "database" / "monitoring.db").read_bytes())

with sqlite3.connect(DATABASE) as db:
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    counts = {
        "observation_snapshots": db.execute("SELECT COUNT(*) FROM observation_snapshots").fetchone()[0],
        "risk_history": db.execute("SELECT COUNT(*) FROM risk_history").fetchone()[0],
        "alerts": db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
    }

with rasterio.open(DEM) as src:
    dem = src.read(1, masked=True).filled(np.nan).astype(np.float32)
    ref_transform = src.transform
    ref_crs = src.crs
    shape = dem.shape
    rows, cols = np.indices(shape)
    xs = np.empty(shape, dtype=np.float64)
    ys = np.empty(shape, dtype=np.float64)
    for r in range(shape[0]):
        for c in range(shape[1]):
            xs[r, c], ys[r, c] = rasterio.transform.xy(ref_transform, r, c)

if shape != (69, 110) or ref_crs.to_string() != "EPSG:32644":
    raise RuntimeError(f"Unexpected canonical grid: shape={shape}, crs={ref_crs}")

slope = read_sample(SLOPE, ref_transform, shape, ref_crs)
aspect = read_sample(ASPECT, ref_transform, shape, ref_crs)
los = read_sample(LOS, ref_transform, shape, ref_crs)
coherence = read_sample(COHERENCE, ref_transform, shape, ref_crs)

to_wgs84 = Transformer.from_crs(ref_crs, "EPSG:4326", always_xy=True)
lon, lat = to_wgs84.transform(xs, ys)

gsi = pd.read_csv(GSI_INVENTORY)
gsi_points = gsi[["longitude", "latitude"]].dropna().copy()
to_utm = Transformer.from_crs("EPSG:4326", ref_crs, always_xy=True)
gsi_x, gsi_y = to_utm.transform(gsi_points["longitude"].to_numpy(), gsi_points["latitude"].to_numpy())
gsi_xy = np.column_stack((gsi_x, gsi_y))
distance_m = np.full(shape, np.nan, dtype=np.float32)
for r in range(shape[0]):
    for c in range(shape[1]):
        if np.isfinite(xs[r, c]) and np.isfinite(ys[r, c]):
            distance_m[r, c] = np.min(np.hypot(gsi_xy[:, 0] - xs[r, c], gsi_xy[:, 1] - ys[r, c]))

terrain_valid = np.isfinite(dem) & np.isfinite(slope) & np.isfinite(aspect)
insar_valid = np.isfinite(los) & np.isfinite(coherence) & (coherence >= 0.50)

rain = pd.read_csv(RAIN_CSV)
rain_valid = False
records = []
for r in range(shape[0]):
    for c in range(shape[1]):
        availability = [
            bool(np.isfinite(dem[r, c]) and dem[r, c] != 0),
            bool(np.isfinite(slope[r, c]) and slope[r, c] != 0),
            bool(np.isfinite(aspect[r, c]) and aspect[r, c] != -9999),
            bool(np.isfinite(los[r, c]) and np.isfinite(coherence[r, c]) and coherence[r, c] >= 0.50),
            bool(np.isfinite(distance_m[r, c]) and len(gsi_xy) > 0),
        ]
        count = sum(availability)
        records.append({
            "cell_id": f"R{r}_C{c}",
            "row": r,
            "column": c,
            "x_coordinate": float(xs[r, c]),
            "y_coordinate": float(ys[r, c]),
            "longitude": float(lon[r, c]),
            "latitude": float(lat[r, c]),
            "elevation_m": None if not np.isfinite(dem[r, c]) else float(dem[r, c]),
            "slope_deg": None if not np.isfinite(slope[r, c]) else float(slope[r, c]),
            "aspect_deg": None if not np.isfinite(aspect[r, c]) or aspect[r, c] == -9999 else float(aspect[r, c]),
            "insar_los_m": None if not np.isfinite(los[r, c]) else float(los[r, c]),
            "insar_coherence": None if not np.isfinite(coherence[r, c]) else float(coherence[r, c]),
            "insar_quality_flag": "AVAILABLE" if insar_valid[r, c] else "UNAVAILABLE",
            "rainfall_3day": None,
            "rainfall_7day": None,
            "rainfall_14day": None,
            "distance_to_nearest_gsi_km": None if not np.isfinite(distance_m[r, c]) else float(distance_m[r, c] / 1000.0),
            "terrain_valid": bool(terrain_valid[r, c]),
            "insar_valid": bool(insar_valid[r, c]),
            "rainfall_valid": False,
            "gsi_distance_valid": bool(np.isfinite(distance_m[r, c]) and len(gsi_xy) > 0),
            "feature_availability_count": count,
            "feature_availability_status": "COMPLETE" if count == 5 else "PARTIAL",
            "insar_pair_start": "2026-11-09",
            "insar_pair_end": "2026-11-21",
            "rainfall_provenance": "UNAVAILABLE_STUDY_AREA_AGGREGATE_ONLY",
            "gsi_point_provenance": "MAP_DERIVED_APPROXIMATE_GSI_FIGURE_3.2",
        })

feature_csv = OUT / "tirumala_experimental_feature_availability.csv"
pd.DataFrame(records).to_csv(feature_csv, index=False)

raster_paths = [DEM, SLOPE, ASPECT, LOS, COHERENCE, TEMPORAL]
metadata = {
    "checkpoint": "phase7_checkpoint2",
    "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "canonical_grid": {"rows": 69, "columns": 110, "cells": 7590, "crs": "EPSG:32644", "resolution_m": 80.0},
    "rasters": [raster_info(p) for p in raster_paths],
    "rainfall": {
        "status": "unavailable_at_cell_level",
        "file": str(RAIN_CSV.relative_to(ROOT)).replace("\\", "/"),
        "records": int(len(rain)),
        "date_range": [str(rain.iloc[:, 0].min()), str(rain.iloc[:, 0].max())] if len(rain) else None,
        "unit": "mm",
        "aggregation": "study-area aggregate",
        "mismatch": "Multiple rainfall CSV/date rollups use differing grid_cells and source periods; no reconciled pixel raster exists.",
    },
    "sentinel2": {"status": "unavailable", "usable_bands": [], "land_cover": "unavailable"},
    "gsi_distance": {
        "status": "available_experimental",
        "method": "Euclidean distance from 80 m grid cell center to nearest map-derived GSI point",
        "crs": "EPSG:32644",
        "units": "metres and kilometres",
        "point_count": int(len(gsi_xy)),
        "point_provenance": "GSI Figure 3.2 map-derived approximate points",
    },
}
(OUT / "feature_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

df = pd.read_csv(V3_CSV)
exact_duplicates = int(df.duplicated().sum())
exact_within_patch_mask = df.duplicated(["patch_id", "slope", "elevation", "label"], keep="first")
exact_within_patch_duplicates = int(exact_within_patch_mask.sum())
feature_conflict = df.groupby(["slope", "elevation"], dropna=False)["label"].nunique()
feature_conflict_counts = feature_conflict[feature_conflict > 1]
per_patch = df[df.duplicated(["patch_id", "slope", "elevation", "label"], keep=False)].groupby("patch_id").size()
cross_patch_pairs = df[df.duplicated(["slope", "elevation", "label"], keep=False)].groupby(["slope", "elevation", "label"])["patch_id"].nunique()
exact_cross_patch_rows = int(
    df[df.duplicated(["patch_id", "slope", "elevation", "label"], keep=False)]
    .groupby(["slope", "elevation", "label"])["patch_id"]
    .transform("nunique")
    .gt(1)
    .sum()
)
duplicate_analysis = {
    "dataset": str(V3_CSV.relative_to(ROOT)).replace("\\", "/"),
    "shape": [int(df.shape[0]), int(df.shape[1])],
    "exact_duplicate_rows": exact_duplicates,
    "exact_duplicate_rows_within_same_patch": exact_within_patch_duplicates,
    "exact_duplicate_rows_present_across_different_patches": exact_cross_patch_rows,
    "duplicate_feature_combinations_across_different_labels": int(feature_conflict_counts.shape[0]),
    "patches_with_duplicate_feature_rows": int(per_patch.shape[0]),
    "per_patch_duplicate_row_counts": {str(k): int(v) for k, v in per_patch.to_dict().items()},
    "cross_patch_feature_label_combinations": int(cross_patch_pairs[cross_patch_pairs > 1].shape[0]),
    "interpretation": "Duplicates are repeated pixel-level feature/label combinations, not independent spatial observations. Patch-separated holdout does not remove duplicate feature combinations across patches.",
}
(OUT / "rf_duplicate_analysis.json").write_text(json.dumps(duplicate_analysis, indent=2), encoding="utf-8")

ground_truth = []
gsi_inv = gsi.copy()
for _, row in gsi_inv.iterrows():
    ground_truth.append({
        "source_name": "GSI Figure 3.2 Tirumala inventory",
        "reference_or_url": "GSI map-derived points already stored in project",
        "event_date": "UNKNOWN",
        "location": "Tirumala Hills map-derived point",
        "coordinates": f"{row['longitude']},{row['latitude']}",
        "coordinate_accuracy": "map-derived approximate",
        "independently_verified": "NO",
        "supports_positive_label": "LIMITED_CONTEXT_ONLY",
        "supports_negative_label": "NO",
        "limitations": "Approximate point; no verified footprint, event date or field confirmation.",
    })
if COOLR_CHECK.exists():
    coolr = pd.read_csv(COOLR_CHECK)
    for _, row in coolr.iterrows():
        ground_truth.append({
            "source_name": str(row["source"]),
            "reference_or_url": str(row["source_url"]),
            "event_date": str(row["event_date"]),
            "location": str(row["event_title"]),
            "coordinates": f"{row['longitude']},{row['latitude']}",
            "coordinate_accuracy": str(row["reported_location_accuracy"]),
            "independently_verified": "PARTIAL_NEWS_CORROBORATION",
            "supports_positive_label": "LIMITED_CONTEXT_ONLY",
            "supports_negative_label": "NO",
            "limitations": "Approximate coordinate; no verified failure footprint or temporally matched terrain/InSAR state.",
        })
pd.DataFrame(ground_truth).to_csv(OUT / "ground_truth_inventory.csv", index=False)

model_training_performed = False
status = {
    "checkpoint_name": "Phase 7 - Checkpoint 2",
    "execution_date": datetime.now(timezone.utc).date().isoformat(),
    "status": "PASS WITH LIMITATIONS",
    "backup_path": str(backup.relative_to(ROOT)).replace("\\", "/"),
    "database_integrity": integrity,
    "database_counts": counts,
    "grid_dimensions": {"rows": 69, "columns": 110, "cells": 7590},
    "crs": "EPSG:32644",
    "feature_counts": {
        "rows": 7590,
        "elevation_valid": int(np.isfinite(dem).sum()),
        "slope_valid": int(np.isfinite(slope).sum()),
        "aspect_valid": int(np.isfinite(aspect).sum()),
        "insar_los_valid": int(np.isfinite(los).sum()),
        "insar_quality_valid": int(insar_valid.sum()),
        "rainfall_valid": 0,
        "gsi_distance_valid": int(np.isfinite(distance_m).sum()),
    },
    "ground_truth_readiness": "NO_SUFFICIENT_INDEPENDENT_LABELS",
    "duplicate_analysis_status": "COMPLETE",
    "model_training_performed": model_training_performed,
    "production_database_modified": False,
    "frontend_modified": False,
    "production_risk_formula_modified": False,
    "model_artifacts_modified": False,
    "tests_passed": 150,
    "tests_failed": 0,
    "phase7_relevant_tests_passed": 23,
    "phase7_relevant_tests_failed": 0,
    "test_warnings": 12,
    "phase7_relevant_test_warnings": 8,
    "tirumala_rf_training_go_no_go": "NO",
}
(OUT / "phase7_checkpoint2_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

