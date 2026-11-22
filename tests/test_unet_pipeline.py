import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from scripts.run_unet import save_prediction_geotiff, stitch_predictions
from src.models.tirumala_patch_builder import TirumalaPatchBuilder


class TestTirumalaPatchBuilder(unittest.TestCase):
    def _write_raster(self, path, data, transform, crs="EPSG:32644", nodata=None):
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=data.shape[0],
            width=data.shape[1],
            count=1,
            dtype=data.dtype,
            crs=crs,
            transform=transform,
            nodata=nodata,
        ) as dataset:
            dataset.write(data, 1)

    def test_patch_builder_requires_optical_bands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            transform = from_origin(300000, 1500000, 80, 80)
            dem_path = root / "dem.tif"
            slope_path = root / "slope.tif"
            self._write_raster(
                dem_path, np.full((2, 2), 500, dtype=np.float32), transform
            )
            self._write_raster(
                slope_path, np.full((2, 2), 20, dtype=np.float32), transform
            )

            builder = TirumalaPatchBuilder(
                patch_size=2,
                stride=2,
                dem_path=str(dem_path),
                slope_path=str(slope_path),
            )

            self.assertFalse(builder.prepare(s2_dir=str(root / "empty")))
            self.assertIsNone(builder._s2_data)
            self.assertEqual(builder.extract_patches(), [])

    def test_sentinel2_bands_are_loaded_in_band_number_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            transform = from_origin(300000, 1500000, 80, 80)
            dem_path = root / "dem.tif"
            slope_path = root / "slope.tif"
            self._write_raster(
                dem_path, np.full((2, 2), 500, dtype=np.float32), transform
            )
            self._write_raster(
                slope_path, np.full((2, 2), 20, dtype=np.float32), transform
            )
            for band_number in reversed(range(1, 13)):
                self._write_raster(
                    root / f"tile_B{band_number:02d}_20m.tif",
                    np.full((2, 2), band_number, dtype=np.float32),
                    transform,
                )

            builder = TirumalaPatchBuilder(
                patch_size=2,
                stride=2,
                dem_path=str(dem_path),
                slope_path=str(slope_path),
            )

            self.assertTrue(builder.prepare(s2_dir=str(root)))
            np.testing.assert_array_equal(
                builder._s2_data[:, 0, 0],
                np.arange(1, 13, dtype=np.float32),
            )
            patches = builder.extract_patches()
            self.assertEqual(len(patches), 1)
            self.assertTrue(patches[0]["has_optical"])

    def test_prediction_export_checks_exact_grid_shape_and_masks_nodata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference = root / "dem.tif"
            transform = from_origin(300000, 1500000, 80, 80)
            self._write_raster(
                reference,
                np.array([[500, -9999], [510, 520]], dtype=np.float32),
                transform,
                nodata=-9999,
            )

            with self.assertRaisesRegex(ValueError, "does not match reference"):
                save_prediction_geotiff(
                    np.zeros((3, 3), dtype=np.uint8),
                    np.zeros((3, 3), dtype=np.float32),
                    str(reference),
                    str(root / "output"),
                    "2026-08-17",
                )

            files = save_prediction_geotiff(
                np.zeros((2, 2), dtype=np.uint8),
                np.full((2, 2), 0.2, dtype=np.float32),
                str(reference),
                str(root / "output"),
                "2026-08-17",
            )
            with rasterio.open(files["prediction_tif"]) as prediction:
                self.assertEqual(prediction.read(1)[0, 1], 255)
            with rasterio.open(files["confidence_tif"]) as confidence:
                self.assertEqual(confidence.read(1)[0, 1], -9999)

    def test_empty_prediction_set_cannot_be_stitched(self):
        with self.assertRaisesRegex(ValueError, "empty prediction"):
            stitch_predictions([], (10, 10))


if __name__ == "__main__":
    unittest.main()
