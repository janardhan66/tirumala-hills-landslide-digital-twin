"""
NASA GPM IMERG Rainfall Data Download

Downloads IMERG Final Daily V07C GeoTIFFs from NASA GES DISC,
clips to Tirumala study area, and calculates rolling accumulations.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import CREDENTIALS, PATHS, RAINFALL, STUDY_AREA, setup_logging
from src.data.db import get_db

logger = setup_logging("download_rainfall")


class IMERGDownloader:
    """Downloads NASA GPM IMERG daily precipitation data."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.db = get_db()
        self.output_dir = PATHS.processed_rainfall
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir = PATHS.raw_rainfall
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """Get authenticated session for NASA Earthdata."""
        if self._session is None:
            if not CREDENTIALS.earthdata_username or not CREDENTIALS.earthdata_password:
                raise ValueError(
                    "NASA Earthdata credentials not configured. "
                    "Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env."
                )
            self._session = requests.Session()
            self._session.auth = (CREDENTIALS.earthdata_username, CREDENTIALS.earthdata_password)
        return self._session

    def _build_url(self, date: datetime, product: str = "final") -> str:
        """Build download URL for IMERG daily GeoTIFF."""
        if product == "late":
            base = RAINFALL.late_base_url
        else:
            base = RAINFALL.base_url

        year = date.strftime("%Y")
        month = date.strftime("%m")
        date_str = date.strftime("%Y%m%d")

        # IMERG Final Daily V07C filename pattern
        filename = (
            f"3B-DAY.MS.MRG.3IMERG.{date_str}-S000000-E235959."
            f"V07C.1day.tif"
        )
        return f"{base}/{year}/{month}/{filename}"

    def _find_cmr_granule(self, date: datetime, product: str) -> Optional[Tuple[str, str]]:
        """Resolve an official IMERG granule through NASA CMR metadata."""
        short_name = "GPM_3IMERGDL" if product == "late" else "GPM_3IMERGDF"
        date_str = date.strftime("%Y-%m-%d")
        temporal = f"{date_str}T00:00:00Z,{date_str}T23:59:59Z"
        response = requests.get(
            "https://cmr.earthdata.nasa.gov/search/granules.json",
            params={
                "short_name": short_name,
                "version": "07",
                "temporal": temporal,
                "page_size": 20,
            },
            timeout=60,
        )
        response.raise_for_status()
        entries = response.json().get("feed", {}).get("entry", [])
        for entry in entries:
            title = str(entry.get("title", ""))
            if ".nc4" not in title.lower():
                continue
            for link in entry.get("links", []):
                href = str(link.get("href", ""))
                if (
                    href.startswith("https://")
                    and "gesdisc.earthdata.nasa.gov/data/" in href
                    and href.lower().endswith(".nc4")
                ):
                    return href, title
        return None

    def _download_daily_tif(self, date: datetime) -> Optional[Tuple[Path, str]]:
        """Download a daily IMERG GeoTIFF, preferring Final over Late."""
        date_str = date.strftime("%Y-%m-%d")
        session = self._get_session()
        for product in ("final", "late"):
            quality = product.upper()
            granule = self._find_cmr_granule(date, product)
            if granule is None:
                logger.info("No CMR granule is available for %s %s.", quality, date_str)
                continue
            url, title = granule
            extension = ".nc4"
            out_path = self.raw_dir / (
                f"imerg_daily_{product}_{date.strftime('%Y%m%d')}{extension}"
            )
            if out_path.is_file():
                logger.debug("Already cached: %s", out_path.name)
                return out_path, quality

            logger.info(
                "Downloading official CMR IMERG %s granule for %s: %s",
                quality,
                date_str,
                title,
            )
            response = session.get(url, timeout=120, allow_redirects=True, stream=True)
            partial_path = out_path.with_name(out_path.name + ".part")
            try:
                if response.status_code == 404:
                    continue
                if response.status_code == 401:
                    raise PermissionError(
                        "NASA Earthdata rejected the configured credentials."
                    )
                response.raise_for_status()
                expected_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                with partial_path.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=131072):
                        if chunk:
                            output.write(chunk)
                            downloaded += len(chunk)
                if downloaded == 0 or (expected_size and downloaded != expected_size):
                    raise IOError(
                        f"Incomplete IMERG download for {date_str}: "
                        f"received {downloaded} of {expected_size} bytes."
                    )

                import rasterio

                with rasterio.open(partial_path) as dataset:
                    if dataset.count < 1:
                        raise ValueError(f"IMERG download has no raster bands: {date_str}")
                os.replace(partial_path, out_path)
                logger.info("Downloaded: %s (%.1f KB)", out_path.name, downloaded / 1024)
                return out_path, quality
            finally:
                response.close()
                if partial_path.exists():
                    partial_path.unlink()

        logger.info("No IMERG Final or Late product is available for %s.", date_str)
        return None

    def _extract_tirumala_rainfall(self, tif_path: Path) -> Optional[float]:
        """Extract mean rainfall over Tirumala from a global IMERG GeoTIFF."""
        if tif_path.suffix.lower() in {".nc4", ".nc"}:
            import h5py

            with h5py.File(tif_path, "r") as granule:
                candidates = []

                def collect(name, obj):
                    if isinstance(obj, h5py.Dataset) and name.lower().endswith(
                        ("precipitation", "precipitationcal")
                    ):
                        candidates.append(name)

                granule.visititems(collect)
                if not candidates:
                    raise ValueError(
                        f"IMERG NetCDF granule has no precipitation dataset: {tif_path}"
                    )
                precipitation = np.asarray(granule[candidates[0]][:], dtype=np.float64)
                latitude = None
                longitude = None
                for possible in (
                    "/Grid/lat",
                    "/Grid/latitude",
                    "lat",
                    "latitude",
                ):
                    if possible in granule:
                        latitude = np.asarray(granule[possible][:], dtype=np.float64)
                        break
                for possible in (
                    "/Grid/lon",
                    "/Grid/longitude",
                    "lon",
                    "longitude",
                ):
                    if possible in granule:
                        longitude = np.asarray(granule[possible][:], dtype=np.float64)
                        break
                for name in ("lat", "latitude", "lon", "longitude"):
                    if name in granule:
                        if name.startswith("lat"):
                            latitude = np.asarray(granule[name][:], dtype=np.float64)
                        else:
                            longitude = np.asarray(granule[name][:], dtype=np.float64)
                    for possible in (
                        f"/Grid/{name}",
                        f"/Grid/{name}itude" if name.startswith("lat") else f"/Grid/{name}",
                    ):
                        if possible in granule:
                            if name.startswith("lat"):
                                latitude = np.asarray(granule[possible][:], dtype=np.float64)
                            else:
                                longitude = np.asarray(granule[possible][:], dtype=np.float64)
                if latitude is None or longitude is None:
                    raise ValueError(
                        f"IMERG NetCDF granule has no latitude/longitude arrays: {tif_path}"
                    )

                while precipitation.ndim > 2:
                    precipitation = np.take(precipitation, 0, axis=0)
                lat_mask = (
                    (latitude >= STUDY_AREA.bbox_south)
                    & (latitude <= STUDY_AREA.bbox_north)
                )
                lon_mask = (
                    (longitude >= STUDY_AREA.bbox_west)
                    & (longitude <= STUDY_AREA.bbox_east)
                )
                if precipitation.shape == (latitude.size, longitude.size):
                    data = precipitation[np.ix_(lat_mask, lon_mask)]
                elif precipitation.shape == (longitude.size, latitude.size):
                    data = precipitation[np.ix_(lon_mask, lat_mask)]
                else:
                    raise ValueError(
                        f"IMERG NetCDF precipitation shape {precipitation.shape} "
                        f"does not match lat/lon sizes."
                    )
                values = np.asarray(data, dtype=np.float64).ravel()
        else:
            import rasterio
            from rasterio.warp import transform_bounds
            from rasterio.windows import from_bounds

            with rasterio.open(tif_path) as src:
                if src.crs is None:
                    raise ValueError(f"IMERG raster has no CRS: {tif_path}")
                bounds = STUDY_AREA.bbox
                if src.crs.to_epsg() != STUDY_AREA.epsg_geographic:
                    bounds = transform_bounds(
                        f"EPSG:{STUDY_AREA.epsg_geographic}", src.crs, *bounds
                    )
                window = from_bounds(*bounds, transform=src.transform)
                data = src.read(1, window=window, masked=True)
            values = np.asarray(data.compressed(), dtype=np.float64)
        valid = values[
            np.isfinite(values)
            & (values >= 0)
            & (values != 29999)
        ]
        if valid.size == 0:
            return None
        mean_precip = float(np.mean(valid * RAINFALL.scale_factor))
        return round(mean_precip, 2)

    def _calculate_rolling(self, daily_values: List[Dict]) -> List[Dict]:
        """Calculate 1-day, 3-day, 7-day, and 14-day rolling accumulations."""
        if not daily_values:
            return []

        sorted_values = sorted(daily_values, key=lambda record: record["date"])
        by_date = {}
        for record in sorted_values:
            datetime.strptime(record["date"], "%Y-%m-%d")
            if record["date"] in by_date:
                raise ValueError(f"Duplicate rainfall date: {record['date']}")
            value = record["daily_mean_mm"]
            by_date[record["date"]] = (
                float(value)
                if value is not None and np.isfinite(value) and value >= 0
                else None
            )

        enriched = []
        for record in sorted_values:
            item = dict(record)
            current_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            item["rolling_1day_mm"] = by_date[item["date"]]
            for days in (3, 7, 14):
                dates = [
                    (current_date - timedelta(days=offset)).isoformat()
                    for offset in range(days - 1, -1, -1)
                ]
                values = [by_date.get(day) for day in dates]
                item[f"rolling_{days}day_mm"] = (
                    round(sum(values), 2)
                    if len(values) == days and all(value is not None for value in values)
                    else None
                )
            enriched.append(item)
        return enriched

    def run(self, start_date: str, end_date: str) -> Dict:
        """Execute rainfall download and processing."""
        results = {"dates_checked": 0, "downloaded": 0, "db_records": 0, "failed": 0}

        if not self.dry_run and (not CREDENTIALS.earthdata_username or not CREDENTIALS.earthdata_password):
            logger.warning(
                "NASA Earthdata credentials not configured in .env. "
                "Skipping remote precipitation download; pipeline will rely on existing verified rainfall records."
            )
            return {
                "dates_checked": 0, "downloaded": 0, "db_records": 0, "failed": 0,
                "status": "BLOCKED_NO_CREDENTIALS",
                "message": "NASA Earthdata credentials not configured in .env. Skipped remote download."
            }

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Rainfall dates must use YYYY-MM-DD format.") from exc

        if end < start:
            raise ValueError("Rainfall end date must be on or after the start date.")
        context_start = start - timedelta(days=13)
        context_end = start - timedelta(days=1)
        history = self.db.get_rainfall_range(
            context_start.strftime("%Y-%m-%d"),
            context_end.strftime("%Y-%m-%d"),
        )
        daily_values = [
            {
                "date": record["record_date"],
                "daily_mean_mm": record["daily_mean_mm"],
                "source_file": record.get("source_file"),
                "data_quality": record.get("data_quality", "FINAL"),
            }
            for record in history
        ]
        current = start

        while current <= end:
            results["dates_checked"] += 1
            date_str = current.strftime("%Y-%m-%d")

            # Check if already in database
            existing = self.db.get_rainfall_range(date_str, date_str)
            existing_record = existing[0] if existing else None
            existing_quality = (
                existing_record.get("data_quality", "FINAL")
                if existing_record
                else None
            )
            if existing_record and (
                existing_quality != "LATE" or self.dry_run
            ):
                daily_values.append({
                    "date": date_str,
                    "daily_mean_mm": existing_record["daily_mean_mm"],
                    "source_file": existing_record.get("source_file"),
                    "data_quality": existing_quality,
                })
                current += timedelta(days=1)
                continue

            if self.dry_run:
                logger.info("[DRY RUN] Would download rainfall for %s", date_str)
                current += timedelta(days=1)
                continue

            # Download and extract
            download = self._download_daily_tif(current)
            if download:
                tif_path, data_quality = download
                mean_precip = self._extract_tirumala_rainfall(tif_path)
                if mean_precip is not None:
                    daily_values.append({
                        "date": date_str,
                        "daily_mean_mm": mean_precip,
                        "source_file": str(tif_path),
                        "data_quality": data_quality,
                    })
                    results["downloaded"] += 1
                elif existing_record:
                    daily_values.append({
                        "date": date_str,
                        "daily_mean_mm": existing_record["daily_mean_mm"],
                        "source_file": existing_record.get("source_file"),
                        "data_quality": existing_quality,
                    })
                else:
                    logger.warning("No valid IMERG pixels for %s; not storing a rainfall value.", date_str)
                    daily_values.append({
                        "date": date_str,
                        "daily_mean_mm": None,
                        "source_file": str(tif_path),
                        "data_quality": data_quality,
                    })
                    results["failed"] += 1
            elif existing_record:
                daily_values.append({
                    "date": date_str,
                    "daily_mean_mm": existing_record["daily_mean_mm"],
                    "source_file": existing_record.get("source_file"),
                    "data_quality": existing_quality,
                })
            else:
                results["failed"] += 1
                daily_values.append({
                    "date": date_str,
                    "daily_mean_mm": None,
                    "source_file": None,
                    "data_quality": None,
                })

            current += timedelta(days=1)

        # Calculate rolling accumulations
        enriched = self._calculate_rolling(daily_values)

        # Store in database
        for record in enriched:
            if (
                start_date <= record["date"] <= end_date
                and record["daily_mean_mm"] is not None
            ):
                self.db.add_rainfall_record(
                    record_date=record["date"],
                    daily_mean_mm=record["daily_mean_mm"],
                    rolling_1day_mm=record.get("rolling_1day_mm"),
                    rolling_3day_mm=record.get("rolling_3day_mm"),
                    rolling_7day_mm=record.get("rolling_7day_mm"),
                    rolling_14day_mm=record.get("rolling_14day_mm"),
                    source_product=(
                        RAINFALL.late_product
                        if record.get("data_quality") == "LATE"
                        else RAINFALL.product
                    ),
                    source_file=record.get("source_file"),
                    data_quality=record.get("data_quality", "FINAL"),
                )
                results["db_records"] += 1

        # Export updated CSV
        self._export_csv(enriched)

        logger.info(
            "Rainfall: %d dates checked, %d downloaded, %d DB records, %d failed.",
            results["dates_checked"], results["downloaded"],
            results["db_records"], results["failed"],
        )
        return results

    def _export_csv(self, records: List[Dict]):
        """Export rainfall records to CSV."""
        if not records:
            return
        import pandas as pd

        df = pd.DataFrame(records)
        if "date" in df.columns:
            df = df.rename(columns={"date": "record_date"})
        out_path = self.output_dir / "tirumala_rainfall_updated.csv"
        df.to_csv(out_path, index=False)
        logger.info("Exported rainfall CSV: %s", out_path)


def main():
    parser = argparse.ArgumentParser(description="Download NASA GPM IMERG rainfall for Tirumala.")
    parser.add_argument("--start-date", default=(datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d"))
    parser.add_argument("--end-date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    dl = IMERGDownloader(dry_run=args.dry_run)
    results = dl.run(args.start_date, args.end_date)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
