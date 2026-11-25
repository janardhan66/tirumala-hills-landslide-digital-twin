"""Export database-backed Master Phase 5 status for dashboard and Cesium."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.monitoring.phase5 import export_phase5_status


if __name__ == "__main__":
    payload = export_phase5_status()
    print(json.dumps(payload, indent=2))
