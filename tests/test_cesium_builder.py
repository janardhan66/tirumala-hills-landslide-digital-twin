import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
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

    def _write_dem(self, values, transform=None, crs="EPSG:32644"):
        with rasterio.open(
            self.dem_path,
            "w",
            driver="GTiff",
            height=values.shape[0],
            width=values.shape[1],
            count=1,
            dtype=np.float32,
            crs=crs,
            transform=transform or self.transform,
            nodata=0,
        ) as dst:
            dst.write(values.astype(np.float32), 1)

    def _read_glb(self):
        data = self.output_glb.read_bytes()
        json_len, _ = struct.unpack("<I4s", data[12:20])
        gltf_json = json.loads(data[20:20 + json_len].decode("utf-8").strip())
        bin_offset = 20 + json_len
        bin_len, _ = struct.unpack("<I4s", data[bin_offset:bin_offset + 8])
        binary = data[bin_offset + 8:bin_offset + 8 + bin_len]
        return gltf_json, binary

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

    def test_masks_nodata_vertices_and_computes_valid_normals(self):
        dem = self.dem_values.copy()
        dem[2, 2] = 0
        self._write_dem(dem)

        metadata = build_terrain_glb(self.dem_path, self.output_glb)
        gltf_json, binary = self._read_glb()

        index_accessor = gltf_json["accessors"][3]
        index_view = gltf_json["bufferViews"][index_accessor["bufferView"]]
        indices = np.frombuffer(
            binary,
            dtype="<u4",
            count=index_accessor["count"],
            offset=index_view["byteOffset"] + index_accessor["byteOffset"],
        ).reshape(-1, 3)
        valid = dem.ravel() != 0
        self.assertEqual(metadata["total_triangles"], 26)
        self.assertTrue(np.all(valid[indices]))

        normal_accessor = gltf_json["accessors"][1]
        normal_view = gltf_json["bufferViews"][normal_accessor["bufferView"]]
        normals = np.frombuffer(
            binary,
            dtype="<f4",
            count=normal_accessor["count"] * 3,
            offset=normal_view["byteOffset"] + normal_accessor["byteOffset"],
        ).reshape(-1, 3)
        self.assertTrue(np.all(np.isfinite(normals)))
        np.testing.assert_allclose(np.linalg.norm(normals, axis=1), 1.0, atol=1e-6)
        np.testing.assert_allclose(normals[12], [0.0, 0.0, 1.0], atol=1e-6)

    def test_rejects_invalid_vertical_exaggeration(self):
        for exaggeration in (0.0, -1.0, np.nan, np.inf):
            with self.subTest(exaggeration=exaggeration):
                with self.assertRaises(TerrainBuilderError):
                    build_terrain_glb(
                        self.dem_path,
                        self.output_glb,
                        vertical_exaggeration=exaggeration,
                    )

    def test_rejects_nonprojected_or_rotated_raster(self):
        with self.subTest(crs="EPSG:4326"):
            self._write_dem(
                self.dem_values,
                transform=from_origin(79.0, 14.0, 0.01, 0.01),
                crs="EPSG:4326",
            )
            with self.assertRaises(TerrainBuilderError):
                build_terrain_glb(self.dem_path, self.output_glb)

        with self.subTest(transform="rotated"):
            self._write_dem(
                self.dem_values,
                transform=Affine(80, 1, 320000, 0, -80, 1512000),
            )
            with self.assertRaises(TerrainBuilderError):
                build_terrain_glb(self.dem_path, self.output_glb)


if __name__ == "__main__":
    unittest.main()
