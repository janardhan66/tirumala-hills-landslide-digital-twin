import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from scripts.download_rainfall import IMERGDownloader
from scripts.download_sentinel1 import Sentinel1Downloader
from scripts.download_sentinel2 import Sentinel2Downloader
from src.data.catalog import ProductCatalog
from src.data.db import DatabaseManager


class TestRainfallIngestion(unittest.TestCase):
    def test_rollups_require_complete_calendar_windows(self):
        downloader = object.__new__(IMERGDownloader)
        records = [
            {"date": "2026-08-01", "daily_mean_mm": 10.0},
            {"date": "2026-08-02", "daily_mean_mm": 10.0},
            {"date": "2026-08-03", "daily_mean_mm": None},
            {"date": "2026-08-04", "daily_mean_mm": 10.0},
        ]

        enriched = downloader._calculate_rolling(records)

        self.assertIsNone(enriched[1]["rolling_3day_mm"])
        self.assertIsNone(enriched[2]["rolling_1day_mm"])
        self.assertIsNone(enriched[3]["rolling_3day_mm"])

    def test_daily_values_use_imerg_scale_and_exclude_fill_pixels(self):
        import rasterio
        from rasterio.transform import from_bounds

        downloader = object.__new__(IMERGDownloader)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "daily.tif"
            data = np.array([[100, 29999], [300, 100]], dtype=np.int16)
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                height=2,
                width=2,
                count=1,
                dtype=data.dtype,
                crs="EPSG:4326",
                transform=from_bounds(79.337, 13.639, 79.423, 13.693, 2, 2),
                nodata=29999,
            ) as dataset:
                dataset.write(data, 1)

            rainfall = downloader._extract_tirumala_rainfall(path)

        self.assertEqual(rainfall, 16.67)

    def test_no_data_download_is_not_stored_as_zero_rainfall(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = object.__new__(IMERGDownloader)
            downloader.dry_run = False
            downloader.db = Mock()
            downloader.db.get_rainfall_range.return_value = []
            downloader.raw_dir = Path(temp_dir)
            downloader.output_dir = Path(temp_dir)
            downloader._download_daily_tif = Mock(
                return_value=(Path(temp_dir) / "missing.tif", "FINAL")
            )
            downloader._extract_tirumala_rainfall = Mock(return_value=None)
            downloader._export_csv = Mock()

            with patch(
                "scripts.download_rainfall.CREDENTIALS.earthdata_username",
                "test-user",
            ), patch(
                "scripts.download_rainfall.CREDENTIALS.earthdata_password",
                "test-password",
            ):
                result = downloader.run("2026-08-01", "2026-08-01")

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["downloaded"], 0)
        self.assertEqual(result["db_records"], 0)
        downloader.db.add_rainfall_record.assert_not_called()

    def test_existing_late_record_is_preserved_when_final_is_unavailable(self):
        record = {
            "record_date": "2026-08-01",
            "daily_mean_mm": 12.5,
            "source_file": "late.tif",
            "data_quality": "LATE",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader = object.__new__(IMERGDownloader)
            downloader.dry_run = False
            downloader.db = Mock()
            downloader.db.get_rainfall_range.side_effect = [[], [record]]
            downloader._download_daily_tif = Mock(return_value=None)
            downloader.output_dir = Path(temp_dir)
            downloader._export_csv = Mock()

            with patch(
                "scripts.download_rainfall.CREDENTIALS.earthdata_username",
                "test-user",
            ), patch(
                "scripts.download_rainfall.CREDENTIALS.earthdata_password",
                "test-password",
            ):
                result = downloader.run("2026-08-01", "2026-08-01")

        self.assertEqual(result["failed"], 0)
        downloader.db.add_rainfall_record.assert_called_once()
        self.assertEqual(
            downloader.db.add_rainfall_record.call_args.kwargs["data_quality"],
            "LATE",
        )


class TestCDSESearch(unittest.TestCase):
    def _response(self, products, next_link=None):
        response = Mock()
        response.raise_for_status.return_value = None
        body = {"value": products}
        if next_link:
            body["@odata.nextLink"] = next_link
        response.json.return_value = body
        return response

    def _zip_response(self):
        contents = io.BytesIO()
        with zipfile.ZipFile(contents, "w") as archive:
            archive.writestr("product.txt", "test")
        payload = contents.getvalue()
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.headers = {"content-length": str(len(payload))}
        response.iter_content.return_value = [payload]
        response.raise_for_status.return_value = None
        return response

    def test_sentinel1_search_follows_odata_next_link(self):
        downloader = object.__new__(Sentinel1Downloader)
        responses = [
            self._response([{"Id": "first"}], "https://catalogue.example/next"),
            self._response([{"Id": "second"}]),
        ]
        with patch("scripts.download_sentinel1.requests.get", side_effect=responses) as get:
            products = downloader.search_products("2026-08-01", "2026-08-31")

        self.assertEqual([product["Id"] for product in products], ["first", "second"])
        self.assertEqual(get.call_count, 2)

    def test_sentinel2_search_follows_odata_next_link(self):
        downloader = object.__new__(Sentinel2Downloader)
        downloader.max_cloud = 30.0
        responses = [
            self._response(
                [{"Id": "first", "Attributes": [{"Name": "cloudCover", "Value": 5}]}],
                "https://catalogue.example/next",
            ),
            self._response(
                [{"Id": "second", "Attributes": [{"Name": "cloudCover", "Value": 10}]}],
            ),
        ]
        with patch("scripts.download_sentinel2.requests.get", side_effect=responses) as get:
            products = downloader.search_products("2026-08-01", "2026-08-31")

        self.assertEqual([product["Id"] for product in products], ["first", "second"])
        self.assertEqual(get.call_count, 2)

    def test_sentinel1_search_surfaces_api_failure(self):
        downloader = object.__new__(Sentinel1Downloader)
        with patch(
            "scripts.download_sentinel1.requests.get",
            side_effect=RuntimeError("network unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "network unavailable"):
                downloader.search_products("2026-08-01", "2026-08-31")

    def test_cdse_search_rejects_invalid_date_range(self):
        downloader = object.__new__(Sentinel1Downloader)
        with self.assertRaisesRegex(ValueError, "on or after"):
            downloader.search_products("2026-08-02", "2026-08-01")
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            downloader.search_products("not-a-date", "2026-08-31")

    def test_sentinel1_dry_run_does_not_register_products(self):
        downloader = object.__new__(Sentinel1Downloader)
        downloader.dry_run = True
        downloader.catalog = Mock()
        downloader.catalog.is_product_new.return_value = True
        downloader.search_products = Mock(return_value=[{
            "Id": "product-id",
            "Name": "S1_TEST",
            "ContentDate": {"Start": "2026-08-17T00:00:00Z"},
            "Attributes": [],
        }])

        result = downloader.run("2026-08-01", "2026-08-31")

        self.assertEqual(result["new"], 1)
        downloader.catalog.register_product.assert_not_called()

    def test_sentinel1_download_is_atomic_and_sanitizes_product_name(self):
        downloader = object.__new__(Sentinel1Downloader)
        downloader.auth = Mock()
        downloader.auth.get_token.return_value = "test-token"
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader.download_dir = Path(temp_dir)
            response = self._zip_response()
            with patch("scripts.download_sentinel1.requests.get", return_value=response):
                path = downloader.download_product("product-id", "..\\..\\product")

            self.assertEqual(path.parent, Path(temp_dir))
            self.assertTrue(zipfile.is_zipfile(path))
            self.assertFalse(Path(str(path) + ".part").exists())

    def test_sentinel2_download_is_atomic(self):
        downloader = object.__new__(Sentinel2Downloader)
        downloader._get_token = Mock(return_value="test-token")
        with tempfile.TemporaryDirectory() as temp_dir:
            downloader.download_dir = Path(temp_dir)
            response = self._zip_response()
            with patch("scripts.download_sentinel2.requests.get", return_value=response):
                path = downloader.download_product("product-id", "product")

            self.assertTrue(zipfile.is_zipfile(path))
            self.assertFalse(Path(str(path) + ".part").exists())


class TestCatalogRetry(unittest.TestCase):
    def test_pending_failed_and_missing_files_remain_downloadable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = DatabaseManager(Path(temp_dir) / "catalog.db")
            try:
                catalog = object.__new__(ProductCatalog)
                catalog.db = database
                product_id = "S1_RETRY_TEST"
                catalog.register_product({
                    "acquisition_id": product_id,
                    "satellite": "Sentinel-1",
                    "product_type": "SLC",
                    "acquisition_date": "2026-08-17",
                })

                self.assertTrue(catalog.needs_download(product_id))
                catalog.mark_download_failed(product_id, "temporary network error")
                self.assertTrue(catalog.needs_download(product_id))

                product_path = Path(temp_dir) / "product.zip"
                product_path.write_bytes(b"downloaded")
                catalog.mark_downloaded(product_id, str(product_path))
                self.assertFalse(catalog.needs_download(product_id))
                product_path.unlink()
                self.assertTrue(catalog.needs_download(product_id))
            finally:
                database.close()


if __name__ == "__main__":
    unittest.main()
