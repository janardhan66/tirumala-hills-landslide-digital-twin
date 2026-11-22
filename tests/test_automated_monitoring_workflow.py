"""
Automated Continuous Landslide Monitoring Workflow Integration Test Suite

Verifies the 12 key capabilities of the Tirumala Hills Landslide Digital Twin:
  Test 1: New product discovery (CDSE OData)
  Test 2: Duplicate detection & prevention
  Test 3: Actual product download (or BLOCKED if unconfigured credentials)
  Test 4: Failed download retry functionality
  Test 5: NASA GPM IMERG rainfall ingestion
  Test 6: Data preprocessing & 80m grid alignment
  Test 7: InSAR processing verification (SNAP / HyP3)
  Test 8: 14-Channel PyTorch U-Net input compatibility
  Test 9: Dynamic multi-criteria risk database update
  Test 10: CesiumJS 3D Digital Twin live asset synchronization
  Test 11: Background APScheduler execution & concurrency lock
  Test 12: Streamlit Dashboard data consistency & Gemini integration
"""

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import CREDENTIALS, PATHS, STUDY_AREA
from src.data.db import get_db
from src.data.catalog import ProductCatalog


class TestContinuousMonitoringWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = get_db()
        cls.catalog = ProductCatalog()

    def test_01_discovery_copernicus_cdse(self):
        """Test 1: Discover Sentinel-1 acquisitions via public CDSE OData API."""
        from scripts.download_sentinel1 import Sentinel1Downloader
        downloader = Sentinel1Downloader(dry_run=True)
        # Search Tirumala AOI for August 2026
        products = downloader.search_products("2026-08-01", "2026-08-30")
        self.assertIsInstance(products, list)
        self.assertGreater(len(products), 0, "CDSE OData API should discover Sentinel-1 acquisitions over Tirumala.")
        first = downloader._parse_product(products[0])
        self.assertIn("acquisition_id", first)
        self.assertEqual(first["satellite"], "Sentinel-1")

    def test_02_duplicate_detection(self):
        """Test 2: Ensure existing registered acquisitions are detected as duplicates."""
        test_id = "S1D_IW_SLC__1SDV_20260805"
        self.assertTrue(self.db.acquisition_exists(test_id), "Baseline test acquisition should exist in SQLite.")
        self.assertFalse(self.catalog.is_product_new(test_id), "is_product_new must return False for existing IDs.")

    def test_03_download_credentials_handling(self):
        """Test 3: Test download attempt behavior (real download if creds exist, else BLOCKED)."""
        from scripts.download_sentinel1 import Sentinel1Downloader
        downloader = Sentinel1Downloader()
        has_creds = bool(CREDENTIALS.cdse_username and CREDENTIALS.cdse_password)
        if not has_creds:
            print("\n  [TEST 3 NOTE] CDSE credentials not configured in .env. Verified graceful BLOCKED handling.")
            with self.assertRaises(ValueError) as ctx:
                downloader.auth.get_token()
            self.assertIn("CDSE credentials not configured", str(ctx.exception))
        else:
            token = downloader.auth.get_token()
            self.assertTrue(bool(token), "CDSE Auth should produce a valid OAuth2 bearer token.")

    def test_04_failed_download_retry(self):
        """Test 4: Verify reset_failed_to_pending and retry query logic."""
        with self.db.cursor() as cur:
            failed_before = cur.execute("SELECT COUNT(*) FROM acquisitions WHERE download_status = 'FAILED'").fetchone()[0]
        pending_and_failed = self.catalog.get_pending_and_failed_acquisitions()
        self.assertIsInstance(pending_and_failed, list)
        # Test reset helper
        reset_count = self.catalog.reset_failed_to_pending("test_non_existent_id")
        self.assertEqual(reset_count, 0)

    def test_05_rainfall_ingestion_and_rolling(self):
        """Test 5: Verify rainfall time series records and rolling calculations."""
        records = self.db.get_rainfall_range("2026-08-01", "2026-08-29")
        self.assertGreaterEqual(len(records), 25, "Database must contain verified historical rainfall records.")
        latest = records[-1]
        self.assertIn("rolling_3day_mm", latest)
        self.assertIn("rolling_7day_mm", latest)
        self.assertGreaterEqual(latest["rolling_3day_mm"], 0.0)
        # Verify that accumulated rainfall was computed for wet period
        max_3d = max(r.get("rolling_3day_mm", 0.0) for r in records if r.get("rolling_3day_mm") is not None)
        self.assertGreater(max_3d, 0.0, "Historical rainfall records must have positive 3-day accumulations.")

    def test_06_data_preprocessing_and_alignment(self):
        """Test 6: Verify preprocessing alignment check and baseline rasters."""
        from scripts.preprocess_data import validate_alignment, preprocess_new_acquisitions
        # Verify DEM raster exists and has EPSG:32644
        self.assertTrue(PATHS.dem_tif.exists(), "Tirumala DEM raster must exist.")
        val = validate_alignment(str(PATHS.dem_tif), expected_crs=32644)
        self.assertTrue(val["valid"], f"DEM raster must be valid EPSG:32644. Details: {val}")

        # Run automated preprocessing worker
        res = preprocess_new_acquisitions(self.db)
        self.assertTrue(res["baseline_ready"], "Baseline terrain layers must be verified READY.")

    def test_07_insar_processing_evaluator(self):
        """Test 7: Verify InSAR processing state and dependencies."""
        from scripts.process_insar import process_new_insar_pairs
        res = process_new_insar_pairs(self.db)
        self.assertIn(res["status"], ["UP_TO_DATE", "BLOCKED", "READY"])
        pairs = self.db.get_insar_pairs()
        self.assertGreaterEqual(len(pairs), 2, "Historical InSAR baseline pairs must be registered.")

    def test_08_unet_compatibility_and_experimental_flag(self):
        """Test 8: Verify 14-channel U-Net input tensor builder and experimental labelling."""
        from src.models.tirumala_patch_builder import TirumalaPatchBuilder
        from scripts.run_unet import load_unet_model

        builder = TirumalaPatchBuilder(stride=64)
        ready = builder.prepare(allow_incomplete=True)
        self.assertTrue(ready, "Patch builder must prepare with DEM and Slope.")
        patches = builder.extract_patches()
        self.assertGreater(len(patches), 0, "Must extract at least 1 patch over Tirumala.")
        sample_patch = patches[0]["tensor"]
        self.assertEqual(sample_patch.shape, (14, 128, 128), "U-Net input patch must have shape (14, 128, 128).")

        # Checkpoint load test
        model = load_unet_model()
        self.assertIsNotNone(model, "PyTorch U-Net model must load cleanly from models/best_unet_model.pth.")

    def test_09_risk_database_update(self):
        """Test 9: Verify multi-criteria risk engine updates database records."""
        history = self.db.get_risk_history()
        self.assertIsNotNone(history, "Database must have active risk history records.")
        self.assertGreater(len(history), 0, "Must contain at least 1 risk history epoch.")
        latest_epoch = history[-1]
        self.assertGreater(latest_epoch.get("total_cells", 0), 2500, "Must evaluate at least 2,500 spatial cells.")

    def test_10_cesium_digital_twin_sync(self):
        """Test 10: Verify Cesium 3D Digital Twin asset export and sync_status."""
        from scripts.export_cesium_data import export_all_cesium_data
        export_all_cesium_data()

        lookup_file = PATHS.viewer_data / "spatial_grid_lookup.json"
        sync_file = PATHS.viewer_data / "sync_status.json"
        self.assertTrue(lookup_file.exists(), "spatial_grid_lookup.json must exist in viewer/cesium/data.")
        self.assertTrue(sync_file.exists(), "sync_status.json must exist in viewer/cesium/data.")

        with open(sync_file, "r", encoding="utf-8") as f:
            sync_data = json.load(f)
        self.assertEqual(sync_data.get("status"), "SYNCHRONIZED")
        self.assertGreater(sync_data.get("total_cells", 0), 4000)

    def test_11_scheduler_concurrency_and_lock(self):
        """Test 11: Verify MasterPipeline concurrency lock prevents overlapping runs."""
        from automation.pipeline import MasterPipeline
        lock_file = PATHS.root / "logs" / "pipeline.lock"
        # Simulate active lock
        lock_file.write_text(json.dumps({"pid": os.getpid(), "time": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
        try:
            pipe = MasterPipeline(dry_run=False)
            res = pipe.run_all()
            self.assertFalse(res.success, "Overlapping pipeline run must be rejected when active PID holds lock.")
            self.assertIn("concurrency_check", res.stages)
        finally:
            if lock_file.exists():
                lock_file.unlink()

    def test_12_dashboard_database_consistency(self):
        """Test 12: Verify database consistency and Gemini configuration."""
        counts = self.db.get_table_counts()
        self.assertGreater(counts.get("acquisitions", 0), 0)
        self.assertGreater(counts.get("rainfall_records", 0), 0)
        self.assertGreater(counts.get("spatial_evidence_grid", 0), 0)
        self.assertGreater(counts.get("alerts", 0), 0)

        # Gemini API Key test
        gemini_key = os.environ.get("GEMINI_API_KEY")
        self.assertTrue(bool(gemini_key), "GEMINI_API_KEY must be configured in .env.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
