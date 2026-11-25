"""Generate the unified Stage 5 monitoring and Cesium status JSON."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.monitoring.stage5 import run_discovery_dry_run, export_stage5_status


def main():
    parser = argparse.ArgumentParser(
        description="Run a conservative discovery check and export Stage 5 status."
    )
    parser.add_argument(
        "--discovery",
        action="store_true",
        help="Perform a live CDSE metadata discovery; no download or HyP3 submission.",
    )
    args = parser.parse_args()

    discovery = None
    if args.discovery:
        discovery = run_discovery_dry_run()
    status = export_stage5_status()
    if discovery is not None:
        status["discovery"]["live_check"] = discovery
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
