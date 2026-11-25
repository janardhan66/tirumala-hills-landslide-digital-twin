"""Stage 1 dry-run tool for acquisition and pair management."""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import STUDY_AREA
from scripts.download_sentinel1 import Sentinel1Downloader
from src.data.db import get_db
from src.data.multi_temporal import PairManager


def main():
    parser = argparse.ArgumentParser(
        description="Discover acquisitions and propose pairs without downloading or submitting jobs."
    )
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--register-discovered", action="store_true")
    parser.add_argument("--select-pairs", action="store_true")
    parser.add_argument("--maximum-pairs", type=int, default=1)
    args = parser.parse_args()

    end_date = args.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = args.start_date or (
        datetime.now(timezone.utc) - timedelta(days=24)
    ).strftime("%Y-%m-%d")

    db = get_db()
    downloader = Sentinel1Downloader(dry_run=not args.register_discovered)
    products = downloader.search_products(start_date, end_date)
    discovered = [downloader._parse_product(product) for product in products]

    new_acquisitions = []
    if args.register_discovered:
        for acquisition in discovered:
            if not db.acquisition_exists(acquisition["acquisition_id"]):
                db.add_acquisition(**acquisition)
                new_acquisitions.append(acquisition["acquisition_id"])
    else:
        new_acquisitions = [
            acquisition["acquisition_id"]
            for acquisition in discovered
            if not db.acquisition_exists(acquisition["acquisition_id"])
        ]

    result = {
        "start_date": start_date,
        "end_date": end_date,
        "discovered_count": len(discovered),
        "new_acquisition_ids": new_acquisitions,
        "duplicates_skipped": len(discovered) - len(new_acquisitions),
        "pair_candidates": [],
        "hyP3_submissions": 0,
    }

    if args.select_pairs:
        with db.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM acquisitions "
                "WHERE satellite = 'Sentinel-1' "
                "ORDER BY acquisition_date, start_time"
            ).fetchall()
        acquisitions = [dict(row) for row in rows]
        manager = PairManager(db)
        candidates = manager.select_next_connected_pairs(
            acquisitions,
            STUDY_AREA.wkt_polygon,
            maximum_pairs=args.maximum_pairs,
        )
        result["pair_candidates"] = [
            {
                "pair_id": candidate.pair_id,
                "reference_acquisition_id": candidate.reference_acquisition_id,
                "secondary_acquisition_id": candidate.secondary_acquisition_id,
                "temporal_baseline_days": candidate.temporal_baseline_days,
                "relative_orbit": candidate.relative_orbit,
                "orbit_direction": candidate.orbit_direction,
                "spatial_overlap_percent": candidate.spatial_overlap_percent,
                "selection_reason": candidate.selection_reason,
                "registered": (
                    bool(
                        args.register_discovered
                        and manager.register_selected_pair(candidate, "CANDIDATE")
                    )
                ),
            }
            for candidate in candidates
        ]

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
