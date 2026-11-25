"""Master Phase 6 InSAR audit and guarded temporal-network status."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import PATHS
from src.analysis.temporal_insar import build_interferogram_network
from src.data.db import get_db


def _tool_versions() -> Dict:
    tools = {}
    for name in ("hyp3", "snappy", "isce2", "isce3", "gdalinfo", "snap"):
        tools[name] = shutil.which(name)
    for module_name in ("rasterio", "numpy", "scipy", "pyproj", "pandas", "hyp3_sdk"):
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            tools[module_name] = None
            continue
        try:
            module = __import__(module_name)
            tools[module_name] = getattr(module, "__version__", "installed")
        except Exception:
            tools[module_name] = "installed"
    return tools


def _raster_summary(path: Path) -> Dict:
    if not path.is_file():
        return {
            "exists": False,
            "path": str(path),
            "status": "NOT_TESTED",
        }
    try:
        with rasterio.open(path) as source:
            values = source.read(1, masked=True)
            finite = np.asarray(values.compressed(), dtype=np.float64)
            finite = finite[np.isfinite(finite)]
            summary = {
                "exists": True,
                "path": str(path),
                "crs": str(source.crs),
                "shape": [source.height, source.width],
                "resolution_m": [float(source.res[0]), float(source.res[1])],
                "bounds": [float(value) for value in source.bounds],
                "nodata": (
                        None
                        if source.nodata is None
                        or not np.isfinite(float(source.nodata))
                        else float(source.nodata)
                ),
                "valid_pixel_count": int(finite.size),
                "minimum": float(finite.min()) if finite.size else None,
                "maximum": float(finite.max()) if finite.size else None,
                "mean": float(finite.mean()) if finite.size else None,
                "status": "PASS",
            }
            return summary
    except Exception as exc:
        return {
            "exists": True,
            "path": str(path),
            "status": "BLOCKED",
            "error": str(exc),
        }


def audit_live_pair(db) -> Dict:
    pair = next(
        (
            item
            for item in db.get_insar_pairs()
            if item["pair_id"] == "PAIR_20261109_20261121"
        ),
        None,
    )
    if pair is None:
        return {"status": "BLOCKED", "message": "Existing live pair is missing."}

    los_path = Path(pair["los_disp_tif"]) if pair.get("los_disp_tif") else None
    coherence_path = Path(pair["coherence_tif"]) if pair.get("coherence_tif") else None
    los = _raster_summary(los_path) if los_path else {"exists": False, "status": "NOT_TESTED"}
    coherence = _raster_summary(coherence_path) if coherence_path else {
        "exists": False,
        "status": "NOT_TESTED",
    }

    quality_valid = 0
    if los.get("exists") and coherence.get("exists"):
        with rasterio.open(los_path) as los_source:
            los_values = los_source.read(1, masked=True)
        with rasterio.open(coherence_path) as coherence_source:
            coherence_values = coherence_source.read(1, masked=True)
        los_array = np.asarray(los_values)
        coherence_array = np.asarray(coherence_values)
        quality_valid = int(
            np.count_nonzero(
                np.isfinite(los_array)
                & np.isfinite(coherence_array)
                & (coherence_array >= 0.50)
            )
        )

    return {
        "status": "PASS WITH LIMITATIONS",
        "pair_id": pair["pair_id"],
        "reference_acquisition": pair["reference_acq_id"],
        "secondary_acquisition": pair["secondary_acq_id"],
        "reference_date": pair["reference_date"],
        "secondary_date": pair["secondary_date"],
        "temporal_baseline_days": pair["temporal_baseline_days"],
        "relative_orbit": pair.get("relative_orbit"),
        "orbit_direction": pair.get("orbit_direction"),
        "processing_method": pair["processing_mode"],
        "hyp3_job_id": pair.get("hyp3_job_id"),
        "processing_status": pair["processing_status"],
        "quality_status": pair["quality_status"],
        "coherence_threshold": 0.50,
        "quality_valid_pixel_count": quality_valid,
        "los": los,
        "coherence": coherence,
        "reference_metadata": {
            "phase_ref_lat": pair.get("phase_ref_lat"),
            "phase_ref_lon": pair.get("phase_ref_lon"),
            "reference_consistency": "REFERENCE_CONVENTION_NOT_REESTABLISHED",
        },
    }


def assess_network(db) -> Dict:
    pairs = db.get_insar_pairs()
    network = build_interferogram_network(pairs)
    valid_edges = network["valid_edges"]

    nodes = network["nodes"]
    rank = None
    if len(valid_edges) == 1:
        rank = 1
    elif len(valid_edges) > 1:
        node_index = {node: index for index, node in enumerate(sorted(nodes))}
        matrix = np.zeros((len(valid_edges), max(0, len(nodes) - 1)))
        reference = sorted(nodes)[0]
        for row, edge in enumerate(valid_edges):
            if edge.secondary_date != reference:
                matrix[row, node_index[edge.secondary_date] - 1] = 1.0
            if edge.reference_date != reference:
                matrix[row, node_index[edge.reference_date] - 1] -= 1.0
        rank = int(np.linalg.matrix_rank(matrix))

    if len(valid_edges) == 0:
        status = "INSUFFICIENT_TEMPORAL_NETWORK"
        message = "No quality-valid interferogram edge is available."
    elif len(valid_edges) == 1:
        status = "NOT_RELIABLE_WITH_SINGLE_PAIR"
        message = (
            "Only one quality-valid interferogram edge is available; "
            "cumulative LOS displacement and velocity are not reliable."
        )
    elif network["connected_components"] != 1:
        status = "INSUFFICIENT_TEMPORAL_NETWORK"
        message = "The quality-valid network is disconnected."
    elif rank is not None and rank < max(0, len(nodes) - 1):
        status = "INSUFFICIENT_TEMPORAL_NETWORK"
        message = "The temporal observation matrix is rank-deficient."
    else:
        status = "REFERENCE_ALIGNMENT_REQUIRED"
        message = (
            "The network has multiple edges, but pair-specific phase references "
            "must be aligned before inversion."
        )

    network_id = "INSAR_NETWORK_20261122"
    network_json = json.dumps({
        "node_count": len(nodes),
        "edge_count": len(network["edges"]),
        "valid_edge_count": len(valid_edges),
        "connected_components": network["connected_components"],
        "component_sizes": network["component_sizes"],
        "rank": rank,
        "node_dates": nodes,
        "valid_pair_ids": [edge.pair_id for edge in valid_edges],
    }, sort_keys=True)

    with db.cursor() as cur:
        cur.execute(
            "INSERT OR REPLACE INTO insar_temporal_network "
            "(network_id,node_count,edge_count,valid_edge_count,"
            "connected_components,matrix_rank,reference_consistency,status,network_json,"
            "assessed_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                network_id,
                len(nodes),
                len(network["edges"]),
                len(valid_edges),
                network["connected_components"],
                rank,
                "REQUIRES_REFERENCE_ALIGNMENT",
                status,
                network_json,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        cur.execute(
            "INSERT OR REPLACE INTO insar_inversion_runs "
            "(run_id,network_id,run_status,cumulative_displacement_status,"
            "velocity_status,residual_norm,uncertainty_summary,result_status,"
            "limitations,result_json,run_date) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                "INSAR_INVERSION_20261122",
                network_id,
                "BLOCKED",
                "NOT_RELIABLE_WITH_SINGLE_PAIR",
                "NOT_RELIABLE_WITH_SINGLE_PAIR",
                None,
                "Unavailable; no validated multi-temporal network.",
                status,
                "LOS values are pair-specific relative measurements; "
                "No cumulative LOS displacement or velocity is reported.",
                json.dumps({"status": status, "rank": rank}),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    return {
        "status": status,
        "message": message,
        "node_count": len(nodes),
        "edge_count": len(network["edges"]),
        "valid_edge_count": len(valid_edges),
        "connected_components": network["connected_components"],
        "component_sizes": network["component_sizes"],
        "matrix_rank": rank,
        "reference_consistency": "REQUIRES_REFERENCE_ALIGNMENT",
        "valid_pair_ids": [edge.pair_id for edge in valid_edges],
    }


def export_phase6_status(db=None) -> Dict:
    db = db or get_db()
    pair_audit = audit_live_pair(db)
    network = assess_network(db)
    run_id = f"INSAR_AUDIT_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO insar_processing_runs "
            "(run_id,pair_id,processing_method,processing_date,software_versions,"
            "input_files,output_files,quality_threshold,reference_metadata,crs,"
            "grid_shape,nodata_convention,validation_status,limitations) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                "PAIR_20261109_20261121",
                "ASF_HyP3_GAMMA_EXISTING_OUTPUT",
                datetime.now(timezone.utc).isoformat(),
                json.dumps(_tool_versions(), sort_keys=True),
                json.dumps({
                    "reference_acquisition": pair_audit.get("reference_acquisition"),
                    "secondary_acquisition": pair_audit.get("secondary_acquisition"),
                }),
                json.dumps({
                    "los": pair_audit.get("los", {}).get("path"),
                    "coherence": pair_audit.get("coherence", {}).get("path"),
                }),
                0.50,
                json.dumps(pair_audit.get("reference_metadata", {})),
                "EPSG:32644",
                "69x110",
                "NaN or masked NoData; never replaced with zero",
                "PASS_WITH_LIMITATIONS",
                "Pair-specific phase reference and single valid edge; "
                "no real cumulative displacement or velocity.",
            ),
        )
        for raster_type in ("los", "coherence"):
            raster = pair_audit.get(raster_type, {})
            cur.execute(
                "INSERT INTO insar_raster_validation "
                "(run_id,pair_id,raster_type,raster_path,crs,shape,resolution_m,"
                "bounds,nodata_value,valid_pixel_count,low_quality_pixel_count,"
                "minimum_value,maximum_value,mean_value,quality_status,notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    "PAIR_20261109_20261121",
                    raster_type.upper(),
                    raster.get("path"),
                    raster.get("crs"),
                    json.dumps(raster.get("shape")),
                    (
                        float(raster["resolution_m"][0])
                        if raster.get("resolution_m")
                        else None
                    ),
                    json.dumps(raster.get("bounds")),
                    json.dumps(raster.get("nodata")),
                    raster.get("valid_pixel_count"),
                    None,
                    raster.get("minimum"),
                    raster.get("maximum"),
                    raster.get("mean"),
                    raster.get("status", "NOT_TESTED"),
                    "Preserved source raster; LOS is relative line-of-sight.",
                ),
            )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": 6,
        "overall_status": network["status"],
        "live_pair": pair_audit,
        "network": network,
        "temporal_inversion": {
            "status": network["status"],
            "cumulative_displacement_status": "NOT_RELIABLE_WITH_SINGLE_PAIR",
            "velocity_status": "NOT_RELIABLE_WITH_SINGLE_PAIR",
            "uncertainty": "NOT_AVAILABLE",
            "residual_error": None,
        },
        "processing": {
            "interferogram_status": "EXISTING_HYP3_PAIR_VALIDATED",
            "new_hyp3_jobs_submitted": 0,
            "credits_consumed_in_phase": 0,
            "local_processing_tools": _tool_versions(),
        },
        "preservation": db.get_table_counts(),
    }

    destination = PATHS.viewer_data / "master_phase6_status.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return payload
