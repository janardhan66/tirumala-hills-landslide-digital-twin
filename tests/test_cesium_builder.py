import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.digital_twin.terrain_glb_builder import (
    TerrainBuilderError,
    build_terrain_glb,
    generate_terrain_texture,
)


class CesiumTerrainBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.dem_path = self.base_dir / "test_dem.tif"
        self.output_glb = self.base_dir / "output.glb"
        self.output_png = self.base_dir / "output.png"

        # Create a small 5x5 test DEM in EPSG:32644
        self.transform = from_origin(320000, 1512000, 80, 80)
        self.dem_values = np.array([
            [200, 210, 220, 230, 240],
            [220, 240, 260, 280, 300],
            [250, 280, 320, 360, 400],
            [300, 350, 420, 490, 560],
            [350, 420, 510, 600, 700],
        ], dtype=np.float32)

        with rasterio.open(
            self.dem_path,
            "w",
            driver="GTiff",
            height=5,
            width=5,
            count=1,
            dtype=np.float32,
            crs="EPSG:32644",
            transform=self.transform,
            nodata=0,
        ) as dst:
            dst.write(self.dem_values, 1)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_builds_valid_gltf2_binary_container(self):
        meta = build_terrain_glb(self.dem_path, self.output_glb, vertical_exaggeration=2.0)

        self.assertTrue(self.output_glb.exists())
        self.assertEqual(meta["total_vertices"], 25)
        self.assertEqual(meta["total_triangles"], 32)
        self.assertAlmostEqual(meta["min_elevation_m"], 200.0, places=1)
        self.assertAlmostEqual(meta["max_elevation_m"], 700.0, places=1)

        # Inspect binary GLB file structure
        with open(self.output_glb, "rb") as f:
            data = f.read()

        magic, version, length = struct.unpack("<4sII", data[:12])
        self.assertEqual(magic, b"glTF")
        self.assertEqual(version, 2)
        self.assertEqual(length, len(data))

        # Check Chunk 0 (JSON)
        json_len, json_type = struct.unpack("<I4s", data[12:20])
        self.assertEqual(json_type, b"JSON")
        json_bytes = data[20:20 + json_len]
        gltf_json = json.loads(json_bytes.decode("utf-8").strip())

        self.assertIn("asset", gltf_json)
        self.assertEqual(gltf_json["asset"]["version"], "2.0")
        self.assertEqual(len(gltf_json["meshes"]), 1)
        self.assertEqual(len(gltf_json["accessors"]), 4)

        # Check Chunk 1 (BIN)
        bin_offset = 20 + json_len
        bin_len, bin_type = struct.unpack("<I4s", data[bin_offset:bin_offset + 8])
        self.assertEqual(bin_type, b"BIN\x00")
        self.assertGreater(bin_len, 0)

    def test_georeferenced_coordinates_reproject_to_wgs84(self):
        meta = build_terrain_glb(self.dem_path, self.output_glb)
        # Bounding center around UTM 320200, 1511800 should be ~79.33°E, 13.67°N
        self.assertGreater(meta["center_longitude"], 79.0)
        self.assertLess(meta["center_longitude"], 80.0)
        self.assertGreater(meta["center_latitude"], 13.0)
        self.assertLess(meta["center_latitude"], 14.0)

    def test_generate_shaded_relief_texture(self):
        tex_path = generate_terrain_texture(
            self.dem_path,
            self.output_png,
            colormap_name="gist_earth",
            resolution=(256, 256),
        )
        self.assertTrue(Path(tex_path).exists())
        self.assertGreater(Path(tex_path).stat().st_size, 500)

    def test_rejects_missing_raster_file(self):
        with self.assertRaises(TerrainBuilderError):
            build_terrain_glb(self.base_dir / "non_existent.tif", self.output_glb)


if __name__ == "__main__":
    unittest.main()
