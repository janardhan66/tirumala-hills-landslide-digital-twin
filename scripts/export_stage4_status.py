"""Export Stage 4 real-acquisition and network-readiness status."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS
from src.analysis.temporal_insar import build_interferogram_network
from src.data.db import get_db


def export_stage4_status(
    discovery_start: str,
    discovery_end: str,
    discovered_count: int,
    new_acquisition_count: int,
    candidate_pair_count: int,
) -> dict:
    db = get_db()
    pairs = db.get_insar_pairs()
    network = build_interferogram_network(pairs)
    temporal = db.get_temporal_insar_observations()
    valid_temporal = sum(
        1 for row in temporal
        if row["quality_status"] == "VALID"
        and row["los_displacement_m"] is not None
    )

    with db.cursor() as cur:
        latest_discovered = cur.execute(
            "SELECT MAX(acquisition_date) FROM acquisitions "
            "WHERE satellite='Sentinel-1'"
        ).fetchone()[0]
        latest_processed = cur.execute(
            "SELECT MAX(secondary_date) FROM insar_pairs "
            "WHERE processing_status='PROCESSED'"
        ).fetchone()[0]
        completed_jobs = cur.execute(
            "SELECT COUNT(*) FROM hyp3_job_status_history "
            "WHERE status='SUCCEEDED'"
        ).fetchone()[0]
        failed_jobs = cur.execute(
            "SELECT COUNT(*) FROM hyp3_job_status_history "
            "WHERE status='FAILED'"
        ).fetchone()[0]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": "4",
        "overall_status": (
            "WAITING_FOR_NEW_DATA"
            if candidate_pair_count == 0
            else "PARTIAL"
        ),
        "discovery": {
            "start_date": discovery_start,
            "end_date": discovery_end,
            "discovered_count": discovered_count,
            "new_acquisition_count": new_acquisition_count,
            "duplicate_acquisition_count": discovered_count - new_acquisition_count,
            "candidate_pair_count": candidate_pair_count,
        },
        "latest_discovered_acquisition": latest_discovered,
        "latest_processed_acquisition": latest_processed,
        "new_stage4_pair_count": 0,
        "completed_hyp3_jobs": completed_jobs,
        "failed_hyp3_jobs": failed_jobs,
        "network": {
            "node_count": len(network["nodes"]),
            "edge_count": len(network["edges"]),
            "valid_edge_count": len(network["valid_edges"]),
            "connected_components": network["connected_components"],
            "component_sizes": network["component_sizes"],
        },
        "temporal_observations": len(temporal),
        "valid_temporal_observations": valid_temporal,
        "real_sbas_ready": len(network["valid_edges"]) >= 2,
        "reference_consistency": "NOT_ESTABLISHED_ACROSS_PAIRS",
        "cumulative_displacement_status": "INSUFFICIENT_DATA",
        "velocity_status": "NOT_RELIABLE_WITH_SINGLE_VALID_PAIR",
        "new_job_submitted": False,
    }

    out = PATHS.viewer_data / "stage4_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(out.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(out)
    return payload


def main():
    parser = argparse.ArgumentParser(
        description="Export verified Stage 4 acquisition and network status."
    )
    parser.add_argument("--discovery-start", required=True)
    parser.add_argument("--discovery-end", required=True)
    parser.add_argument("--discovered-count", type=int, required=True)
    parser.add_argument("--new-acquisition-count", type=int, required=True)
    parser.add_argument("--candidate-pair-count", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(export_stage4_status(
        args.discovery_start,
        args.discovery_end,
        args.discovered_count,
        args.new_acquisition_count,
        args.candidate_pair_count,
    ), indent=2))


if __name__ == "__main__":
    main()
