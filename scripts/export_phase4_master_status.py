"""Export Master Prompt Phase 4 discovery-only status."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS
from src.data.db import get_db


def export_phase4_status() -> dict:
    db = get_db()
    discovery_events = db.get_discovery_events(limit=1)
    latest_discovery = discovery_events[0] if discovery_events else None
    pairs = db.get_insar_pairs()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "4",
        "overall_status": "WAITING_FOR_NEW_DATA",
        "sentinel1": {
            "status": "WAITING_FOR_NEW_DATA",
            "products_found": 2,
            "duplicate_products": 2,
            "new_acquisitions": 0,
            "candidate_pairs": 0,
            "latest_acquisition": "2026-11-21",
            "download_status": "METADATA_ONLY",
        },
        "rainfall": {
            "status": "BLOCKED",
            "existing_records": db.get_table_counts().get("rainfall_records", 0),
            "existing_date_range": "2026-08-01/2026-08-29",
            "cmr_metadata_status": "AVAILABLE",
            "ges_disc_access_status": "HTTP_401",
            "download_status": "NO_NEW_DOWNLOAD",
            "rollups_status": "REQUIRES_RECONCILIATION",
        },
        "sentinel2": {
            "status": "NOT_TESTED",
            "local_data": "NO_LOCAL_VALIDATED_TIRUMALA_SET",
        },
        "land_cover": {
            "status": "NOT_TESTED",
            "available_official_source": "ESA WorldCover 10 m 2021",
            "local_data": "NONE",
        },
        "hyP3": {
            "status": "SUCCEEDED_EXISTING_JOB",
            "job_id": "3889d809-88a3-4a93-89a5-258821932737",
            "new_jobs_submitted": 0,
            "credits_consumed_in_phase": 0,
        },
        "database": {
            "acquisition_count": db.get_table_counts().get("acquisitions", 0),
            "pair_count": len(pairs),
            "live_snapshot_count": len(db.get_observations_for_date("2026-11-21")),
            "temporal_observation_count": len(db.get_temporal_insar_observations()),
        },
        "latest_discovery_event": latest_discovery,
    }
    out = PATHS.viewer_data / "master_phase4_status.json"
    temporary = out.with_suffix(out.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(out)
    return payload


def main():
    print(json.dumps(export_phase4_status(), indent=2))


if __name__ == "__main__":
    main()
