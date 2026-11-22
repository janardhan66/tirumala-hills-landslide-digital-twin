"""
Export Cesium 3D Digital Twin Assets

Exports spatial_grid_lookup.json, temporal_registry.json, active_alerts.geojson,
and sync_status.json for live synchronization of the CesiumJS 3D viewer.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS, setup_logging
from src.data.db import get_db
from scripts.update_database import export_cesium_lookups

logger = setup_logging("export_cesium_data")


def export_all_cesium_data():
    db = get_db()
    export_cesium_lookups(db)
    logger.info("Cesium 3D Digital Twin data successfully refreshed.")


if __name__ == "__main__":
    export_all_cesium_data()
