"""Stage 3 backup and temporal-observation migration."""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.populate_stage3_temporal import populate_processed_pairs
from src.data.db import DatabaseManager, get_db


def create_backup(database_path: Path) -> Path:
    database_path = database_path.resolve()
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"{database_path.stem}_stage3_{stamp}.db"
    shutil.copy2(database_path, backup)
    for suffix in ("-wal", "-shm"):
        source = Path(str(database_path) + suffix)
        if source.exists():
            shutil.copy2(source, Path(str(backup) + suffix))
    return backup


def main():
    database = Path(__file__).resolve().parents[1] / "database" / "monitoring.db"
    backup = create_backup(database)
    db = get_db()
    result = populate_processed_pairs(db)
    pair_count = len(db.get_insar_pairs(status="PROCESSED"))
    temporal_count = len(db.get_temporal_insar_observations())
    db.close()
    print(json.dumps({
        "backup": str(backup),
        "processed_pair_count": pair_count,
        "temporal_observation_count": temporal_count,
        **result,
    }, indent=2))


if __name__ == "__main__":
    main()
