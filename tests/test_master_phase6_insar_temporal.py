import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import rasterio
from rasterio.transform import from_origin

from src.analysis.temporal_insar import (
    InterferogramEdge,
    build_interferogram_network,
    build_per_cell_increment_matrix,
)
from src.data.db import DatabaseManager
from src.monitoring.phase6 import _raster_summary, assess_network, export_phase6_status


class TestPhase6RasterValidation(unittest.TestCase):
    def test_raster_crs_grid_nodata_and_alignment_fixture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "los.tif"
            data = np.array([[0.01, -9999.0], [0.02, 0.03]], dtype=np.float32)
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                height=2,
                width=2,
                count=1,
                dtype="float32",
                crs="EPSG:32644",
                transform=from_origin(319720, 1514360, 80, 80),
                nodata=-9999.0,
            ) as destination:
                destination.write(data, 1)

            summary = _raster_summary(path)

        self.assertEqual(summary["crs"], "EPSG:32644")
        self.assertEqual(summary["shape"], [2, 2])
        self.assertEqual(summary["resolution_m"], [80.0, 80.0])
        self.assertEqual(summary["nodata"], -9999.0)
        self.assertEqual(summary["valid_pixel_count"], 3)

    def test_no_data_is_not_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "coherence.tif"
            data = np.array([[np.nan, 0.6], [0.4, 0.8]], dtype=np.float32)
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                height=2,
                width=2,
                count=1,
                dtype="float32",
                crs="EPSG:32644",
                transform=from_origin(319720, 1514360, 80, 80),
                nodata=np.nan,
            ) as destination:
                destination.write(data, 1)
            summary = _raster_summary(path)

        self.assertEqual(summary["valid_pixel_count"], 3)
        self.assertAlmostEqual(summary["minimum"], 0.4, places=6)


class TestPhase6Network(unittest.TestCase):
    def test_single_valid_edge_is_not_reliable(self):
        pairs = [
            {
                "pair_id": "PAIR_1",
                "reference_date": "2026-08-05",
                "secondary_date": "2026-08-17",
                "processing_status": "PROCESSED",
                "quality_status": "PENDING",
            },
            {
                "pair_id": "PAIR_2",
                "reference_date": "2026-11-09",
                "secondary_date": "2026-11-21",
                "processing_status": "PROCESSED",
                "quality_status": "VALID",
            },
        ]
        network = build_interferogram_network(pairs)
        self.assertEqual(len(network["valid_edges"]), 1)
        self.assertEqual(network["connected_components"], 3)

    def test_disconnected_network_fixture(self):
        pairs = [
            {
                "pair_id": "PAIR_1",
                "reference_date": "2026-08-05",
                "secondary_date": "2026-08-17",
                "processing_status": "PROCESSED",
                "quality_status": "VALID",
            },
            {
                "pair_id": "PAIR_2",
                "reference_date": "2026-11-09",
                "secondary_date": "2026-11-21",
                "processing_status": "PROCESSED",
                "quality_status": "VALID",
            },
        ]
        network = build_interferogram_network(pairs)
        self.assertEqual(len(network["valid_edges"]), 2)
        self.assertEqual(network["connected_components"], 2)

    def test_rank_deficient_fixture_is_not_inverted(self):
        matrix, observations, weights, retained = build_per_cell_increment_matrix(
            ["2026-08-05", "2026-08-17", "2026-08-29"],
            [
                {
                    "pair_id": "PAIR_1",
                    "reference_date": "2026-08-05",
                    "secondary_date": "2026-08-17",
                    "los_displacement_m": 0.01,
                    "coherence": 0.6,
                }
            ],
        )
        self.assertEqual(matrix.shape[0], 1)
        self.assertLess(matrix.shape[0], matrix.shape[1])
        self.assertEqual(retained, ["PAIR_1"])


class TestPhase6DatabaseAndStatus(unittest.TestCase):
    def test_phase6_tables_are_additive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = DatabaseManager(Path(temp_dir) / "phase6.db")
            try:
                names = [
                    r[0]
                    for r in db._get_connection().execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE name LIKE 'insar_%'"
                    ).fetchall()
                ]
                self.assertIn("insar_processing_runs", names)
                self.assertIn("insar_raster_validation", names)
                self.assertIn("insar_temporal_network", names)
                self.assertIn("insar_inversion_runs", names)
            finally:
                db.close()

    def test_live_status_is_not_reliable_with_single_pair(self):
        from src.data.db import get_db
        db = get_db()
        status = assess_network(db)
        self.assertEqual(
            status["status"],
            "NOT_RELIABLE_WITH_SINGLE_PAIR",
        )
        self.assertEqual(status["valid_edge_count"], 1)

    def test_export_never_contains_nan_json(self):
        payload = export_phase6_status()
        import json
        encoded = json.dumps(payload, allow_nan=False)
        self.assertIn("NOT_RELIABLE_WITH_SINGLE_PAIR", encoded)


if __name__ == "__main__":
    unittest.main()
