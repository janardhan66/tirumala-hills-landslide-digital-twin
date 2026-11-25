"""Restart-safe Stage 2 HyP3 status and product retrieval monitor."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.process_insar import HyP3Processor, process_new_insar_pairs
from src.data.db import get_db


def run_monitor(pair_id: str = "all") -> dict:
    db = get_db()
    processor = HyP3Processor(db=db)
    downloaded = processor.check_and_download(pair_id)
    processed = []
    for pair in db.get_insar_pairs():
        if pair_id != "all" and pair["pair_id"] != pair_id:
            continue
        if pair["processing_status"] not in {"DOWNLOADED", "PROCESSED"}:
            continue
        result = processor.process_downloaded_products(pair["pair_id"])
        processed.append({"pair_id": pair["pair_id"], **result})
    return {
        "downloaded_files": [str(path) for path in downloaded],
        "processed_pairs": processed,
        "active_history": db.get_hyp3_status_history(),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Poll existing HyP3 jobs and retrieve completed products; never submits jobs."
    )
    parser.add_argument("--pair-id", default="all")
    args = parser.parse_args()
    print(json.dumps(run_monitor(args.pair_id), indent=2))


if __name__ == "__main__":
    main()
