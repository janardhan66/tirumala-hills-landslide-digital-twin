import json
import tempfile
from pathlib import Path

from scripts.export_stage4_status import export_stage4_status


def test_stage4_waiting_status_never_invents_a_candidate():
    payload = export_stage4_status(
        discovery_start="2026-10-29",
        discovery_end="2026-11-22",
        discovered_count=2,
        new_acquisition_count=0,
        candidate_pair_count=0,
    )
    assert payload["overall_status"] == "WAITING_FOR_NEW_DATA"
    assert payload["discovery"]["duplicate_acquisition_count"] == 2
    assert payload["discovery"]["candidate_pair_count"] == 0
    assert payload["new_stage4_pair_count"] == 0
    assert payload["new_job_submitted"] is False
    assert payload["real_sbas_ready"] is False
    assert payload["reference_consistency"] == "NOT_ESTABLISHED_ACROSS_PAIRS"
