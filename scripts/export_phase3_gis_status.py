"""Export validated Phase 3 GIS evidence metadata and registry."""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS
from src.data.db import get_db
from src.digital_twin.phase3_validation import audit_gsi_inventory, validate_raster_grid


def create_backup(file_path: Path) -> Path:
    if not file_path.is_file():
        return None
    backup_dir = file_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"{file_path.stem}_phase3_{stamp}{file_path.suffix}"
    shutil.copy2(file_path, backup)
    return backup


def export_phase3_status() -> dict:
    gsi_aoi_dir = PATHS.processed_dinsar
    dem_path = gsi_aoi_dir / "tirumala_dem_80m_gsi_aoi.tif"
    raster_paths = {
        "dem": dem_path,
        "slope": gsi_aoi_dir / "tirumala_slope_80m_gsi_aoi.tif",
        "aspect": gsi_aoi_dir / "tirumala_aspect_80m_gsi_aoi.tif",
        "insar_los": (
            gsi_aoi_dir
            / "PAIR_20261109_20261121"
            / "tirumala_live_los_disp_80m.tif"
        ),
        "insar_coherence": (
            gsi_aoi_dir
            / "PAIR_20261109_20261121"
            / "tirumala_live_coherence_80m.tif"
        ),
    }
    raster_paths = {
        name: path for name, path in raster_paths.items()
        if path.exists()
    }
    alignment = validate_raster_grid(dem_path, raster_paths)

    inventory_csv = (
        PATHS.root
        / "data"
        / "features"
        / "tirumala_gsi_validation_table.csv"
    )
    gsi_output = PATHS.viewer_data / "tirumala_gsi_points.geojson"
    if gsi_output.exists():
        create_backup(gsi_output)
    gsi = audit_gsi_inventory(inventory_csv, gsi_output)

    db = get_db()
    with db.cursor() as cur:
        pair_count = cur.execute(
            "SELECT COUNT(*) FROM insar_pairs"
        ).fetchone()[0]
        live_pair = cur.execute(
            "SELECT * FROM insar_pairs "
            "WHERE pair_id='PAIR_20261109_20261121'"
        ).fetchone()
        live_pair = dict(live_pair) if live_pair else None

    for name, profile in alignment["rasters"].items():
        if "error" in profile:
            continue
        db.register_cesium_layer(
            layer_id=f"phase3_{name}",
            layer_name=name,
            layer_type="raster_overlay",
            observation_date=(
                "2026-11-21"
                if name.startswith("insar")
                else None
            ),
            file_path=profile["path"],
            bounds_json=json.dumps({
                "bounds": profile["bounds"]
            }),
            metadata_json=json.dumps(profile, sort_keys=True),
            is_active=1,
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "3",
        "status": "PASS" if alignment["valid"] and gsi["valid"] else "PARTIAL",
        "terrain": {
            "dem": str(dem_path),
            "crs": "EPSG:32644",
            "shape": [69, 110],
            "resolution_m": 80.0,
            "source": "existing real DEM",
        },
        "gis_alignment": alignment,
        "gsi_inventory": gsi,
        "temporal": {
            "registered_pair_count": pair_count,
            "live_pair": live_pair,
            "cross_pair_difference": "NOT_SHOWN",
        },
        "scientific_limitations": [
            "LOS is relative to a pair-specific phase reference.",
            "Low coherence is insufficient-quality evidence, not zero movement.",
            "GSI coordinates are approximate map-derived points.",
            "No rainfall or land-cover raster is fabricated.",
        ],
    }

    output = PATHS.viewer_data / "phase3_gis_status.json"
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(output)

    manifest_path = PATHS.viewer_cesium / "layers_manifest.json"
    if manifest_path.is_file():
        manifest_backup = create_backup(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        layer_sources = {
            "elevation": "Tirumala existing validated DEM",
            "slope": "Existing 80 m slope raster",
            "aspect": "Existing 80 m aspect raster",
            "los": "ASF HyP3 PAIR_20261109_20261121 relative LOS",
            "coherence": "ASF HyP3 PAIR_20261109_20261121 coherence",
            "risk_zones": "Existing empirical risk evidence",
        }
        layer_acquisition_dates = {
            "elevation": None,
            "slope": None,
            "aspect": None,
            "los": "2026-11-21",
            "coherence": "2026-11-21",
            "risk_zones": "2026-11-21",
        }
        layer_quality = {
            "elevation": "VALID",
            "slope": "VALID",
            "aspect": "AVAILABLE_WITH_LIMITATION",
            "los": "VALID_WITH_REFERENCE_LIMITATION",
            "coherence": "VALID",
            "risk_zones": "EMPIRICAL_EVIDENCE_NOT_CALIBRATED",
        }
        for layer in manifest.setdefault("layers", []):
            layer_id = layer.get("id")
            layer["source"] = layer_sources.get(layer_id, "Existing project asset")
            layer["acquisition_date"] = layer_acquisition_dates.get(layer_id)
            layer["quality_status"] = layer_quality.get(layer_id, "NOT_TESTED")
            layer["nodata_status"] = (
                "PRESERVED_AS_NODATA_OR_TRANSPARENT"
                if layer_id in {"elevation", "slope", "aspect", "los", "coherence"}
                else "NOT_APPLICABLE"
            )
        manifest["phase3_status"] = payload
        manifest["reference_features"] = {
            "gsi_historical_inventory": {
                "source": "GSI Figure 3.2",
                "record_count": gsi["record_count"],
                "coordinate_quality": gsi["coordinate_quality"],
                "geojson": "./data/tirumala_gsi_points.geojson",
            }
        }
        manifest_temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        manifest_temporary.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        manifest_temporary.replace(manifest_path)
    else:
        manifest_backup = None

    payload["manifest_backup"] = (
        str(manifest_backup)
        if manifest_path.is_file() and "manifest_backup" in locals()
        else None
    )
    return payload


def main():
    print(json.dumps(export_phase3_status(), indent=2))


if __name__ == "__main__":
    main()
