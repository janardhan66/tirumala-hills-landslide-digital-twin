"""Export the unified Master 7-12 emergency sprint status."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.monitoring.final_integration import export_final_status


if __name__ == "__main__":
    print(json.dumps(export_final_status(), indent=2))
