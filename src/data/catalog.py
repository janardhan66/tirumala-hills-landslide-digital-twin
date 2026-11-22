"""
Product Catalog Manager — wraps the database acquisitions table.

Provides high-level functions for checking duplicates, registering new products,
and querying unprocessed products.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import setup_logging
from src.data.db import get_db

logger = setup_logging("catalog")


class ProductCatalog:
    """High-level satellite product catalog backed by SQLite."""

    def __init__(self):
        self.db = get_db()

    def is_product_new(self, product_id: str) -> bool:
        """Check if a product is NOT in the catalog (i.e., not yet downloaded)."""
        return not self.db.acquisition_exists(product_id)

    def needs_download(self, product_id: str) -> bool:
        """Return whether a catalogued product still needs a usable local file."""
        acquisition = self.db.get_acquisition(product_id)
        if acquisition is None or acquisition.get("download_status") != "DOWNLOADED":
            return True

        file_path = acquisition.get("file_path")
        return not file_path or not Path(file_path).is_file()

    def register_product(self, metadata: Dict) -> str:
        """Register a new satellite product. Returns acquisition_id."""
        acq_id = self.db.add_acquisition(**metadata)
        logger.info("Registered product: %s (%s, %s)",
                     acq_id, metadata.get("satellite"), metadata.get("acquisition_date"))
        return acq_id

    def get_unprocessed_products(self, satellite: str) -> List[Dict]:
        """Get downloaded but unprocessed products."""
        return self.db.get_acquisitions_by_status(
            satellite=satellite,
            download_status="DOWNLOADED",
            processing_status="UNPROCESSED",
        )

    def mark_downloaded(self, product_id: str, file_path: str):
        """Mark a product as successfully downloaded."""
        self.db.update_acquisition_status(
            product_id,
            download_status="DOWNLOADED",
            file_path=file_path,
        )
        logger.info("Product marked DOWNLOADED: %s", product_id)

    def mark_download_failed(self, product_id: str, error: str):
        """Mark a download as failed."""
        self.db.update_acquisition_status(
            product_id,
            download_status="FAILED",
            error_message=error,
        )
        logger.warning("Product download FAILED: %s — %s", product_id, error)

    def mark_processed(self, product_id: str):
        """Mark a product as fully processed."""
        self.db.update_acquisition_status(
            product_id,
            processing_status="PROCESSED",
        )
        logger.info("Product marked PROCESSED: %s", product_id)

    def mark_processing_failed(self, product_id: str, error: str):
        """Mark processing as failed."""
        self.db.update_acquisition_status(
            product_id,
            processing_status="FAILED",
            error_message=error,
        )
        logger.warning("Product processing FAILED: %s — %s", product_id, error)

    def get_product_history(
        self, satellite: str, start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """Get product history for a satellite, optionally filtered by date range."""
        db = self.db
        with db.cursor() as cur:
            query = "SELECT * FROM acquisitions WHERE satellite = ?"
            params: list = [satellite]
            if start_date:
                query += " AND acquisition_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND acquisition_date <= ?"
                params.append(end_date)
            query += " ORDER BY acquisition_date DESC"
            rows = cur.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_latest_date(self, satellite: str) -> Optional[str]:
        """Get the most recent acquisition date for a satellite."""
        return self.db.get_latest_acquisition_date(satellite)

    def get_summary(self) -> Dict:
        """Get a summary of all catalogued products."""
        db = self.db
        with db.cursor() as cur:
            summary = {}
            for sat in ["Sentinel-1", "Sentinel-2"]:
                rows = cur.execute(
                    "SELECT download_status, COUNT(*) as cnt "
                    "FROM acquisitions WHERE satellite = ? GROUP BY download_status",
                    (sat,),
                ).fetchall()
                summary[sat] = {r["download_status"]: r["cnt"] for r in rows}
            return summary

    def get_pending_and_failed_acquisitions(self, satellite: Optional[str] = None) -> List[Dict]:
        """Get all acquisitions that are in PENDING or FAILED download status."""
        with self.db.cursor() as cur:
            query = "SELECT * FROM acquisitions WHERE download_status IN ('PENDING', 'FAILED')"
            params: list = []
            if satellite:
                query += " AND satellite = ?"
                params.append(satellite)
            query += " ORDER BY acquisition_date DESC"
            rows = cur.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def reset_failed_to_pending(self, product_id: Optional[str] = None) -> int:
        """Reset failed acquisitions back to PENDING so downloader can retry them."""
        with self.db.cursor() as cur:
            if product_id:
                cur.execute(
                    "UPDATE acquisitions SET download_status = 'PENDING', error_message = NULL WHERE acquisition_id = ? AND download_status = 'FAILED'",
                    (product_id,)
                )
            else:
                cur.execute(
                    "UPDATE acquisitions SET download_status = 'PENDING', error_message = NULL WHERE download_status = 'FAILED'"
                )
            return cur.rowcount

