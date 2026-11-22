import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_bounds

from scripts.preprocess_data import clip_to_aoi, validate_alignment
from src.data.db import DatabaseManager


class TestAlignedPreprocessing(unittest.TestCase):
    def test_clipped_raster_uses_exact_reference_grid_and_preserves_nodata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_path = root / "source.tif"
            reference_path = root / "reference.tif"
            output_path = root / "processed.tif"

            source_data = np.full((1, 10, 10), 12.0, dtype=np.float32)
            source_data[0, 0, 0] = -9999.0
            with rasterio.open(
                source_path,
                "w",
                driver="GTiff",
                height=10,
                width=10,
                count=1,
                dtype="float32",
                crs="EPSG:4326",
                transform=from_bounds(79.337, 13.639, 79.423, 13.693, 10, 10),
                nodata=-9999.0,
            ) as source:
                source.write(source_data)

            transformer = Transformer.from_crs(4326, 32644, always_xy=True)
            west, south = transformer.transform(79.337, 13.639)
            east, north = transformer.transform(79.423, 13.693)
            reference_transform = from_bounds(west, south, east, north, 8, 7)
            with rasterio.open(
                reference_path,
                "w",
                driver="GTiff",
                height=7,
                width=8,
                count=1,
                dtype="float32",
                crs="EPSG:32644",
                transform=reference_transform,
                nodata=np.nan,
            ) as reference:
                reference.write(np.zeros((1, 7, 8), dtype=np.float32))

            result = clip_to_aoi(
                str(source_path),
                str(output_path),
                reference_path=str(reference_path),
            )

            self.assertEqual(result, str(output_path))
            with rasterio.open(output_path) as output:
                self.assertEqual(output.crs.to_epsg(), 32644)
                self.assertEqual(output.shape, (7, 8))
                self.assertEqual(output.transform, reference_transform)
                data = output.read(1, masked=True)
                self.assertTrue(np.any(~np.ma.getmaskarray(data)))
                self.assertTrue(np.any(np.ma.getmaskarray(data)))

            alignment = validate_alignment(str(output_path))
            self.assertTrue(alignment["valid"])

    def test_non_overlapping_source_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "outside.tif"
            with rasterio.open(
                source_path,
                "w",
                driver="GTiff",
                height=2,
                width=2,
                count=1,
                dtype="float32",
                crs="EPSG:4326",
                transform=from_bounds(0, 0, 1, 1, 2, 2),
            ) as source:
                source.write(np.ones((1, 2, 2), dtype=np.float32))

            with self.assertRaisesRegex(ValueError, "does not overlap"):
                clip_to_aoi(
                    str(source_path),
                    str(Path(temp_dir) / "output.tif"),
                    reference_path=str(Path(temp_dir) / "missing-reference.tif"),
                )

    def test_archive_validation_extracts_and_keeps_incomplete_in_sar_state_safe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive_path = root / "sentinel.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("manifest.safe", "metadata")

            db = DatabaseManager(root / "monitoring.db")
            db.add_acquisition(
                acquisition_id="S1_TEST_ARCHIVE",
                satellite="Sentinel-1",
                product_type="SLC",
                acquisition_date="2026-08-29",
                download_status="DOWNLOADED",
                processing_status="UNPROCESSED",
                file_path=str(archive_path),
            )

            from scripts.preprocess_data import preprocess_new_acquisitions
            result = preprocess_new_acquisitions(db)

            assert result["preprocessed"] == 0
            assert db.get_acquisition("S1_TEST_ARCHIVE")["processing_status"] == "UNPROCESSED"
            db.close()


if __name__ == "__main__":
    unittest.main()
