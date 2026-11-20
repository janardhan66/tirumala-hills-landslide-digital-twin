import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.digital_twin.terrain_3d import (
    TerrainViewError,
    create_terrain_figure,
)


class TerrainFigureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.raster_dir = (
            self.base_dir
            / "data"
            / "processed"
            / "dinsar"
            / "tirumala"
            / "gsi_aoi"
        )
        self.raster_dir.mkdir(parents=True)
        self.transform = from_origin(319720, 1514360, 80, 80)
        self._write_raster(
            "tirumala_dem_80m_gsi_aoi.tif",
            np.array([[200, 210, 220], [230, 240, 250]], dtype=np.float32),
            self.transform,
        )
        self._write_raster(
            "tirumala_slope_80m_gsi_aoi.tif",
            np.array([[5, 10, 15], [20, 25, 30]], dtype=np.float32),
            self.transform,
        )
        self._write_raster(
            "tirumala_corr_80m_gsi_aoi.tif",
            np.full((2, 3), 0.7, dtype=np.float32),
            self.transform,
        )
        self._write_raster(
            "tirumala_los_disp_80m_gsi_aoi.tif",
            np.array([[-0.04, -0.03, -0.02], [-0.03, -0.02, -0.01]], dtype=np.float32),
            self.transform,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_raster(self, filename, values, transform):
        with rasterio.open(
            self.raster_dir / filename,
            "w",
            driver="GTiff",
            height=values.shape[0],
            width=values.shape[1],
            count=1,
            dtype=values.dtype,
            crs="EPSG:32644",
            transform=transform,
            nodata=0,
        ) as dataset:
            dataset.write(values, 1)

    def test_builds_georeferenced_surface_with_selected_overlay(self):
        figure = create_terrain_figure(
            self.base_dir,
            "Slope",
            vertical_exaggeration=2.0,
        )

        self.assertEqual(len(figure.data), 1)
        self.assertEqual(figure.data[0].z.shape, (2, 3))
        self.assertEqual(figure.data[0].surfacecolor[0][0], 5.0)
        self.assertEqual(figure.layout.scene.xaxis.title.text, "Easting (m, UTM 44N)")
        self.assertIn("2x vertical exaggeration", figure.layout.scene.zaxis.title.text)

    def test_rejects_overlay_with_misaligned_transform(self):
        shifted_transform = from_origin(319800, 1514360, 80, 80)
        self._write_raster(
            "tirumala_slope_80m_gsi_aoi.tif",
            np.ones((2, 3), dtype=np.float32),
            shifted_transform,
        )

        with self.assertRaisesRegex(TerrainViewError, "not aligned"):
            create_terrain_figure(self.base_dir, "Slope")

    def test_rejects_unknown_overlay_and_invalid_exaggeration(self):
        with self.assertRaisesRegex(TerrainViewError, "Unsupported"):
            create_terrain_figure(self.base_dir, "Temporal pair difference")
        with self.assertRaisesRegex(TerrainViewError, "positive"):
            create_terrain_figure(self.base_dir, "Elevation", 0)


if __name__ == "__main__":
    unittest.main()
