"""Export guarded Stage 3 temporal status for Cesium and the dashboard."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.db import get_db
from src.analysis.temporal_insar import build_interferogram_network
from config.settings import PATHS


def export_stage3_temporal(db=None) -> dict:
    db = db or get_db()
    pairs = db.get_insar_pairs()
    network = build_interferogram_network(pairs)
    temporal_observations = db.get_temporal_insar_observations()
    valid_count = sum(
        1 for row in temporal_observations
        if row["quality_status"] == "VALID"
        and row["los_displacement_m"] is not None
    )
    insufficient_count = len(temporal_observations) - valid_count

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "study_area": "Tirumala Hills",
        "node_count": len(network["nodes"]),
        "edge_count": len(network["edges"]),
        "valid_edge_count": len(network["valid_edges"]),
        "connected_components": network["connected_components"],
        "component_sizes": network["component_sizes"],
        "temporal_observation_count": len(temporal_observations),
        "valid_observation_count": valid_count,
        "insufficient_observation_count": insufficient_count,
        "time_series_status": (
            "INSUFFICIENT_DATA"
            if len(network["valid_edges"]) < 2
            else "READY_FOR_INVESTIGATION"
        ),
        "velocity_status": "NOT_RELIABLE_WITH_SINGLE_PAIR",
        "reference_convention": (
            "LOS displacement is relative to each pair's own phase reference "
            "and is not vertical displacement."
        ),
        "pair_status": [
            {
                "pair_id": pair["pair_id"],
                "reference_date": pair["reference_date"],
                "secondary_date": pair["secondary_date"],
                "processing_status": pair["processing_status"],
                "quality_status": pair.get("quality_status"),
                "valid_pixels": pair.get("valid_pixels"),
                "mean_coherence": pair.get("mean_coherence"),
            }
            for pair in pairs
        ],
        "synthetic_disclaimer": (
            "Synthetic values may test the inversion only and are never "
            "written as Tirumala observations."
        ),
    }

    output = PATHS.viewer_data / "stage3_temporal_status.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(output)
    return payload


def main():
    print(json.dumps(export_stage3_temporal(), indent=2))


if __name__ == "__main__":
    main()
