"""
Sentinel-2 Optical Data Download — Copernicus Data Space Ecosystem (CDSE)

Searches for Sentinel-2 L2A products covering Tirumala Hills, filters by
cloud cover, downloads new products, and optionally computes NDVI.
"""

import argparse
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import (
    CREDENTIALS, PATHS, SENTINEL2, STUDY_AREA, setup_logging,
)
from src.data.catalog import ProductCatalog

logger = setup_logging("download_sentinel2")


class Sentinel2Downloader:
    """Searches and downloads Sentinel-2 L2A products from CDSE."""

    TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

    def __init__(self, dry_run: bool = False, max_cloud: float = 30.0):
        self.catalog = ProductCatalog()
        self.dry_run = dry_run
        self.max_cloud = max_cloud
        self.download_dir = PATHS.raw_sentinel2
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._token: Optional[str] = None
        self._token_expires: float = 0

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires - 60:
            return self._token

        if not CREDENTIALS.cdse_username or not CREDENTIALS.cdse_password:
            raise ValueError("CDSE credentials not configured in .env.")

        resp = requests.post(self.TOKEN_URL, data={
            "client_id": "cdse-public",
            "grant_type": "password",
            "username": CREDENTIALS.cdse_username,
            "password": CREDENTIALS.cdse_password,
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires = now + data.get("expires_in", 600)
        return self._token

    def search_products(self, start_date: str, end_date: str) -> List[Dict]:
        """Search CDSE for Sentinel-2 L2A products over Tirumala."""
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("CDSE search dates must use YYYY-MM-DD format.") from exc
        if end < start:
            raise ValueError("CDSE search end date must be on or after the start date.")

        filters = [
            f"Collection/Name eq '{SENTINEL2.collection}'",
            f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
            f"and att/OData.CSC.StringAttribute/Value eq '{SENTINEL2.product_type}')",
            f"ContentDate/Start ge {start_date}T00:00:00.000Z",
            f"ContentDate/Start le {end_date}T23:59:59.999Z",
            f"OData.CSC.Intersects(area=geography'SRID=4326;{STUDY_AREA.wkt_polygon}')",
        ]

        filter_str = " and ".join(filters)
        url = f"{SENTINEL2.odata_base}/Products"
        params = {
            "$filter": filter_str,
            "$orderby": "ContentDate/Start desc",
            "$top": 50,
            "$expand": "Attributes",
        }

        logger.info("Searching CDSE for Sentinel-2 L2A: %s to %s", start_date, end_date)
        products = []
        while url:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            products.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            params = None

        # Filter by cloud cover
        filtered = []
        for product in products:
            cloud = None
            for attr in product.get("Attributes", []):
                if attr.get("Name") == "cloudCover":
                    cloud = float(attr.get("Value", 100))
            if cloud is not None and cloud <= self.max_cloud:
                filtered.append(product)
                logger.info("  Product %s — cloud: %.1f%%", product.get("Name", "")[:40], cloud)
            elif cloud is not None:
                logger.debug("  Skipping %s — cloud: %.1f%% (exceeds %.0f%%)",
                             product.get("Name", "")[:40], cloud, self.max_cloud)

        logger.info("Found %d products (%d passed cloud filter).", len(products), len(filtered))
        return filtered

    def _parse_product(self, product: Dict) -> Dict:
        attrs = {a.get("Name"): a.get("Value") for a in product.get("Attributes", [])}
        start_str = product.get("ContentDate", {}).get("Start", "")
        acq_date = start_str[:10] if start_str else "unknown"

        return {
            "acquisition_id": product.get("Id", ""),
            "satellite": "Sentinel-2",
            "product_type": SENTINEL2.product_type,
            "sensor_mode": "MSI",
            "orbit_direction": attrs.get("orbitDirection", ""),
            "acquisition_date": acq_date,
            "start_time": start_str,
            "cloud_cover": float(attrs.get("cloudCover", -1)),
            "footprint_wkt": product.get("Footprint", ""),
            "file_size_mb": round(product.get("ContentLength", 0) / 1e6, 1),
            "source_api": "CDSE",
            "metadata_json": json.dumps({"name": product.get("Name", "")}),
        }

    def download_product(self, product_id: str, name: str, max_retries: int = 3) -> Optional[Path]:
        """Download Sentinel-2 L2A product with exponential backoff and resume support."""
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
        if not safe_name:
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", product_id).strip("._")
        out_path = self.download_dir / f"{safe_name}.zip"

        if out_path.exists():
            if zipfile.is_zipfile(out_path):
                logger.info("Already on disk: %s", out_path.name)
                return out_path
            out_path.unlink()

        token = self._get_token()
        url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
        partial_path = out_path.with_name(out_path.name + ".part")
        logger.info("Downloading %s...", safe_name[:50])

        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                headers = {"Authorization": f"Bearer {token}"}
                existing_bytes = partial_path.stat().st_size if partial_path.exists() else 0
                if existing_bytes > 0:
                    headers["Range"] = f"bytes={existing_bytes}-"
                    file_mode = "ab"
                else:
                    file_mode = "wb"

                with requests.get(url, headers=headers, stream=True, timeout=600) as resp:
                    if resp.status_code == 416:
                        existing_bytes = 0
                        file_mode = "wb"
                        headers.pop("Range", None)
                        with requests.get(url, headers=headers, stream=True, timeout=600) as retry_resp:
                            resp = retry_resp
                    resp.raise_for_status()

                    expected_length = resp.headers.get("content-length")
                    downloaded = existing_bytes
                    with partial_path.open(file_mode) as output:
                        for chunk in resp.iter_content(chunk_size=131072):
                            if chunk:
                                output.write(chunk)
                                downloaded += len(chunk)

                    if expected_length and resp.status_code == 200 and downloaded < int(expected_length):
                        raise IOError(
                            f"Incomplete CDSE download for {safe_name}: "
                            f"received {downloaded} of {expected_length} bytes."
                        )

                    if not zipfile.is_zipfile(partial_path):
                        raise IOError(f"CDSE download is not a valid ZIP archive: {safe_name}")
                    with zipfile.ZipFile(partial_path) as archive:
                        archive.infolist()
                    os.replace(partial_path, out_path)
                    logger.info("Downloaded: %s (%.1f MB)", out_path.name, out_path.stat().st_size / 1e6)
                    return out_path
            except Exception as exc:
                last_err = exc
                if "credentials not configured" in str(exc).lower():
                    raise
                if attempt < max_retries:
                    wait_sec = 2 ** attempt
                    logger.warning("Download attempt %d/%d for %s failed: %s. Retrying in %ds...",
                                   attempt, max_retries, safe_name[:40], exc, wait_sec)
                    time.sleep(wait_sec)
                else:
                    logger.error("All %d download attempts failed for %s: %s", max_retries, safe_name[:40], exc)
                    if partial_path.exists():
                        try:
                            partial_path.unlink()
                        except Exception:
                            pass
                    raise last_err

        return None

    def run(self, start_date: str, end_date: str) -> Dict:
        results = {"searched": 0, "new": 0, "downloaded": 0, "skipped": 0, "failed": 0, "products": []}
        products = self.search_products(start_date, end_date)
        results["searched"] = len(products)

        for p in products:
            meta = self._parse_product(p)
            pid = meta["acquisition_id"]

            is_new = self.catalog.is_product_new(pid)
            if not is_new and not self.catalog.needs_download(pid):
                results["skipped"] += 1
                continue
            if is_new and not self.dry_run:
                self.catalog.register_product(meta)
            results["new"] += 1

            if self.dry_run:
                logger.info("[DRY RUN] Would download: %s", meta["acquisition_date"])
                continue

            name = json.loads(meta.get("metadata_json", "{}")).get("name", pid)
            try:
                path = self.download_product(pid, name)
                if path:
                    self.catalog.mark_downloaded(pid, str(path))
                    results["downloaded"] += 1
                    results["products"].append(str(path))
                else:
                    self.catalog.mark_download_failed(pid, "Download returned empty path")
                    results["failed"] += 1
            except Exception as exc:
                err_msg = str(exc)
                self.catalog.mark_download_failed(pid, err_msg)
                results["failed"] += 1
                logger.warning("Download not completed for Sentinel-2 %s (%s): %s",
                               pid[:12], meta["acquisition_date"], err_msg)

        logger.info("Sentinel-2: %d searched, %d new, %d downloaded, %d skipped, %d failed.",
                     results["searched"], results["new"], results["downloaded"],
                     results["skipped"], results["failed"])
        return results

    def retry_pending_and_failed(self) -> Dict:
        """Retry downloading all Sentinel-2 acquisitions marked PENDING or FAILED."""
        pending_items = self.catalog.get_pending_and_failed_acquisitions("Sentinel-2")
        results = {"total": len(pending_items), "downloaded": 0, "failed": 0}
        for item in pending_items:
            pid = item["acquisition_id"]
            name = json.loads(item.get("metadata_json", "{}")).get("name", pid)
            try:
                out = self.download_product(pid, name)
                if out:
                    self.catalog.mark_downloaded(pid, str(out))
                    results["downloaded"] += 1
                else:
                    self.catalog.mark_download_failed(pid, "Download failed")
                    results["failed"] += 1
            except Exception as exc:
                self.catalog.mark_download_failed(pid, str(exc))
                results["failed"] += 1
        return results


def main():
    parser = argparse.ArgumentParser(description="Download Sentinel-2 L2A from CDSE.")
    parser.add_argument("--start-date", default=(datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"))
    parser.add_argument("--end-date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    parser.add_argument("--max-cloud", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dl = Sentinel2Downloader(dry_run=args.dry_run, max_cloud=args.max_cloud)
    results = dl.run(args.start_date, args.end_date)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
