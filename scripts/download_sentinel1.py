"""
Sentinel-1 SAR Data Download — Copernicus Data Space Ecosystem (CDSE)

Searches for new Sentinel-1 IW SLC acquisitions covering Tirumala Hills,
downloads only new products, and updates the local catalog database.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import (
    CREDENTIALS, PATHS, SENTINEL1, STUDY_AREA, setup_logging,
)
from src.data.catalog import ProductCatalog

logger = setup_logging("download_sentinel1")


class CDSEAuthenticator:
    """Handles OAuth2 token acquisition for Copernicus Data Space."""

    def __init__(self):
        self._token: Optional[str] = None
        self._expires_at: float = 0

    def get_token(self) -> str:
        """Get a valid access token, refreshing if expired."""
        now = time.time()
        if self._token and now < self._expires_at - 60:
            return self._token

        if not CREDENTIALS.cdse_username or not CREDENTIALS.cdse_password:
            raise ValueError(
                "CDSE credentials not configured. "
                "Set CDSE_USERNAME and CDSE_PASSWORD in .env file."
            )

        logger.info("Requesting CDSE OAuth2 access token...")
        resp = requests.post(
            SENTINEL1.token_url,
            data={
                "client_id": "cdse-public",
                "grant_type": "password",
                "username": CREDENTIALS.cdse_username,
                "password": CREDENTIALS.cdse_password,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = now + data.get("expires_in", 600)
        logger.info("CDSE token acquired (expires in %ds).", data.get("expires_in", 600))
        return self._token


class Sentinel1Downloader:
    """Searches and downloads Sentinel-1 products from CDSE."""

    def __init__(self, dry_run: bool = False):
        self.auth = CDSEAuthenticator()
        self.catalog = ProductCatalog()
        self.dry_run = dry_run
        self.download_dir = PATHS.raw_sentinel1
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.max_download_bytes = int(
            os.environ.get("S1_MAX_DOWNLOAD_BYTES", str(5 * 1024 * 1024 * 1024))
        )
        self.download_enabled = (
            os.environ.get("S1_DOWNLOAD_ENABLED", "").strip().lower() in {"1", "true", "yes"}
        )
        self.max_downloads = int(os.environ.get("S1_MAX_DOWNLOADS", "1"))

    @staticmethod
    def sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _sufficient_disk_space(self, required_bytes: int) -> bool:
        if required_bytes <= 0:
            required_bytes = self.max_download_bytes
        usage = shutil.disk_usage(self.download_dir)
        return usage.free > required_bytes

    def validate_archive(
        self,
        path: Path,
        expected_product_id: Optional[str] = None,
    ) -> Dict:
        """Validate a downloaded ZIP and its basic SAFE structure."""
        result = {
            "is_zip": False,
            "zip_integrity": False,
            "safe_structure": False,
            "manifest_present": False,
            "measurement_present": False,
            "annotation_present": False,
            "orbit_metadata_present": False,
            "product_id_match": bool(expected_product_id),
            "checksum_sha256": None,
            "validation_status": "QUARANTINED",
            "failure_details": None,
        }
        if not path or not path.is_file() or path.stat().st_size == 0:
            result["failure_details"] = "Downloaded file is missing or empty."
            return result

        result["checksum_sha256"] = self.sha256_file(path)
        result["is_zip"] = zipfile.is_zipfile(path)
        if not result["is_zip"]:
            result["failure_details"] = "File is not a valid ZIP archive."
            return result

        try:
            with zipfile.ZipFile(path) as archive:
                corrupt_member = archive.testzip()
                if corrupt_member:
                    result["failure_details"] = f"Corrupt ZIP member: {corrupt_member}"
                    return result
                result["zip_integrity"] = True
                names = archive.namelist()

                safe_names = [name for name in names if ".SAFE/" in name]
                result["safe_structure"] = bool(safe_names)
                lower_names = [name.lower() for name in names]
                result["manifest_present"] = any(
                    name.endswith("/manifest.safe") or name == "manifest.safe"
                    for name in lower_names
                )
                result["measurement_present"] = any(
                    "/measurement/" in name and name.endswith(".tiff")
                    for name in lower_names
                )
                result["annotation_present"] = any(
                    "/annotation/" in name and name.endswith(".xml")
                    for name in lower_names
                )
                result["orbit_metadata_present"] = any(
                    "orbit" in name or "manifest.safe" in name
                    for name in lower_names
                )
                if expected_product_id:
                    result["product_id_match"] = (
                        expected_product_id in path.name
                        or expected_product_id in "\n".join(names)
                    )
        except (OSError, zipfile.BadZipFile) as exc:
            result["failure_details"] = f"Archive validation failed: {exc}"
            return result

        required = (
            result["zip_integrity"],
            result["safe_structure"],
            result["manifest_present"],
            result["measurement_present"],
            result["annotation_present"],
            result["product_id_match"],
        )
        if all(required):
            result["validation_status"] = "VALIDATED"
        else:
            missing = [
                label for label, present in (
                    ("SAFE structure", result["safe_structure"]),
                    ("manifest", result["manifest_present"]),
                    ("measurement files", result["measurement_present"]),
                    ("annotation files", result["annotation_present"]),
                    ("product identifier", result["product_id_match"]),
                ) if not present
            ]
            result["failure_details"] = "Missing: " + ", ".join(missing)
        return result

    def search_products(
        self, start_date: str, end_date: str
    ) -> List[Dict]:
        """Search CDSE OData API for Sentinel-1 IW SLC products over Tirumala."""
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("CDSE search dates must use YYYY-MM-DD format.") from exc
        if end < start:
            raise ValueError("CDSE search end date must be on or after the start date.")

        # Build OData filter
        filters = [
            f"Collection/Name eq '{SENTINEL1.collection}'",
            f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
            f"and att/OData.CSC.StringAttribute/Value eq '{SENTINEL1.product_type}')",
            f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'operationalMode' "
            f"and att/OData.CSC.StringAttribute/Value eq '{SENTINEL1.sensor_mode}')",
            f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'orbitDirection' "
            f"and att/OData.CSC.StringAttribute/Value eq '{SENTINEL1.orbit_direction}')",
            f"ContentDate/Start ge {start_date}T00:00:00.000Z",
            f"ContentDate/Start le {end_date}T23:59:59.999Z",
            f"OData.CSC.Intersects(area=geography'SRID=4326;{STUDY_AREA.wkt_polygon}')",
        ]

        filter_str = " and ".join(filters)
        url = f"{SENTINEL1.odata_base}/Products"
        params = {
            "$filter": filter_str,
            "$orderby": "ContentDate/Start desc",
            "$top": 50,
            "$expand": "Attributes",
        }

        logger.info("Searching CDSE for Sentinel-1 products: %s to %s", start_date, end_date)
        products = []
        while url:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            products.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            params = None

        logger.info("Found %d Sentinel-1 products.", len(products))
        return products

    def _parse_product(self, product: Dict) -> Dict:
        """Parse CDSE OData product into our metadata format."""
        attrs = {}
        for attr in product.get("Attributes", []):
            name = attr.get("Name", "")
            value = attr.get("Value", "")
            attrs[name] = value

        start_str = product.get("ContentDate", {}).get("Start", "")
        acq_date = start_str[:10] if start_str else "unknown"

        return {
            "acquisition_id": product.get("Id", ""),
            "satellite": "Sentinel-1",
            "product_type": attrs.get("productType", SENTINEL1.product_type),
            "sensor_mode": attrs.get("operationalMode", SENTINEL1.sensor_mode),
            "beam_mode": attrs.get("operationalMode", SENTINEL1.sensor_mode),
            "orbit_direction": attrs.get("orbitDirection", SENTINEL1.orbit_direction),
            "orbit_number": int(attrs.get("orbitNumber", 0)) if attrs.get("orbitNumber") else None,
            "relative_orbit": int(attrs.get("relativeOrbitNumber", 0)) if attrs.get("relativeOrbitNumber") else None,
            "acquisition_date": acq_date,
            "start_time": start_str,
            "acquisition_timestamp": start_str,
            "end_time": product.get("ContentDate", {}).get("End", ""),
            "spatial_coverage": product.get("Footprint", ""),
            "polarisation": attrs.get("polarisationChannels", ""),
            "footprint_wkt": product.get("Footprint", ""),
            "file_size_mb": round(product.get("ContentLength", 0) / 1e6, 1),
            "source_api": "CDSE",
            "metadata_json": json.dumps({
                "name": product.get("Name", ""),
                "online": product.get("Online", True),
            }),
        }

    def download_product(
        self,
        product_id: str,
        product_name: str,
        max_retries: int = 3,
        expected_size: Optional[int] = None,
    ) -> Optional[Path]:
        """Download a single product from CDSE with exponential backoff and resume support."""
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", product_name).strip("._")
        if not safe_name:
            safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", product_id).strip("._")
        out_path = self.download_dir / f"{safe_name}.zip"
        if not self._sufficient_disk_space(
            getattr(self, "max_download_bytes", 5 * 1024 * 1024 * 1024)
        ):
            raise IOError(
                "Insufficient disk space for controlled Sentinel-1 download."
            )
        if out_path.exists():
            if zipfile.is_zipfile(out_path):
                logger.info("Product already on disk: %s", out_path.name)
                return out_path
            out_path.unlink()

        token = self.auth.get_token()
        url = f"{SENTINEL1.download_base}/Products({product_id})/$value"
        partial_path = out_path.with_name(out_path.name + ".part")
        logger.info("Downloading %s...", safe_name)

        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                headers = {"Authorization": f"Bearer {token}"}
                existing_bytes = partial_path.stat().st_size if partial_path.exists() else 0
                if expected_size and existing_bytes > expected_size:
                    partial_path.unlink()
                    existing_bytes = 0
                if existing_bytes > 0:
                    headers["Range"] = f"bytes={existing_bytes}-"
                    file_mode = "ab"
                else:
                    file_mode = "wb"

                with requests.get(
                    url,
                    headers=headers,
                    stream=True,
                    timeout=(30, 600),
                ) as resp:
                    if resp.status_code == 416:  # Range not satisfiable, restart fresh
                        existing_bytes = 0
                        file_mode = "wb"
                        headers.pop("Range", None)
                        with requests.get(
                            url,
                            headers=headers,
                            stream=True,
                            timeout=(30, 600),
                        ) as retry_resp:
                            resp = retry_resp
                    resp.raise_for_status()

                    if resp.status_code == 200 and existing_bytes > 0:
                        existing_bytes = 0
                        file_mode = "wb"

                    content_length = resp.headers.get("content-length")
                    content_range = resp.headers.get("content-range")
                    if resp.status_code == 206:
                        downloaded = existing_bytes
                    else:
                        downloaded = 0

                    if resp.status_code == 206:
                        if not content_range or not content_range.startswith("bytes "):
                            raise IOError(
                                f"CDSE resume response omitted a valid Content-Range header: {safe_name}"
                            )
                        try:
                            range_spec = content_range.split(" ", 1)[1]
                            range_start = int(range_spec.split("-", 1)[0])
                            total_size = int(range_spec.rsplit("/", 1)[1])
                        except (ValueError, IndexError) as exc:
                            raise IOError(
                                f"Could not parse CDSE Content-Range header: {content_range}"
                            ) from exc
                        if range_start != existing_bytes:
                            raise IOError(
                                f"CDSE resume started at byte {range_start}, expected {existing_bytes}"
                            )
                        if expected_size is None:
                            expected_size = total_size if total_size >= 0 else None

                    with partial_path.open(file_mode) as output:
                        for chunk in resp.iter_content(chunk_size=8192 * 16):
                            if chunk:
                                output.write(chunk)
                                downloaded += len(chunk)

                    final_size = None
                    if expected_size is not None:
                        final_size = expected_size
                    elif content_length:
                        if resp.status_code == 206:
                            final_size = existing_bytes + int(content_length)
                        else:
                            final_size = int(content_length)
                    if final_size is not None and partial_path.stat().st_size != final_size:
                        raise IOError(
                            f"Incomplete CDSE download for {safe_name}: "
                            f"received {partial_path.stat().st_size} of {final_size} bytes."
                        )

                    if not zipfile.is_zipfile(partial_path):
                        raise IOError(f"CDSE download is not a valid ZIP archive: {safe_name}")
                    with zipfile.ZipFile(partial_path) as archive:
                        bad_member = archive.testzip()
                        if bad_member:
                            raise IOError(
                                f"CDSE ZIP integrity failure for {safe_name}: corrupt member {bad_member}"
                            )
                    os.replace(partial_path, out_path)
                    logger.info("Downloaded %s (%.1f MB).", safe_name, out_path.stat().st_size / 1e6)
                    return out_path
            except Exception as exc:
                last_err = exc
                if "credentials not configured" in str(exc).lower():
                    raise
                if attempt < max_retries:
                    wait_sec = 2 ** attempt
                    logger.warning("Download attempt %d/%d for %s failed: %s. Retrying in %ds...",
                                   attempt, max_retries, safe_name, exc, wait_sec)
                    time.sleep(wait_sec)
                else:
                    logger.error("All %d download attempts failed for %s: %s", max_retries, safe_name, exc)
                    if partial_path.exists():
                        quarantine = partial_path.with_name(
                            f"{partial_path.name}.quarantine-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
                        )
                        try:
                            os.replace(partial_path, quarantine)
                            logger.warning("Quarantined incomplete CDSE partial archive: %s", quarantine)
                        except OSError:
                            logger.exception("Could not quarantine incomplete CDSE partial archive.")
                    raise last_err

        return None

    def run(self, start_date: str, end_date: str) -> Dict:
        """Execute full search-and-download workflow."""
        results = {
            "searched": 0, "new": 0, "skipped": 0,
            "downloaded": 0, "failed": 0, "products": [],
            "status": "WAITING_FOR_NEW_DATA",
            "blocked_reason": None,
            "validated": 0,
        }

        products = self.search_products(start_date, end_date)
        results["searched"] = len(products)

        for product in products:
            meta = self._parse_product(product)
            pid = meta["acquisition_id"]

            # Duplicate check
            is_new = self.catalog.is_product_new(pid)
            if not is_new and not self.catalog.needs_download(pid):
                logger.info("Skipping duplicate: %s (%s)", pid[:12], meta["acquisition_date"])
                results["skipped"] += 1
                continue

            if is_new and not self.dry_run:
                self.catalog.register_product(meta)
            results["new"] += 1

            if self.dry_run:
                logger.info("[DRY RUN] Would download: %s (%s)",
                            meta.get("metadata_json", ""), meta["acquisition_date"])
                continue

            if not getattr(self, "download_enabled", False):
                results["blocked_reason"] = (
                    "Explicit S1_DOWNLOAD_ENABLED=true approval is required."
                )
                results["status"] = "BLOCKED"
                results["skipped"] += 1
                continue

            if results["downloaded"] >= getattr(self, "max_downloads", 1):
                results["blocked_reason"] = "Configured maximum download count reached."
                results["status"] = "BLOCKED"
                results["skipped"] += 1
                continue

            # Download
            name = json.loads(meta.get("metadata_json", "{}")).get("name", pid)
            try:
                expected_size = product.get("ContentLength")
                if isinstance(expected_size, str):
                    try:
                        expected_size = int(expected_size)
                    except ValueError:
                        expected_size = None
                out_path = self.download_product(
                    pid,
                    name,
                    expected_size=expected_size,
                )
                if out_path:
                    validation = self.validate_archive(out_path, pid)
                    if validation["validation_status"] == "VALIDATED":
                        self.catalog.mark_downloaded(pid, str(out_path))
                        results["downloaded"] += 1
                        results["validated"] += 1
                        results["status"] = "DOWNLOADED_VALIDATED"
                        results["products"].append(str(out_path))
                    else:
                        quarantine = out_path.with_name(
                            f"{out_path.name}.quarantine-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
                        )
                        os.replace(out_path, quarantine)
                        self.catalog.mark_download_failed(
                            pid,
                            validation["failure_details"] or "Archive validation failed",
                        )
                        results["failed"] += 1
                        results["status"] = "QUARANTINED"
                else:
                    self.catalog.mark_download_failed(pid, "Download returned empty path")
                    results["failed"] += 1
            except Exception as exc:
                err_msg = str(exc)
                self.catalog.mark_download_failed(pid, err_msg)
                results["failed"] += 1
                logger.warning("Download not completed for %s (%s): %s", pid[:12], meta["acquisition_date"], err_msg)
                # Continue loop so remaining products are catalogued safely

        logger.info(
            "Sentinel-1 download complete: %d searched, %d new, %d downloaded, "
            "%d skipped, %d failed.",
            results["searched"], results["new"], results["downloaded"],
            results["skipped"], results["failed"],
        )
        return results

    def retry_pending_and_failed(self) -> Dict:
        """Retry downloading all acquisitions marked PENDING or FAILED."""
        pending_items = self.catalog.get_pending_and_failed_acquisitions("Sentinel-1")
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
    parser = argparse.ArgumentParser(
        description="Download Sentinel-1 SLC products from CDSE for Tirumala Hills."
    )
    parser.add_argument(
        "--start-date", default=(datetime.now(timezone.utc) - timedelta(days=24)).strftime("%Y-%m-%d"),
        help="Start date (YYYY-MM-DD). Default: 24 days ago.",
    )
    parser.add_argument(
        "--end-date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Search only, do not download.",
    )
    args = parser.parse_args()

    downloader = Sentinel1Downloader(dry_run=args.dry_run)
    results = downloader.run(args.start_date, args.end_date)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
