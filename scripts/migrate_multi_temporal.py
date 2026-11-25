"""Safe Stage 1 SQLite migration and existing-pair verification."""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.db import DatabaseManager


def create_backup(database_path: Path) -> Path:
    database_path = database_path.resolve()
    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{database_path.stem}_{timestamp}.db"
    shutil.copy2(database_path, backup_path)
    for suffix in ("-wal", "-shm"):
        source = Path(str(database_path) + suffix)
        if source.exists():
            shutil.copy2(source, Path(str(backup_path) + suffix))
    return backup_path


def migrate(database_path: Path) -> dict:
    db = DatabaseManager(database_path)
    pair_id = "PAIR_20261109_20261121"
    pair = next(
        (item for item in db.get_insar_pairs() if item["pair_id"] == pair_id),
        None,
    )
    if pair is not None:
        reference = db.get_acquisition(pair["reference_acq_id"])
        secondary = db.get_acquisition(pair["secondary_acq_id"])
        overlap = None
        if reference and secondary:
            from config.settings import STUDY_AREA
            from src.data.multi_temporal import spatial_overlap_percent
            overlap = spatial_overlap_percent(
                reference,
                secondary,
                STUDY_AREA.wkt_polygon,
            )
        db.update_insar_pair(
            pair_id,
            orbit_direction="DESCENDING",
            relative_orbit=92,
            orbit_compatibility="VERIFIED",
            spatial_overlap_percent=overlap,
            quality_status="PROCESSED",
            selection_method="Existing verified live pair; preserve unchanged.",
        )

    for acq_id in (
        "220f79ba-248d-4e02-81ad-1f9f10d202ed",
        "b69aeace-3306-4e9b-94f3-a6d643296386",
    ):
        acquisition = db.get_acquisition(acq_id)
        if acquisition:
            db.update_acquisition_status(
                acq_id,
                acquisition_timestamp=acquisition.get("start_time"),
                beam_mode=acquisition.get("sensor_mode"),
                spatial_coverage=acquisition.get("footprint_wkt"),
            )

    snapshot_count = db.get_table_counts().get("observation_snapshots", 0)
    result = {
        "pair_id": pair_id,
        "pair_preserved": pair is not None,
        "observation_snapshot_count": snapshot_count,
        "pair_status": pair["processing_status"] if pair else None,
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Stage 1 multi-temporal SQLite migration.")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "database" / "monitoring.db",
    )
    args = parser.parse_args()
    backup = create_backup(args.database)
    result = migrate(args.database)
    result["backup"] = str(backup)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
