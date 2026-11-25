from scripts.validate_phase2_terrain import validate_phase2_terrain


def test_real_tirumala_dem_and_glb_validate():
    result = validate_phase2_terrain()
    assert result["valid"] is True
    assert result["dem"]["crs"] == "EPSG:32644"
    assert result["dem"]["shape"] == [69, 110]
    assert result["dem"]["resolution"] == [80.0, 80.0]
    assert result["dem"]["valid_pixels"] == 4083
    assert result["glb"]["valid"] is True
    assert result["glb"]["declared_length"] == result["glb"]["actual_length"]
