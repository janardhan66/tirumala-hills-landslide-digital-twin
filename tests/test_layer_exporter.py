import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from rasterio.transform import from_origin

from src.features.calculate_aspect import calculate_dem_aspect
from src.digital_twin.layer_exporter import (
    LayerExportError,
    raster_to_rgba_overlay,
)


class LayerExporterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.dem_path = self.base_dir / "test_dem.tif"
        self.aspect_path = self.base_dir / "test_aspect.tif"
        self.output_png = self.base_dir / "test_overlay.png"

        # 5x5 test DEM sloping strictly from North (high) to South (low) -> Aspect should be South (~180 deg)
        self.transform = from_origin(320000, 1512000, 80, 80)
        self.dem_values = np.array([
            [500, 500, 500, 500, 500],
            [400, 400, 400, 400, 400],
            [300, 300, 300, 300, 300],
            [200, 200, 200, 200, 200],
            [100, 100, 100, 100, 100],
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
            nodata=-9999,
        ) as dst:
            dst.write(self.dem_values, 1)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_calculate_dem_aspect_identifies_slope_azimuth(self):
        calculate_dem_aspect(self.dem_path, self.aspect_path)
        self.assertTrue(self.aspect_path.exists())

        with rasterio.open(self.aspect_path) as src:
            aspect = src.read(1)
            # For a North-to-South slope, the aspect azimuth is South (~180 degrees)
            center_aspect = aspect[2, 2]
            self.assertAlmostEqual(center_aspect, 180.0, delta=2.0)

    def test_raster_to_rgba_overlay_produces_georeferenced_bounds(self):
        png_path, bounds = raster_to_rgba_overlay(
            self.dem_path,
            self.output_png,
            colormap_name="gist_earth",
            resolution=(128, 128),
        )

        self.assertTrue(Path(png_path).exists())
        self.assertIn("west", bounds)
        self.assertIn("south", bounds)
        self.assertIn("east", bounds)
        self.assertIn("north", bounds)

        # Bounds should be valid geographic coordinates in India
        self.assertGreater(bounds["west"], 79.0)
        self.assertLess(bounds["east"], 80.0)
        self.assertGreater(bounds["south"], 13.0)
        self.assertLess(bounds["north"], 14.0)

    def test_rejects_missing_raster(self):
        with self.assertRaises(LayerExportError):
            raster_to_rgba_overlay(self.base_dir / "missing.tif", self.output_png)

    def test_rejects_raster_not_aligned_with_reference_grid(self):
        misaligned_path = self.base_dir / "misaligned.tif"
        with rasterio.open(
            misaligned_path,
            "w",
            driver="GTiff",
            height=5,
            width=5,
            count=1,
            dtype=np.float32,
            crs="EPSG:32644",
            transform=from_origin(320080, 1512000, 80, 80),
            nodata=-9999,
        ) as dst:
            dst.write(self.dem_values, 1)

        with self.assertRaises(LayerExportError):
            raster_to_rgba_overlay(
                misaligned_path,
                self.output_png,
                reference_raster_path=self.dem_path,
            )

    def test_rejects_alpha_mask_with_wrong_shape(self):
        with self.assertRaises(LayerExportError):
            raster_to_rgba_overlay(
                self.dem_path,
                self.output_png,
                alpha_mask=np.ones((4, 5), dtype=bool),
            )

    def test_exports_aligned_layer_models_in_manifest(self):
        from src.digital_twin.layer_exporter import export_all_gis_layers

        base_dir = self.base_dir
        raster_dir = base_dir / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi"
        raster_dir.mkdir(parents=True)
        raster_values = np.arange(1, 26, dtype=np.float32).reshape(5, 5)
        raster_names = [
            "tirumala_dem_80m_gsi_aoi.tif",
            "tirumala_slope_80m_gsi_aoi.tif",
            "tirumala_aspect_80m_gsi_aoi.tif",
            "tirumala_los_disp_80m_gsi_aoi.tif",
            "tirumala_corr_80m_gsi_aoi.tif",
        ]
        aspect_values = np.full((5, 5), 180.0, dtype=np.float32)
        aspect_values[0, 0] = -1.0
        los_values = np.linspace(-0.045, -0.006, 25, dtype=np.float32).reshape(5, 5)
        coherence_values = np.full((5, 5), 0.8, dtype=np.float32)
        coherence_values[0, 0] = 0.49
        values_by_name = {
            "tirumala_aspect_80m_gsi_aoi.tif": aspect_values,
            "tirumala_los_disp_80m_gsi_aoi.tif": los_values,
            "tirumala_corr_80m_gsi_aoi.tif": coherence_values,
        }
        for name in raster_names:
            with rasterio.open(
                raster_dir / name,
                "w",
                driver="GTiff",
                height=5,
                width=5,
                count=1,
                dtype=np.float32,
                crs="EPSG:32644",
                transform=self.transform,
                nodata=-9999,
            ) as dst:
                dst.write(values_by_name.get(name, raster_values), 1)

        pair1_dir = raster_dir / "pair_05_17"
        pair1_dir.mkdir()
        pair1_los = np.linspace(-0.035, -0.003, 25, dtype=np.float32).reshape(5, 5)
        pair1_coherence = np.full((5, 5), 0.8, dtype=np.float32)
        pair1_coherence[0, 0] = 0.4
        for name, values in (
            ("tirumala_los_disp_80m_gsi_aoi_pair_05_17.tif", pair1_los),
            ("tirumala_corr_80m_gsi_aoi_pair_05_17.tif", pair1_coherence),
        ):
            with rasterio.open(
                pair1_dir / name,
                "w",
                driver="GTiff",
                height=5,
                width=5,
                count=1,
                dtype=np.float32,
                crs="EPSG:32644",
                transform=self.transform,
                nodata=-9999,
            ) as dst:
                dst.write(values, 1)

        feature_path = base_dir / "data" / "features" / "tirumala_final_agent_evidence.csv"
        feature_path.parent.mkdir(parents=True)
        pd.DataFrame(
            [{"row": 2, "col": 2, "agent_evidence_category": "High"}]
        ).to_csv(feature_path, index=False)

        output_dir = base_dir / "viewer" / "cesium"
        manifest = export_all_gis_layers(base_dir, output_dir)

        self.assertEqual(len(manifest["layers"]), 6)
        for layer in manifest["layers"]:
            self.assertTrue((output_dir / layer["model_url"].removeprefix("./")).exists())

        temporal_pairs = manifest["temporal"]["insar_pairs"]
        self.assertEqual(
            [pair["pair_id"] for pair in temporal_pairs],
            ["PAIR_20260805_20260817", "PAIR_20260817_20260829"],
        )
        for pair in temporal_pairs:
            self.assertTrue((output_dir / pair["model_url"].removeprefix("./")).exists())

        layers = {layer["id"]: layer for layer in manifest["layers"]}
        self.assertEqual(layers["los"]["unit"], "mm")
        self.assertAlmostEqual(layers["los"]["bounds"]["min_value"], -43.375, places=2)
        self.assertAlmostEqual(layers["los"]["bounds"]["max_value"], -6.0, places=2)
        for layer_id in ("aspect", "coherence"):
            with Image.open(output_dir / layers[layer_id]["url"].removeprefix("./")) as image:
                self.assertEqual(image.getpixel((0, 0))[3], 0)
        with Image.open(output_dir / layers["los"]["url"].removeprefix("./")) as image:
            self.assertEqual(image.getpixel((0, 0))[3], 0)
        with Image.open(
            output_dir / "textures" / "layer_los_pair_05_17.png"
        ) as image:
            self.assertEqual(image.getpixel((0, 0))[3], 0)


if __name__ == "__main__":
    unittest.main()
