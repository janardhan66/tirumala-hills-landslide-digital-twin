"""
Master Processing Pipeline Orchestrator

Executes the automated end-to-end landslide monitoring lifecycle:
  Stage 1: Satellite Data Discovery & Download Check (Sentinel-1 & Sentinel-2)
  Stage 2: Rainfall Data Ingestion (NASA GPM IMERG)
  Stage 3: Data Preprocessing & Grid Alignment (EPSG:32644, 80m)
  Stage 4: InSAR Processing & Coherence Quality Screening
  Stage 5: Terrain & Spatial Feature Extraction
  Stage 6: PyTorch 14-Channel U-Net Segmentation (with Tirumala Adapter)
  Stage 7: Evidence-Based Multi-Criteria Risk Assessment
  Stage 8: Multi-Temporal Historical Comparison
  Stage 9: Database & Audit Trail Synchronization
  Stage 10: 3D CesiumJS Digital Twin Asset Refresh
  Stage 11: Intelligent Decision-Support Alert Evaluation & Logging

Provides CLI flags:
  --stage <name> : Run a specific single stage
  --dry-run      : Preview operations without mutating persistent state
  --force        : Run pipeline regardless of whether new satellite data was acquired
"""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS, setup_logging
from src.data.db import get_db

logger = setup_logging("pipeline")


class PipelineResult:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.completed_at = None
        self.stages = {}
        self.success = True
        self.alerts_generated = 0

    def add_stage(self, name: str, status: str, duration: float, records: int = 0, message: str = "", error: str = ""):
        self.stages[name] = {
            "status": status,
            "duration_seconds": round(duration, 2),
            "records_processed": records,
            "message": message,
            "error": error,
        }
        if status not in {"SUCCESS", "SKIPPED"}:
            self.success = False

    def finish(self):
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "success": self.success,
            "alerts_generated": self.alerts_generated,
            "stages": self.stages,
        }


class MasterPipeline:
    def __init__(self, dry_run: bool = False, force: bool = False):
        self.dry_run = dry_run
        self.force = force
        self.db = None if dry_run else get_db()
        self.run_id = f"RUN_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.observation_date: Optional[str] = None

    def _write_status(self, stage_name: str, status: str, message: str = ""):
        status_path = PATHS.logs_dir / "pipeline_status.json"
        temporary_path = status_path.with_suffix(".json.tmp")
        payload = {
            "run_id": self.run_id,
            "stage": stage_name,
            "status": status,
            "message": message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            status_path.parent.mkdir(parents=True, exist_ok=True)
            with temporary_path.open("w", encoding="utf-8") as status_file:
                json.dump(payload, status_file, indent=2)
            os.replace(temporary_path, status_path)
        except OSError:
            logger.exception("Could not publish current pipeline status.")

    def _execute_stage(self, stage_name: str, func, *args, **kwargs) -> Dict:
        t0 = time.time()
        if self.dry_run:
            duration = time.time() - t0
            message = "Dry run: stage skipped; no work or persistent state changed."
            logger.info("<<< [STAGE SKIPPED] %s: %s", stage_name, message)
            return {
                "status": "SKIPPED",
                "duration": duration,
                "count": 0,
                "message": message,
                "error": "",
            }

        logger.info(">>> [STAGE START] %s", stage_name)
        self._write_status(stage_name, "RUNNING")
        try:
            status, count, msg = func(*args, **kwargs)
            duration = time.time() - t0
            self._write_status(stage_name, status, msg)
            self.db.log_pipeline_stage(
                run_id=self.run_id,
                stage_name=stage_name,
                status=status,
                duration_seconds=duration,
                records_processed=count,
                message=msg,
            )
            logger.info("<<< [STAGE END] %s: %s (%.2fs) - %s", stage_name, status, duration, msg)
            return {"status": status, "duration": duration, "count": count, "message": msg, "error": ""}
        except Exception as exc:
            duration = time.time() - t0
            err_msg = str(exc)
            self._write_status(stage_name, "ERROR", err_msg)
            logger.error("<<< [STAGE FAILED] %s: %s", stage_name, err_msg, exc_info=True)
            self.db.log_pipeline_stage(
                run_id=self.run_id,
                stage_name=stage_name,
                status="ERROR",
                duration_seconds=duration,
                records_processed=0,
                message=f"Exception: {err_msg}",
                error_traceback=err_msg,
            )
            return {"status": "ERROR", "duration": duration, "count": 0, "message": "", "error": err_msg}

    # -------------------------------------------------------------
    # STAGE DEFINITIONS
    # -------------------------------------------------------------
    def stage_check_satellite(self):
        """Stage 1: Check Copernicus Data Space for new Sentinel-1 and Sentinel-2 acquisitions."""
        if self.dry_run:
            return "SUCCESS", 0, "Dry run: satellite search bypassed."

        from scripts.download_sentinel1 import Sentinel1Downloader
        from scripts.download_sentinel2 import Sentinel2Downloader

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Sentinel-1 Search
        s1_downloader = Sentinel1Downloader(dry_run=False)
        s1_start = s1_downloader.catalog.get_latest_date("Sentinel-1") or (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).strftime("%Y-%m-%d")
        s1_res = s1_downloader.run(start_date=s1_start, end_date=today)

        # Sentinel-2 Search
        s2_downloader = Sentinel2Downloader(dry_run=False)
        s2_start = s2_downloader.catalog.get_latest_date("Sentinel-2") or (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).strftime("%Y-%m-%d")
        s2_res = s2_downloader.run(start_date=s2_start, end_date=today)

        total_searched = s1_res.get("searched", 0) + s2_res.get("searched", 0)
        total_new = s1_res.get("new", 0) + s2_res.get("new", 0)
        total_dl = s1_res.get("downloaded", 0) + s2_res.get("downloaded", 0)
        total_failed = s1_res.get("failed", 0) + s2_res.get("failed", 0)

        msg = (
            f"Satellite check: {total_searched} searched (S1: {s1_res.get('searched',0)}, S2: {s2_res.get('searched',0)}), "
            f"{total_new} new registered, {total_dl} downloaded, {total_failed} pending/failed auth."
        )
        return ("WARNING" if total_failed else "SUCCESS"), total_dl, msg

    def stage_ingest_rainfall(self):
        """Stage 2: Poll NASA GPM IMERG daily precipitation."""
        if self.dry_run:
            return "SUCCESS", 0, "Dry run: rainfall polling bypassed."

        from scripts.download_rainfall import IMERGDownloader
        downloader = IMERGDownloader(dry_run=False)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        latest_date = downloader.db.get_latest_rainfall_date() or (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).strftime("%Y-%m-%d")
        res = downloader.run(start_date=latest_date, end_date=today)

        if res.get("status") == "BLOCKED_NO_CREDENTIALS":
            return "WARNING", 0, res.get("message", "NASA Earthdata credentials unconfigured; using existing rainfall.")

        return "SUCCESS", res.get("db_records", 0), f"Rainfall check complete: {res.get('db_records',0)} daily records ingested."

    def stage_data_preprocessing(self):
        """Stage 3: Preprocess and align newly acquired satellite data to Tirumala 80m grid."""
        if self.dry_run:
            return "SUCCESS", 0, "Dry run: preprocessing bypassed."

        from scripts.preprocess_data import preprocess_new_acquisitions
        res = preprocess_new_acquisitions(self.db)
        status = "WARNING" if res.get("errors") else "SUCCESS"
        return status, res.get("preprocessed", 0), res.get("message", "Preprocessing complete.")

    def stage_insar_processing(self):
        """Stage 4: Evaluate InSAR processing for Sentinel-1 pairs (SNAP or HyP3)."""
        if self.dry_run:
            return "SUCCESS", 0, "Dry run: InSAR processing bypassed."

        from scripts.process_insar import process_new_insar_pairs
        res = process_new_insar_pairs(self.db)
        status = "SUCCESS" if res.get("status") == "UP_TO_DATE" else "WARNING"
        return status, res.get("pairs_processed", 0), res.get("message", "InSAR stage complete.")

    def stage_feature_extraction(self):
        """Stage 5: Extract spatial features from DEM, slope, and InSAR rasters."""
        from scripts.extract_features import extract_all_features
        self.observation_date = self.db.get_latest_processed_insar_date()
        if self.observation_date is None:
            return "WARNING", 0, "No processed InSAR pair date; refusing to label static rasters as current."
        summary = extract_all_features(observation_date=self.observation_date)
        if summary.get("errors"):
            return "WARNING", summary.get("cells_processed", 0), f"Feature extraction: {summary['errors']}"
        return "SUCCESS", summary.get("cells_processed", 0), f"Extracted features for {summary['cells_processed']} cells."

    def stage_run_unet(self):
        """Stage 6: Execute 14-Channel U-Net inference across Tirumala patches."""
        import numpy as np

        from scripts.run_unet import load_unet_model, run_inference, stitch_predictions, save_prediction_geotiff
        from src.models.tirumala_patch_builder import TirumalaPatchBuilder

        builder = TirumalaPatchBuilder(stride=64)
        if not builder.prepare(allow_incomplete=False):
            return "WARNING", 0, (
                "U-Net inference skipped: complete, aligned Sentinel-2 L2A bands "
                "B01-B12 are required; incomplete optical channels are not substituted."
            )

        patches = builder.extract_patches()
        if not patches:
            return "WARNING", 0, "No patches created."

        model = load_unet_model()
        if model is None:
            return "WARNING", 0, "U-Net checkpoint missing or unloadable."

        results = run_inference(model, patches, threshold=0.50, batch_size=2)
        H, W = builder._dem_data.shape
        pred, conf, _ = stitch_predictions(results, (H, W))

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        save_prediction_geotiff(pred, conf, str(PATHS.dem_tif), str(PATHS.outputs_dir / "unet_predictions"), today)
        pos_fraction = float(np.mean(pred))

        return "SUCCESS", len(patches), f"U-Net inference finished across {len(patches)} patches. Pos ratio: {pos_fraction:.3f}"

    def stage_risk_assessment(self):
        """Stage 7 & 8: Calculate composite evidence risk and compare with historical baseline."""
        import pandas as pd
        from src.features.risk_engine import run_risk_assessment, save_risk_to_database

        if not PATHS.spatial_evidence_csv.exists():
            return "WARNING", 0, "No spatial evidence CSV to assess."

        df = pd.read_csv(PATHS.spatial_evidence_csv)
        observation_date = self.observation_date
        if observation_date is None:
            observation_date = self.db.get_latest_processed_insar_date()
            if observation_date is None:
                return "WARNING", 0, "No processed observation date is available for risk assessment."
            self.observation_date = observation_date

        prior_dates = [
            date for date in self.db.get_observation_dates()
            if date < observation_date
        ]
        historical_observations = [
            pd.DataFrame(self.db.get_observations_for_date(date))
            for date in prior_dates[-1:]
        ]
        previous_data = historical_observations[-1] if historical_observations else None
        result = run_risk_assessment(
            current_data=df,
            observation_date=observation_date,
            previous_data=previous_data,
            historical_observations=historical_observations,
        )
        save_risk_to_database(result, self.db)
        return "SUCCESS", result.total_cells, (
            f"Risk scoring completed: {result.total_cells} cells. Low: {result.low_count}, "
            f"Med: {result.medium_count}, High: {result.high_count}."
        )

    def stage_refresh_viewer(self):
        """Refresh terrain layers before publishing the latest Cesium sync marker."""
        from src.digital_twin.layer_exporter import export_all_gis_layers
        from scripts.update_database import export_cesium_lookups

        export_all_gis_layers(PATHS.root, PATHS.viewer_cesium, db=self.db)
        export_cesium_lookups(self.db)
        return "SUCCESS", 1, "Exported the terrain layer manifest and latest Cesium lookup/sync data."

    def stage_evaluate_alerts(self):
        """Stage 10: Evaluate decision-support alert conditions."""
        import pandas as pd
        from src.agent.alert_engine import AlertRulesEngine, save_alerts_to_db

        if not PATHS.spatial_evidence_csv.exists():
            return "WARNING", 0, "No spatial evidence CSV available for alerts."

        df = pd.read_csv(PATHS.spatial_evidence_csv)
        observation_date = self.observation_date
        if observation_date is None:
            observation_date = self.db.get_latest_processed_insar_date()
            if observation_date is None:
                return "WARNING", 0, "No processed observation date is available for alert evaluation."
            self.observation_date = observation_date

        rainfall_records = self.db.get_rainfall_range("0001-01-01", observation_date)
        latest_rain = rainfall_records[-1]["record_date"] if rainfall_records else None
        rain_3d = None
        if latest_rain:
            rec = self.db.get_rainfall_range(latest_rain, latest_rain)
            if rec:
                rain_3d = rec[0]["rolling_3day_mm"]

        engine = AlertRulesEngine()
        alerts = engine.evaluate_all_rules(
            df,
            rainfall_3day_mm=rain_3d,
            observation_date=observation_date,
        )
        save_alerts_to_db(alerts)
        return "SUCCESS", len(alerts), f"Alerts evaluation: {len(alerts)} alerts generated."

    # -------------------------------------------------------------
    # ORCHESTRATION RUNNER (WITH CONCURRENCY LOCK)
    # -------------------------------------------------------------
    def run_all(self) -> PipelineResult:
        lock_file = PATHS.root / "logs" / "pipeline.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        # Check for an existing run, then create the lock exclusively to close
        # the check/write race between the scheduler and manual invocations.
        if lock_file.exists():
            try:
                lock_text = lock_file.read_text(encoding="utf-8").strip()
                lock_data = json.loads(lock_text)
                lock_pid = lock_data.get("pid")
                lock_time = lock_data.get("time", "")

                # Check if process is still active
                import psutil
                if lock_pid and psutil.pid_exists(lock_pid):
                    logger.warning("Another pipeline run is currently in progress (PID: %s, started: %s). Aborting.", lock_pid, lock_time)
                    res = PipelineResult(self.run_id)
                    res.success = False
                    res.add_stage("concurrency_check", "ABORTED", 0.0, 0, f"Overlapping run blocked by active PID {lock_pid}")
                    res.finish()
                    return res
                else:
                    logger.info("Found stale lock from inactive PID %s; breaking lock and proceeding.", lock_pid)
            except (OSError, ValueError, json.JSONDecodeError):
                logger.info("Breaking unreadable pipeline lock and proceeding.")

            try:
                lock_file.unlink()
            except FileNotFoundError:
                pass

        # Acquire the lock atomically. A competing run may have created it
        # since the stale-lock check above.
        try:
            lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            res = PipelineResult(self.run_id)
            res.success = False
            res.add_stage("concurrency_check", "ABORTED", 0.0, 0, "Another pipeline run acquired the lock.")
            res.finish()
            return res
        with os.fdopen(lock_fd, "w", encoding="utf-8") as lock_handle:
            lock_handle.write(json.dumps({
                "pid": os.getpid(),
                "run_id": self.run_id,
                "time": datetime.now(timezone.utc).isoformat(),
            }))

        try:
            logger.info("============================================================")
            logger.info("STARTING MASTER PIPELINE RUN: %s", self.run_id)
            logger.info("============================================================")
            result = PipelineResult(self.run_id)

            # 1. Satellite Check (Sentinel-1 & Sentinel-2)
            s1 = self._execute_stage("satellite_check", self.stage_check_satellite)
            result.add_stage("satellite_check", s1["status"], s1["duration"], s1["count"], s1["message"], s1["error"])

            # 2. Rainfall Ingestion (NASA GPM IMERG)
            s2 = self._execute_stage("rainfall_ingest", self.stage_ingest_rainfall)
            result.add_stage("rainfall_ingest", s2["status"], s2["duration"], s2["count"], s2["message"], s2["error"])

            # 3. Data Preprocessing & Alignment
            s3 = self._execute_stage("data_preprocessing", self.stage_data_preprocessing)
            result.add_stage("data_preprocessing", s3["status"], s3["duration"], s3["count"], s3["message"], s3["error"])

            # 4. InSAR Processing & Coherence Quality Screening
            s4 = self._execute_stage("insar_processing", self.stage_insar_processing)
            result.add_stage("insar_processing", s4["status"], s4["duration"], s4["count"], s4["message"], s4["error"])

            # 5. Spatial Feature Extraction
            s5 = self._execute_stage("feature_extraction", self.stage_feature_extraction)
            result.add_stage("feature_extraction", s5["status"], s5["duration"], s5["count"], s5["message"], s5["error"])

            # 6. PyTorch 14-Channel U-Net Inference
            s6 = self._execute_stage("unet_inference", self.stage_run_unet)
            result.add_stage("unet_inference", s6["status"], s6["duration"], s6["count"], s6["message"], s6["error"])

            # 7. Evidence-Based Multi-Criteria Risk Assessment
            s7 = self._execute_stage("risk_assessment", self.stage_risk_assessment)
            result.add_stage("risk_assessment", s7["status"], s7["duration"], s7["count"], s7["message"], s7["error"])

            # 8. 3D CesiumJS Digital Twin Asset Refresh
            s8 = self._execute_stage("refresh_viewer", self.stage_refresh_viewer)
            result.add_stage("refresh_viewer", s8["status"], s8["duration"], s8["count"], s8["message"], s8["error"])

            # 9. Intelligent Decision-Support Alert Evaluation
            s9 = self._execute_stage("evaluate_alerts", self.stage_evaluate_alerts)
            result.add_stage("evaluate_alerts", s9["status"], s9["duration"], s9["count"], s9["message"], s9["error"])
            result.alerts_generated = s9["count"]

            result.finish()
            self._write_status(
                "pipeline",
                "COMPLETED" if result.success else "BLOCKED_OR_FAILED",
                f"Run {self.run_id} completed; success={result.success}.",
            )
            logger.info("============================================================")
            logger.info("PIPELINE COMPLETED: Success=%s, Alerts=%d", result.success, result.alerts_generated)
            logger.info("============================================================")
            return result
        finally:
            if lock_file.exists():
                try:
                    lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
                    if lock_data.get("run_id") == self.run_id:
                        lock_file.unlink()
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    logger.warning("Could not safely remove pipeline lock: %s", exc)


def main():
    parser = argparse.ArgumentParser(description="Master Landslide Monitoring Pipeline Orchestrator.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without remote calls or disk writes.")
    parser.add_argument("--force", action="store_true", help="Force pipeline execution even if no new data detected.")
    parser.add_argument("--stage", choices=[
        "satellite_check", "rainfall_ingest", "data_preprocessing", "insar_processing",
        "feature_extraction", "unet_inference", "risk_assessment", "refresh_viewer", "evaluate_alerts"
    ], help="Run an isolated single stage.")
    args = parser.parse_args()

    pipeline = MasterPipeline(dry_run=args.dry_run, force=args.force)

    if args.stage:
        stage_func = getattr(pipeline, f"stage_{args.stage}")
        res = pipeline._execute_stage(args.stage, stage_func)
        print(json.dumps(res, indent=2))
    else:
        full_res = pipeline.run_all()
        print(json.dumps(full_res.to_dict(), indent=2))


if __name__ == "__main__":
    import numpy as np
    main()
