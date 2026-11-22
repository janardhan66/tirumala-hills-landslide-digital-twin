import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

from scripts.update_database import grid_cell_center_wgs84, read_quality_masked_los_pair
from src.features.temporal_registry import TemporalRegistry


class FakeCursor:
    def __init__(self, rainfall_rows):
        self.rainfall_rows = rainfall_rows

    def execute(self, query):
        self.rows = self.rainfall_rows
        return self

    def fetchall(self):
        return self.rows


class FakeDatabase:
    def __init__(self, pairs, rainfall_rows, observation_dates):
        self.pairs = pairs
        self.rainfall_rows = rainfall_rows
        self.observation_dates = observation_dates

    def get_insar_pairs(self):
        return self.pairs

    def get_observation_dates(self):
        return self.observation_dates

    @contextmanager
    def cursor(self):
        yield FakeCursor(self.rainfall_rows)


def make_pair(pair_id, reference_date, secondary_date):
    return {
        "pair_id": pair_id,
        "reference_date": reference_date,
        "secondary_date": secondary_date,
        "temporal_baseline_days": 12,
        "processing_status": "PROCESSED",
        "valid_pixels": 100,
        "mean_coherence": 0.7,
    }


class TemporalRegistryTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDatabase(
            pairs=[
                make_pair("PAIR_20260817_20260829", "2026-08-17", "2026-08-29"),
                make_pair("PAIR_20260805_20260817", "2026-08-05", "2026-08-17"),
            ],
            rainfall_rows=[
                {
                    "record_date": "2026-08-10",
                    "daily_mean_mm": 4.0,
                    "rolling_3day_mm": 10.0,
                },
                {
                    "record_date": "2026-08-01",
                    "daily_mean_mm": 2.0,
                    "rolling_3day_mm": None,
                },
            ],
            observation_dates=["2026-08-29"],
        )
        self.registry = TemporalRegistry(db=self.db)

    def test_builds_sorted_epochs_and_avoids_duplicate_known_insar_dates(self):
        epochs = self.registry.build_registry()

        self.assertEqual([epoch["date"] for epoch in epochs], sorted(epoch["date"] for epoch in epochs))
        insar_epochs = [epoch for epoch in epochs if epoch["type"] == "insar"]
        self.assertEqual(len(insar_epochs), 4)
        self.assertEqual(
            [pair["pair_id"] for pair in self.registry._insar_pairs],
            ["PAIR_20260805_20260817", "PAIR_20260817_20260829"],
        )
        self.assertEqual(
            len(self.registry.get_epochs_in_range("2026-08-17", "2026-08-29")),
            4,
        )

    def test_rejects_invalid_or_reversed_date_ranges(self):
        self.registry.build_registry()
        with self.assertRaises(ValueError):
            self.registry.get_epochs_in_range("2026-08-29", "2026-08-17")
        with self.assertRaises(ValueError):
            self.registry.get_epochs_in_range("17-08-2026", "2026-08-29")

    def test_export_contains_pair_metadata_and_utc_timestamp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "registry.json"
            self.registry.export_for_cesium(str(output_path))
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["total_epochs"], 7)
        self.assertEqual(len(payload["insar_pairs"]), 2)
        self.assertEqual(payload["insar_pairs"][0]["reference_date"], "2026-08-05")
        self.assertIn("own phase reference", payload["comparison_note"])
        self.assertTrue(payload["generated_at"].endswith("+00:00"))

    def test_invalid_database_observation_dates_fail_explicitly(self):
        self.db.pairs = [
            make_pair("PAIR_BAD", "2026-13-01", "2026-08-17")
        ]
        with self.assertRaisesRegex(ValueError, "Invalid observation date"):
            self.registry.build_registry()

    def test_grid_cell_coordinates_use_the_projected_cell_center(self):
        transform = from_origin(320000, 1512000, 80, 80)
        transformer = Transformer.from_crs("EPSG:32644", "EPSG:4326", always_xy=True)

        easting, northing, latitude, longitude = grid_cell_center_wgs84(
            transform, transformer, 0, 0
        )

        self.assertEqual((easting, northing), (320040.0, 1511960.0))
        self.assertGreater(longitude, 79.0)
        self.assertLess(longitude, 80.0)
        self.assertGreater(latitude, 13.0)
        self.assertLess(latitude, 14.0)

    def test_temporal_pair_lookup_masks_nodata_and_low_coherence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            transform = from_origin(320000, 1512000, 80, 80)
            reference = root / "dem.tif"
            los_path = root / "los.tif"
            coherence_path = root / "coherence.tif"
            los = np.full((5, 5), -0.02, dtype=np.float32)
            coherence = np.full((5, 5), 0.8, dtype=np.float32)
            coherence[0, 0] = 0.4
            los[1, 1] = -9999.0
            coherence[1, 1] = -9999.0

            for path, values, nodata in (
                (reference, np.full((5, 5), 500.0, dtype=np.float32), -9999.0),
                (los_path, los, -9999.0),
                (coherence_path, coherence, -9999.0),
            ):
                with rasterio.open(
                    path,
                    "w",
                    driver="GTiff",
                    height=5,
                    width=5,
                    count=1,
                    dtype=np.float32,
                    crs="EPSG:32644",
                    transform=transform,
                    nodata=nodata,
                ) as destination:
                    destination.write(values, 1)

            los_data, coherence_data, valid = read_quality_masked_los_pair(
                los_path, coherence_path, reference
            )

        self.assertFalse(valid[0, 0])
        self.assertFalse(valid[1, 1])
        self.assertTrue(valid[2, 2])
        self.assertAlmostEqual(float(los_data[2, 2]), -0.02, places=6)
        self.assertAlmostEqual(float(coherence_data[2, 2]), 0.8, places=6)

    def test_temporal_pair_lookup_rejects_misaligned_rasters(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference = root / "dem.tif"
            los_path = root / "los.tif"
            coherence_path = root / "coherence.tif"
            values = np.ones((5, 5), dtype=np.float32)
            for path, transform in (
                (reference, from_origin(320000, 1512000, 80, 80)),
                (los_path, from_origin(320080, 1512000, 80, 80)),
                (coherence_path, from_origin(320000, 1512000, 80, 80)),
            ):
                with rasterio.open(
                    path,
                    "w",
                    driver="GTiff",
                    height=5,
                    width=5,
                    count=1,
                    dtype=np.float32,
                    crs="EPSG:32644",
                    transform=transform,
                    nodata=-9999.0,
                ) as destination:
                    destination.write(values, 1)

            with self.assertRaisesRegex(ValueError, "not aligned"):
                read_quality_masked_los_pair(los_path, coherence_path, reference)


if __name__ == "__main__":
    unittest.main()
