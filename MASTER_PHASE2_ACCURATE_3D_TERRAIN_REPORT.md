# Master Prompt - Phase 2: Accurate 3D Terrain Report

**Assessment date:** 22 November 2026

## 1. Phase Summary

Status: **PASS WITH LIMITATIONS**

Phase 2 audited and validated the existing real DEM-based terrain rather than
rebuilding or replacing it. The existing raster and GLB assets are internally
consistent and geographically aligned to the declared Tirumala grid.

No source DEM, GLB, texture or Cesium terrain layer was replaced.

## 2. Existing Terrain Audit

### DEM

- Path:
  `data/processed/dinsar/tirumala/gsi_aoi/tirumala_dem_80m_gsi_aoi.tif`
- CRS: EPSG:32644
- Shape: 69 x 110
- Resolution: 80 x 80 m
- Bounds:
  319720,1508840 to 328520,1514360
- DEM nodata: 0.0
- Valid pixels: 4083
- Invalid pixels: 3507
- Minimum valid elevation: 180.02676391601562 m
- Maximum valid elevation: 899.16064453125 m
- Mean valid elevation: 611.13427734375 m
- Median valid elevation: 640.6561889648438 m

The 3507 invalid pixels are from the NoData convention and are not
interpreted as real 0 m elevation. The source raster metadata and alignment
match the project grid.

### Terrain generator

Existing implementation:

- `src/digital_twin/terrain_glb_builder.py`
- Rasterio reads the DEM and metadata.
- NumPy constructs a north-up local ENU mesh.
- Valid vertices and triangles preserve the DEM grid.
- Invalid/NoData vertices and triangles are excluded.
- The GLB is placed at the transformed DEM center:
  79.37384529023056 E, 13.66800780237739 N.
- `vertical_exaggeration` is controlled as a visualization setting.

The existing generated elevation GLB metadata reports:

- 7590 vertices.
- 7821 triangles.
- Base elevation: 180.02676391601562 m.
- Elevation span: 719.1338806152344 m.
- Vertical exaggeration: 1.0 in the manifest.

### Existing Cesium viewer

Existing viewer:

- `viewer/cesium/app.js`
- `viewer/cesium/layers_manifest.json`
- Port 8088 local server.

The viewer uses an ellipsoid terrain provider plus georeferenced GLB terrain
models. The elevation GLB and evidence GLBs share the same DEM grid metadata.
The base Esri satellite imagery is a separate external visual basemap.

## 3. GLB Validation

All 11 existing GLB files were read and checked:

- Magic: `glTF`
- Version: 2
- Declared length equals actual file length

Elevation GLB:

- Path:
  `viewer/cesium/models/tirumala_terrain_elevation.glb`
- Size: 672472 bytes
- Valid GLB2 header.

Live pair GLB:

- Path:
  `viewer/cesium/models/tirumala_terrain_los_pair_20261109_20261121.glb`
- Size: 955992 bytes
- Valid GLB2 header.

No existing GLB was replaced or deleted.

## 4. Corrections Implemented

No source DEM or terrain geometry correction was necessary.

New validation support:

- `scripts/validate_phase2_terrain.py`
- `tests/test_phase2_real_terrain.py`

These files verify:

- DEM CRS.
- 69 x 110 shape.
- 80 x 80 m resolution.
- Valid/invalid pixel statistics.
- GLB header, version and length.
- Manifest elevation metadata.

No elevation value was invented or overwritten.

## 5. Cesium Verification

Verified locally:

- Streamlit: HTTP 200.
- Cesium: HTTP 200.
- Elevation GLB: HTTP 200.
- Six manifest evidence layers.
- Three temporal InSAR pair entries.
- Live pair `PAIR_20261109_20261121`.

Browser-level camera interaction and visual screenshot inspection were not
available in this validation pass. No external terrain tiles or satellite
download was attempted.

## 6. Test Results

Phase 2 focused tests:

- 17 passed.
- 6 subtests passed.

Real asset test:

- Real DEM and elevation GLB validate.

Full suite:

- 114 passed.
- 6 subtests passed.
- 6 warnings.

Warnings are existing test collection/deprecation warnings.

## 7. Preservation Verification

Preserved:

- Database and historical records.
- Existing 3 InSAR pair records.
- Existing pair `PAIR_20261109_20261121`.
- Existing HyP3 job ID.
- 7590 live observation snapshots.
- 7590 temporal observations.
- Existing risk history and alerts.
- Existing GLB assets.
- Existing textures.
- Existing Cesium temporal pair entries.
- Existing dashboard tabs.
- Existing Stage 1-6 implementation.

No database record count differed from the Phase 1 audit.

## 8. Limitations

- Independent ground-survey control points were not audited.
- Cesium uses a GLB mesh rather than a hosted terrain tileset.
- The existing centre and bounds are derived from the DEM grid.
- NoData boundaries are visible as missing/triangulated exclusions.
- Elevation is measured from the real DEM plus the relative base datum used
  by the GLB builder.
- Existing Cesium visualization may apply a scene exaggeration; this is not
  source elevation height.

## 9. Phase 3 Readiness

Phase 2 is ready for Phase 3 GIS evidence integration.

The existing DEM and GLB:

- Use the same EPSG:32644 geographic frame.
- Are aligned to 80 m, 69 x 110 grid metadata.
- Preserve valid elevation and NoData cells.
- Have valid GLB headers and manifest references.

Phase 3 may continue with existing layers without replacing the DEM or terrain
assets.
