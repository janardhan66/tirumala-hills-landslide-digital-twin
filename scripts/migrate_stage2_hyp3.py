"""Stage 2 backup and HyP3 status-registration migration."""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import CREDENTIALS
from src.data.db import DatabaseManager


def create_backup(database_path: Path) -> Path:
    database_path = database_path.resolve()
    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"{database_path.stem}_stage2_{stamp}.db"
    shutil.copy2(database_path, backup)
    for suffix in ("-wal", "-shm"):
        source = Path(str(database_path) + suffix)
        if source.exists():
            shutil.copy2(source, Path(str(backup) + suffix))
    return backup


def migrate(database_path: Path) -> dict:
    db = DatabaseManager(database_path)
    pair_id = "PAIR_20261109_20261121"
    pair = next(
        (item for item in db.get_insar_pairs() if item["pair_id"] == pair_id),
        None,
    )
    result = {
        "existing_pair_preserved": pair is not None,
        "existing_pair_status": pair["processing_status"] if pair else None,
        "live_job_status": None,
        "job_status_history_count": 0,
    }

    if pair and pair.get("hyp3_job_id"):
        db.update_insar_pair(
            pair_id,
            submitted_at="2026-11-22T06:06:42+00:00",
            expected_credit_cost=10,
            job_config_json=json.dumps({
                "job_type": "INSAR_GAMMA",
                "looks": "20x4",
                "include_dem": True,
                "include_inc_map": True,
                "include_displacement_maps": True,
                "phase_filter_parameter": 0.6,
            }, sort_keys=True),
        )
        if CREDENTIALS.earthdata_username and CREDENTIALS.earthdata_password:
            try:
                import hyp3_sdk

                hyp3 = hyp3_sdk.HyP3(
                    username=CREDENTIALS.earthdata_username,
                    password=CREDENTIALS.earthdata_password,
                )
                job = hyp3.get_job_by_id(pair["hyp3_job_id"])
                status = str(job.status_code)
                result["live_job_status"] = status
                history = db.get_hyp3_status_history(pair["hyp3_job_id"])
                if not history or history[-1].get("status") != status:
                    db.record_hyp3_status(
                        pair_id,
                        pair["hyp3_job_id"],
                        status,
                        payload={
                            "job_id": getattr(job, "job_id", pair["hyp3_job_id"]),
                            "status_code": status,
                            "request_time": str(getattr(job, "request_time", "")),
                            "job_type": getattr(job, "job_type", None),
                        },
                    )
                output_archive = pair.get("los_disp_tif") and pair.get("coherence_tif")
                if status == "SUCCEEDED" and output_archive:
                    db.update_insar_pair(
                        pair_id,
                        processing_status="PROCESSED",
                        quality_status="PROCESSED",
                        output_validation_status="VALID",
                        output_archive="S1DD_20261109T003100_20261121T003100_VVR012_INT80_G_ueF_FD61.zip",
                    )
            except Exception as exc:
                result["live_job_status"] = f"BLOCKED: {exc}"

    result["job_status_history_count"] = len(
        db.get_hyp3_status_history(
            pair["hyp3_job_id"] if pair and pair.get("hyp3_job_id") else None
        )
    )
    db.close()
    return result


def main():
    database = Path(__file__).resolve().parents[1] / "database" / "monitoring.db"
    backup = create_backup(database)
    result = migrate(database)
    result["backup"] = str(backup)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
