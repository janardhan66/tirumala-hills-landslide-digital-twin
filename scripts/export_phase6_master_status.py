"""Export guarded Master Phase 6 InSAR and temporal-network status."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.monitoring.phase6 import export_phase6_status


if __name__ == "__main__":
    print(json.dumps(export_phase6_status(), indent=2))
