"""
Automated Continuous Monitoring Scheduler Daemon (APScheduler)

Provides robust, laptop-friendly background scheduling using Python APScheduler.
Schedules one end-to-end pipeline trigger at the configured interval.
The pipeline owns discovery and retry work so independent jobs cannot race
each other while writing the same download files.

Windows-friendly:
  - Uses BackgroundScheduler with threading.Event for clean graceful shutdown
  - Avoids POSIX signal dependencies
  - Persists job execution history and consecutive error counters in SQLite
  - Supports CLI commands: start, status, trigger <job_name>, test
"""

import argparse
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import SCHEDULER, setup_logging
from src.data.db import get_db

logger = setup_logging("scheduler")

# Shutdown coordination event
_stop_event = threading.Event()


def job_check_sentinel1():
    db = get_db()
    job_name = "sentinel1_check"
    logger.info("[CRON] Starting Sentinel-1 SAR acquisition search...")
    t0 = time.time()
    try:
        from scripts.download_sentinel1 import Sentinel1Downloader
        downloader = Sentinel1Downloader(dry_run=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last_date = downloader.catalog.get_latest_date("Sentinel-1") or (
            datetime.now().astimezone() - timedelta(days=30)
        ).strftime("%Y-%m-%d")
        res = downloader.run(start_date=last_date, end_date=today)

        db.update_scheduler_state(
            job_name=job_name,
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_success_time=datetime.now(timezone.utc).isoformat(),
            last_data_found_date=downloader.catalog.get_latest_date("Sentinel-1"),
            consecutive_failures=0,
            notes=f"Search success. {res.get('new', 0)} new products found.",
        )
        logger.info("[CRON] Sentinel-1 check completed successfully in %.2fs", time.time() - t0)
    except Exception as e:
        logger.error("[CRON] Sentinel-1 check failed: %s", e)
        db.update_scheduler_state(
            job_name=job_name,
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_failure_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=1,
            notes=f"Failed: {str(e)}",
        )


def job_check_sentinel2():
    db = get_db()
    job_name = "sentinel2_check"
    logger.info("[CRON] Starting Sentinel-2 MSI acquisition search...")
    t0 = time.time()
    try:
        from scripts.download_sentinel2 import Sentinel2Downloader
        downloader = Sentinel2Downloader(dry_run=False)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last_date = downloader.catalog.get_latest_date("Sentinel-2") or (
            datetime.now().astimezone() - timedelta(days=30)
        ).strftime("%Y-%m-%d")
        res = downloader.run(start_date=last_date, end_date=today)

        db.update_scheduler_state(
            job_name=job_name,
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_success_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=0,
            notes=f"S2 search success: {res.get('downloaded', 0)} downloaded.",
        )
        logger.info("[CRON] Sentinel-2 check completed in %.2fs", time.time() - t0)
    except Exception as e:
        logger.error("[CRON] Sentinel-2 check failed: %s", e)
        db.update_scheduler_state(
            job_name=job_name,
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_failure_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=1,
            notes=f"Failed: {str(e)}",
        )


def job_check_rainfall():
    db = get_db()
    job_name = "rainfall_check"
    logger.info("[CRON] Checking NASA GPM IMERG daily rainfall...")
    t0 = time.time()
    try:
        from scripts.download_rainfall import IMERGDownloader
        downloader = IMERGDownloader(dry_run=False)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last_date = downloader.db.get_latest_rainfall_date() or (
            datetime.now().astimezone() - timedelta(days=30)
        ).strftime("%Y-%m-%d")
        res = downloader.run(start_date=last_date, end_date=today)

        db.update_scheduler_state(
            job_name=job_name,
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_success_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=0,
            notes=f"Rainfall check success. {res.get('db_records', 0)} records stored.",
        )
        logger.info("[CRON] Rainfall check completed in %.2fs", time.time() - t0)
    except Exception as e:
        logger.error("[CRON] Rainfall check failed: %s", e)
        db.update_scheduler_state(
            job_name=job_name,
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_failure_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=1,
            notes=f"Failed: {str(e)}",
        )


def job_master_pipeline():
    logger.info("[CRON] Triggering scheduled master processing pipeline...")
    try:
        from automation.pipeline import MasterPipeline
        pipeline = MasterPipeline(dry_run=False)
        res = pipeline.run_all()
        logger.info("[CRON] Master pipeline execution finished. Success: %s", res.success)
    except Exception as e:
        logger.error("[CRON] Scheduled master pipeline failed: %s", e)


def job_retry_downloads():
    """Explicit-download policy: retries are not scheduled automatically."""
    logger.info(
        "[CRON] Automatic download retry sweep is disabled; "
        "manual explicit approval is required."
    )


def job_discovery_check():
    """Conservative CDSE discovery without downloads or HyP3 submission."""
    db = get_db()
    try:
        from src.monitoring.stage5 import run_discovery_dry_run
        result = run_discovery_dry_run(db)
        db.update_scheduler_state(
            job_name="sentinel1_discovery",
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_success_time=datetime.now(timezone.utc).isoformat(),
            last_data_found_date=result.get("latest_acquisition_date"),
            consecutive_failures=0,
            notes=(
                f"{result['status']}: {result['products_found']} found, "
                f"{result['new_acquisitions']} genuinely new."
            ),
        )
    except Exception as exc:
        db.update_scheduler_state(
            job_name="sentinel1_discovery",
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_failure_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=1,
            notes=f"Discovery failed: {str(exc)}",
        )
        logger.error("[CRON] Sentinel-1 discovery check failed: %s", exc)


def job_hyp3_status_check():
    """Poll existing submitted/succeeded HyP3 jobs without submitting new jobs."""
    db = get_db()
    try:
        from scripts.process_insar import HyP3Processor
        processor = HyP3Processor(db=db)
        downloaded = processor.check_and_download("all")
        db.update_scheduler_state(
            job_name="hyp3_status_check",
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_success_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=0,
            notes=f"Polled existing jobs; {len(downloaded)} completed products retrieved.",
        )
    except Exception as exc:
        db.update_scheduler_state(
            job_name="hyp3_status_check",
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_failure_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=1,
            notes=f"HyP3 status check failed: {str(exc)}",
        )
        logger.error("[CRON] HyP3 status check failed: %s", exc)


def job_stage5_status_export():
    """Publish unified database-backed Stage 5 status for dashboard/Cesium."""
    try:
        from src.monitoring.stage5 import export_stage5_status
        payload = export_stage5_status()
        db = get_db()
        db.update_scheduler_state(
            job_name="stage5_status_export",
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_success_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=0,
            notes=f"Unified status exported: {payload['overall_status']}.",
        )
    except Exception as exc:
        db = get_db()
        db.update_scheduler_state(
            job_name="stage5_status_export",
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_failure_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=1,
            notes=f"Status export failed: {str(exc)}",
        )
        logger.error("[CRON] Stage 5 status export failed: %s", exc)


def job_phase5_status_export():
    """Export guarded Master Phase 5 download/preprocessing status."""
    try:
        from src.monitoring.phase5 import export_phase5_status
        payload = export_phase5_status()
        db = get_db()
        db.update_scheduler_state(
            job_name="phase5_status_export",
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_success_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=0,
            notes=f"Phase 5 status exported: {payload['overall_status']}.",
        )
    except Exception as exc:
        db = get_db()
        db.update_scheduler_state(
            job_name="phase5_status_export",
            last_check_time=datetime.now(timezone.utc).isoformat(),
            last_failure_time=datetime.now(timezone.utc).isoformat(),
            consecutive_failures=1,
            notes=f"Phase 5 status export failed: {str(exc)}",
        )
        logger.error("[CRON] Phase 5 status export failed: %s", exc)


def create_scheduler():
    """Initializes and returns an APScheduler BackgroundScheduler instance."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.error("APScheduler is not installed. Please run: pip install apscheduler")
        return None

    interval_hours = SCHEDULER.monitoring_interval_hours
    scheduler = BackgroundScheduler(timezone=SCHEDULER.timezone)

    # One owner performs ingestion and downstream work; the first cycle starts
    # at daemon startup and subsequent cycles follow the configured interval.
    scheduler.add_job(
        job_master_pipeline,
        trigger=IntervalTrigger(hours=interval_hours),
        id="pipeline_trigger",
        name="Master Processing Pipeline Trigger",
        replace_existing=True,
        next_run_time=datetime.now().astimezone(),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        job_discovery_check,
        trigger=IntervalTrigger(hours=SCHEDULER.sentinel1_check_hours),
        id="sentinel1_discovery",
        name="Sentinel-1 Discovery Check",
        replace_existing=True,
        next_run_time=datetime.now().astimezone(),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        job_hyp3_status_check,
        trigger=IntervalTrigger(hours=1),
        id="hyp3_status_check",
        name="HyP3 Status and Product Check",
        replace_existing=True,
        next_run_time=datetime.now().astimezone(),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        job_stage5_status_export,
        trigger=IntervalTrigger(minutes=5),
        id="stage5_status_export",
        name="Unified Stage 5 Status Export",
        replace_existing=True,
        next_run_time=datetime.now().astimezone(),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        job_phase5_status_export,
        trigger=IntervalTrigger(minutes=15),
        id="phase5_status_export",
        name="Master Phase 5 Download and Preprocessing Status Export",
        replace_existing=True,
        next_run_time=datetime.now().astimezone(),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )

    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
    scheduler.add_listener(
        lambda event: _write_scheduler_status(scheduler, running=True),
        EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED,
    )

    return scheduler


def _write_scheduler_status(scheduler, running: bool):
    """Atomically publish scheduler liveness and the next pipeline run."""
    from config.settings import PATHS

    next_run = None
    job = scheduler.get_job("pipeline_trigger") if running else None
    if job is not None and job.next_run_time is not None:
        next_run = job.next_run_time.isoformat()

    status_path = PATHS.logs_dir / "scheduler_status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = status_path.with_suffix(".json.tmp")
    payload = {
        "running": running,
        "pid": os.getpid(),
        "interval_hours": SCHEDULER.monitoring_interval_hours,
        "next_pipeline_run": next_run,
        "updated_at": datetime.now().astimezone().isoformat(),
    }
    with temporary_path.open("w", encoding="utf-8") as status_file:
        json.dump(payload, status_file, indent=2)
    os.replace(temporary_path, status_path)


def run_daemon():
    """Runs the scheduler continuously until KeyboardInterrupt or stop event with single-instance lock."""
    from config.settings import PATHS
    lock_file = PATHS.root / "logs" / "scheduler.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_id = uuid.uuid4().hex

    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            pid = int(lock_data.get("pid", 0))
            import psutil
            if pid > 0 and psutil.pid_exists(pid):
                print(f"\nWARNING: Another scheduler instance is already running (PID: {pid}). Aborting new startup.")
                return
        except (OSError, ValueError, json.JSONDecodeError, ImportError) as exc:
            logger.error("Cannot validate existing scheduler lock %s: %s", lock_file, exc)
            return

        try:
            lock_file.unlink()
        except FileNotFoundError:
            pass

    try:
        lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print("\nWARNING: Another scheduler instance acquired the startup lock. Aborting.")
        return
    with os.fdopen(lock_fd, "w", encoding="utf-8") as lock_handle:
        lock_handle.write(json.dumps({
            "pid": os.getpid(),
            "lock_id": lock_id,
            "started": datetime.now().astimezone().isoformat(),
        }))

    _stop_event.clear()
    scheduler = create_scheduler()
    if scheduler is None:
        _remove_owned_lock(lock_file, lock_id)
        sys.exit(1)

    logger.info("Starting Tirumala Landslide Continuous Monitoring Daemon (APScheduler)...")
    scheduler.start()
    _write_scheduler_status(scheduler, running=True)

    interval_hours = SCHEDULER.monitoring_interval_hours
    print("\n" + "=" * 65)
    print(" TIRUMALA HILLS CONTINUOUS LANDSLIDE MONITORING DAEMON ACTIVE")
    print("=" * 65)
    print(f" Timezone          : {SCHEDULER.timezone}")
    print(f" Monitoring Cycle  : Every {interval_hours} hours")
    print(" Press Ctrl+C to terminate cleanly.\n")

    try:
        while not _stop_event.is_set():
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Termination signal received. Shutting down scheduler gracefully...")
        _stop_event.set()
    finally:
        scheduler.shutdown(wait=False)
        _remove_owned_lock(lock_file, lock_id)
        _write_scheduler_status(scheduler, running=False)
        logger.info("Scheduler daemon stopped.")


def _remove_owned_lock(lock_file: Path, lock_id: str):
    """Remove only the scheduler lock created by this process."""
    try:
        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
        if lock_data.get("lock_id") == lock_id:
            lock_file.unlink()
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not safely remove scheduler lock %s: %s", lock_file, exc)


def show_status():
    db = get_db()
    states = db.get_scheduler_state()
    counts = db.get_table_counts()

    print("\n" + "=" * 60)
    print(" SCHEDULER & PIPELINE MONITORING TELEMETRY")
    print("=" * 60)
    print(f" Database: {db.db_path}")
    print("\n--- DB Table Counts ---")
    for tbl, cnt in counts.items():
        print(f"  {tbl:<25}: {cnt:>6} records")

    print("\n--- Scheduler Registered States ---")
    if not states:
        print("  (No scheduler states recorded yet. Run daemon or manual trigger.)")
    for s in states:
        print(f"  [{s.get('job_name')}]")
        print(f"    Last Check:   {s.get('last_check_time') or 'Never'}")
        print(f"    Last Success: {s.get('last_success_time') or 'Never'}")
        print(f"    Failures:     {s.get('consecutive_failures', 0)}")
        print(f"    Notes:        {s.get('notes') or '-'}")

    latest_run = db.get_latest_pipeline_run()
    if latest_run:
        print("\n--- Latest Pipeline Execution ---")
        print(f"  Run ID:    {latest_run.get('run_id')}")
        print(f"  Started:   {latest_run.get('started')}")
        print(f"  Completed: {latest_run.get('completed')}")
        print(f"  Stages:    {latest_run.get('stages')}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Continuous Landslide Monitoring APScheduler Daemon.")
    parser.add_argument("command", choices=["start", "status", "trigger"], help="Action to execute.")
    parser.add_argument("--job", choices=["sentinel1_check", "sentinel2_check", "rainfall_check", "pipeline"],
                        help="Job name to trigger manually.")
    args = parser.parse_args()

    if args.command == "start":
        run_daemon()
    elif args.command == "status":
        show_status()
    elif args.command == "trigger":
        if args.job == "sentinel1_check":
            job_check_sentinel1()
        elif args.job == "sentinel2_check":
            job_check_sentinel2()
        elif args.job == "rainfall_check":
            job_check_rainfall()
        elif args.job == "pipeline":
            job_master_pipeline()
        else:
            print("Please provide --job to trigger. Available: sentinel1_check, sentinel2_check, rainfall_check, pipeline")


if __name__ == "__main__":
    main()
