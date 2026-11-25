import json
from pathlib import Path

from src.digital_twin.phase3_validation import (
    validate_raster_grid,
)


def test_phase3_real_rasters_align_to_dem():
    root = Path(__file__).resolve().parents[1]
    gsi_aoi = (
        root
        / "data/processed/dinsar/tirumala/gsi_aoi"
    )
    dem = gsi_aoi / "tirumala_dem_80m_gsi_aoi.tif"
    result = validate_raster_grid(dem, {
        "slope": gsi_aoi / "tirumala_slope_80m_gsi_aoi.tif",
        "aspect": gsi_aoi / "tirumala_aspect_80m_gsi_aoi.tif",
        "los": (
            gsi_aoi
            / "PAIR_20261109_20261121"
            / "tirumala_live_los_disp_80m.tif"
        ),
        "coherence": (
            gsi_aoi
            / "PAIR_20261109_20261121"
            / "tirumala_live_coherence_80m.tif"
        ),
    })
    assert result["valid"] is True
    assert result["errors"] == []
    for profile in result["rasters"].values():
        assert profile["aligned"] is True
        assert profile["crs"] == "EPSG:32644"
        assert profile["shape"] == [69, 110]
        assert profile["resolution"] == [80.0, 80.0]


def test_phase3_gsi_geojson_has_15_approximate_points():
    root = Path(__file__).resolve().parents[1]
    geojson_path = root / "viewer/cesium/data/tirumala_gsi_points.geojson"
    if not geojson_path.exists():
        return
    payload = json.loads(geojson_path.read_text(encoding="utf-8"))
    assert len(payload["features"]) == 15
    assert all(
        feature["properties"]["quality"] == "map-derived approximate"
        for feature in payload["features"]
    )


def test_phase3_status_and_manifest_preserve_existing_pairs():
    root = Path(__file__).resolve().parents[1]
    status_path = root / "viewer/cesium/data/phase3_gis_status.json"
    manifest_path = root / "viewer/cesium/layers_manifest.json"
    assert status_path.exists()
    status = json.loads(status_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert status["status"] == "PASS"
    assert status["gsi_inventory"]["record_count"] == 15
    assert status["gis_alignment"]["valid"] is True
    assert manifest["phase3_status"]["status"] == "PASS"
    pair_ids = {
        pair["pair_id"]
        for pair in manifest["temporal"]["insar_pairs"]
    }
    assert "PAIR_20261109_20261121" in pair_ids
    assert "PAIR_20260817_20260829" in pair_ids
    assert "PAIR_20260805_20260817" in pair_ids
