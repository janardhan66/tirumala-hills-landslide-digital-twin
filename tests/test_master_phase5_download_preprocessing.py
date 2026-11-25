import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.download_sentinel1 import Sentinel1Downloader
from src.data.db import DatabaseManager


class TestPhase5DownloadDatabase(unittest.TestCase):
    def test_phase5_tables_are_additive_and_preserve_existing_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = DatabaseManager(Path(temp_dir) / "phase5.db")
            try:
                table_names = [
                    r[0]
                    for r in db._get_connection().execute(
                        "SELECT name FROM sqlite_master WHERE name LIKE 'sentinel_%'"
                    ).fetchall()
                ]
                self.assertIn("sentinel_download_jobs", table_names)
                self.assertIn("sentinel_download_attempts", table_names)
                self.assertIn("sentinel_archive_validation", table_names)
                self.assertIn("sentinel_preprocessing_readiness", table_names)
                self.assertIn("sentinel_product_inventory", table_names)
                counts = db.get_table_counts()
                self.assertIn("acquisitions", counts)
            finally:
                db.close()


class TestPhase5ArchiveValidation(unittest.TestCase):
    def test_valid_safe_fixture_passes_archive_validation(self):
        downloader = object.__new__(Sentinel1Downloader)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "product-id.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("S1_TEST.SAFE/manifest.safe", "<manifest />")
                archive.writestr(
                    "S1_TEST.SAFE/measurement/s1-iw1-slc-vv-001.tiff",
                    b"fixture",
                )
                archive.writestr(
                    "S1_TEST.SAFE/annotation/s1-iw1-slc-vv-001.xml",
                    "<annotation />",
                )
            result = downloader.validate_archive(path, "product-id")
        self.assertEqual(result["validation_status"], "VALIDATED")
        self.assertTrue(result["zip_integrity"])
        self.assertTrue(result["safe_structure"])
        self.assertTrue(result["measurement_present"])
        self.assertTrue(result["annotation_present"])
        self.assertTrue(result["manifest_present"])

    def test_corrupt_zip_is_quarantined_by_validation_result(self):
        downloader = object.__new__(Sentinel1Downloader)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "corrupt.zip"
            path.write_bytes(b"not a zip")
            result = downloader.validate_archive(path)
        self.assertEqual(result["validation_status"], "QUARANTINED")
        self.assertFalse(result["is_zip"])
        self.assertIsNotNone(result["failure_details"])

    def test_invalid_safe_structure_is_blocked(self):
        downloader = object.__new__(Sentinel1Downloader)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "product-id.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("product.txt", "no SAFE structure")
            result = downloader.validate_archive(path, "product-id")
        self.assertEqual(result["validation_status"], "QUARANTINED")
        self.assertIn("SAFE structure", result["failure_details"])


class TestPhase5DownloadSafety(unittest.TestCase):
    def test_download_requires_explicit_enablement(self):
        downloader = object.__new__(Sentinel1Downloader)
        downloader.dry_run = False
        downloader.download_enabled = False
        downloader.max_downloads = 1
        downloader.catalog = Mock()
        downloader.search_products = Mock(return_value=[{
            "Id": "new-product",
            "Name": "S1_TEST",
            "ContentDate": {"Start": "2026-11-21T00:00:00Z"},
            "Attributes": [],
        }])
        downloader.catalog.is_product_new.return_value = True

        result = downloader.run("2026-11-01", "2026-11-22")

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("explicit", result["blocked_reason"].lower())
        downloader.catalog.register_product.assert_called_once()
        downloader.catalog.mark_downloaded.assert_not_called()

    def test_duplicate_product_is_not_selected_for_download(self):
        downloader = object.__new__(Sentinel1Downloader)
        downloader.dry_run = True
        downloader.catalog = Mock()
        downloader.catalog.is_product_new.return_value = False
        downloader.catalog.needs_download.return_value = False
        downloader.search_products = Mock(return_value=[{
            "Id": "existing-product",
            "Name": "S1_EXISTING",
            "ContentDate": {"Start": "2026-11-21T00:00:00Z"},
            "Attributes": [],
        }])

        result = downloader.run("2026-11-01", "2026-11-22")

        self.assertEqual(result["skipped"], 1)
        downloader.catalog.register_product.assert_not_called()

    def test_http_401_is_not_registered_as_downloaded(self):
        downloader = object.__new__(Sentinel1Downloader)
        downloader.auth = Mock()
        downloader.auth.get_token.return_value = "test-token"
        downloader.download_dir = Path(tempfile.gettempdir())
        downloader.max_download_bytes = 5 * 1024 * 1024 * 1024
        response = Mock()
        response.status_code = 401
        response.raise_for_status.side_effect = RuntimeError("401 Unauthorized")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("scripts.download_sentinel1.requests.get", return_value=response):
            with self.assertRaises(RuntimeError):
                downloader.download_product("product-id", "S1_TEST", max_retries=1)


class TestPhase5PreprocessingStatus(unittest.TestCase):
    def test_tool_inventory_marks_missing_tools_honestly(self):
        from src.monitoring.phase5 import _tool_versions
        tools = _tool_versions()
        self.assertIn("rasterio", tools)
        self.assertIn("gdalinfo", tools)

    def test_no_new_product_returns_waiting_status(self):
        from src.monitoring.phase5 import discover_new_products
        db = Mock()
        db.get_acquisitions_by_status.return_value = []
        db.record_discovery_event.return_value = 1
        downloader = Mock()
        downloader.search_products = Mock(return_value=[
            {
                "Id": "existing-in-catalog",
                "Name": "S1_TEST",
                "ContentDate": {"Start": "2026-11-21T00:00:00Z"},
                "Attributes": [],
            }
        ])
        with patch(
            "src.monitoring.phase5.Sentinel1Downloader",
            return_value=downloader,
        ):
            with patch.object(
                downloader,
                "_parse_product",
                return_value={
                    "acquisition_id": "existing-in-catalog",
                    "acquisition_date": "2026-11-21",
                },
            ):
                db.get_acquisitions_by_status.return_value = [
                    {"acquisition_id": "existing-in-catalog"}
                ]
                result = discover_new_products(db=db)
        self.assertEqual(result["status"], "WAITING_FOR_NEW_DATA")


if __name__ == "__main__":
    unittest.main()
