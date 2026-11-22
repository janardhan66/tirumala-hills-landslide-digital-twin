"""
InSAR Processing Orchestrator

Provides two processing modes:
  Mode A (HyP3): Submit pairs to ASF HyP3 cloud API
  Mode B (SNAP): Local SNAP GPT processing for DInSAR

Outputs geocoded LOS displacement and coherence GeoTIFFs aligned to the
Tirumala 80m EPSG:32644 grid.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import CREDENTIALS, INSAR, PATHS, STUDY_AREA, setup_logging
from src.data.db import get_db

logger = setup_logging("process_insar")


class HyP3Processor:
    """
    Cloud-based InSAR processing via ASF HyP3 API.
    
    Uses hyp3_sdk to submit interferogram jobs and download geocoded results.
    This is the recommended mode for laptop environments since full SLC-to-
    interferogram processing requires 32+ GB RAM locally.
    """

    def __init__(self, db=None, output_dir: Optional[Path] = None):
        self.db = db or get_db()
        self.output_dir = output_dir or PATHS.processed_dinsar
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def submit_pair(
        self, granule_ref: str, granule_sec: str,
        reference_date: str, secondary_date: str
    ) -> str:
        """Submit an InSAR pair to HyP3 for processing."""
        try:
            import hyp3_sdk
        except ImportError as exc:
            raise RuntimeError("hyp3_sdk is required for HyP3 processing.") from exc

        if not CREDENTIALS.earthdata_username or not CREDENTIALS.earthdata_password:
            raise ValueError(
                "NASA Earthdata credentials are required for HyP3 processing."
            )
        try:
            reference = datetime.strptime(reference_date, "%Y-%m-%d").date()
            secondary = datetime.strptime(secondary_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("InSAR dates must use YYYY-MM-DD format.") from exc
        baseline_days = (secondary - reference).days
        if baseline_days <= 0:
            raise ValueError("Secondary acquisition date must follow the reference date.")
        if not self.db.acquisition_exists(granule_ref):
            raise ValueError(f"Reference acquisition is not in the local catalog: {granule_ref}")
        if not self.db.acquisition_exists(granule_sec):
            raise ValueError(f"Secondary acquisition is not in the local catalog: {granule_sec}")

        pair_id = f"PAIR_{reference:%Y%m%d}_{secondary:%Y%m%d}"
        with self.db.cursor() as cursor:
            existing = cursor.execute(
                "SELECT pair_id FROM insar_pairs WHERE pair_id = ?", (pair_id,)
            ).fetchone()
        if existing:
            raise ValueError(f"InSAR pair is already registered: {pair_id}")

        hyp3 = hyp3_sdk.HyP3(
            username=CREDENTIALS.earthdata_username,
            password=CREDENTIALS.earthdata_password,
        )
        def resolve_granule(acquisition_id: str) -> str:
            acquisition = self.db.get_acquisition(acquisition_id)
            if acquisition:
                try:
                    metadata = json.loads(acquisition.get("metadata_json") or "{}")
                    name = metadata.get("name")
                    if name:
                        return str(name)
                except json.JSONDecodeError:
                    pass
                file_path = acquisition.get("file_path")
                if file_path:
                    path = Path(file_path)
                    if path.suffix.lower() == ".zip":
                        return path.stem
                    if path.name:
                        return path.name
            return acquisition_id

        hyp3_ref = resolve_granule(granule_ref)
        hyp3_sec = resolve_granule(granule_sec)
        if hyp3_ref == granule_ref and hyp3_sec == granule_sec:
            logger.warning(
                "HyP3 granule names were not found in acquisition metadata; "
                "submission may require the original CDSE SAFE product name."
            )
        logger.info(
            "Submitting HyP3 InSAR job: %s × %s", granule_ref[:30], granule_sec[:30]
        )
        batch = hyp3.submit_insar_job(
            hyp3_ref,
            hyp3_sec,
            name=f"tirumala_{reference_date}_{secondary_date}",
            looks=INSAR.hyp3_looks,
            include_dem=True,
            include_inc_map=True,
            include_displacement_maps=True,
            phase_filter_parameter=INSAR.hyp3_phase_filter,
        )
        if not batch.jobs:
            raise RuntimeError("HyP3 accepted no jobs for the requested InSAR pair.")

        job_id = batch.jobs[0].job_id
        self.db.add_insar_pair(
            pair_id=pair_id,
            reference_acq_id=granule_ref,
            secondary_acq_id=granule_sec,
            reference_date=reference_date,
            secondary_date=secondary_date,
            temporal_baseline_days=baseline_days,
            processing_mode="hyp3",
            processing_status="SUBMITTED",
            hyp3_job_id=job_id,
        )
        logger.info("HyP3 job submitted: %s", job_id)
        return pair_id

    def check_and_download(self, pair_id: str = "all") -> List[Path]:
        """Check HyP3 job status and download results if complete."""
        try:
            import hyp3_sdk
        except ImportError as exc:
            raise RuntimeError("hyp3_sdk is required to check HyP3 jobs.") from exc

        pairs = self.db.get_insar_pairs(status="SUBMITTED")
        if pair_id != "all":
            pairs = [pair for pair in pairs if pair["pair_id"] == pair_id]
        if not pairs:
            logger.info("No pending HyP3 jobs found.")
            return []

        if not CREDENTIALS.earthdata_username or not CREDENTIALS.earthdata_password:
            raise ValueError(
                "NASA Earthdata credentials are required to check HyP3 jobs."
            )

        hyp3 = hyp3_sdk.HyP3(
            username=CREDENTIALS.earthdata_username,
            password=CREDENTIALS.earthdata_password,
        )
        downloaded_files: List[Path] = []
        for pair in pairs:
            job_id = pair.get("hyp3_job_id")
            if not job_id:
                self.db.update_insar_pair(
                    pair["pair_id"],
                    processing_status="FAILED",
                    error_message="Missing HyP3 job ID.",
                )
                continue

            job = hyp3.get_job_by_id(job_id)
            if job.status_code == "SUCCEEDED":
                logger.info("HyP3 job complete: %s", job.job_id)
                files = [Path(file) for file in job.download_files(self.output_dir)]
                if not files:
                    self.db.update_insar_pair(
                        pair["pair_id"],
                        processing_status="FAILED",
                        error_message="HyP3 job succeeded but returned no files.",
                    )
                    continue
                pair_dir = self.output_dir / pair["pair_id"]
                pair_dir.mkdir(parents=True, exist_ok=True)
                import zipfile
                for downloaded_file in files:
                    if downloaded_file.suffix.lower() == ".zip" and zipfile.is_zipfile(downloaded_file):
                        with zipfile.ZipFile(downloaded_file) as archive:
                            archive.extractall(pair_dir)
                    elif downloaded_file.is_file():
                        destination = pair_dir / downloaded_file.name
                        if downloaded_file.resolve() != destination.resolve():
                            import shutil
                            shutil.copy2(downloaded_file, destination)
                self.db.update_insar_pair(
                    pair["pair_id"],
                    processing_status="DOWNLOADED",
                    error_message=None,
                )
                downloaded_files.extend(files)
            elif job.status_code == "FAILED":
                self.db.update_insar_pair(
                    pair["pair_id"],
                    processing_status="FAILED",
                    error_message=f"HyP3 job failed: {job.job_id}",
                )
                logger.error("HyP3 job failed: %s", job.job_id)
            else:
                logger.info("HyP3 job %s status: %s", job.job_id, job.status_code)

        return downloaded_files

    def process_downloaded_products(self, pair_id: str) -> Dict:
        """Align downloaded HyP3 LOS/coherence products to the canonical 80 m grid."""
        pair = next(
            (item for item in self.db.get_insar_pairs() if item["pair_id"] == pair_id),
            None,
        )
        if pair is None:
            return {"status": "FAILED", "message": f"Unknown InSAR pair: {pair_id}"}

        pair_dir = self.output_dir / pair_id
        candidates = list(pair_dir.rglob("*")) if pair_dir.exists() else []
        tif_files = [path for path in candidates if path.is_file() and path.suffix.lower() == ".tif"]
        if not tif_files:
            return {
                "status": "WAITING",
                "message": f"No downloaded HyP3 GeoTIFF products found for {pair_id}.",
            }

        los_candidates = [
            path for path in tif_files
            if "los" in path.name.lower() or "displacement" in path.name.lower()
        ]
        coherence_candidates = [
            path for path in tif_files
            if "coh" in path.name.lower() or "correlation" in path.name.lower()
        ]
        if not los_candidates or not coherence_candidates:
            return {
                "status": "WAITING",
                "message": (
                    f"Downloaded HyP3 products for {pair_id} lack identifiable "
                    "LOS displacement and coherence rasters."
                ),
            }

        from scripts.preprocess_data import clip_to_aoi

        pair_output = PATHS.processed_dinsar / pair_id
        pair_output.mkdir(parents=True, exist_ok=True)
        los_output = pair_output / "los_disp_80m.tif"
        coherence_output = pair_output / "coherence_80m.tif"
        clip_to_aoi(
            str(los_candidates[0]),
            str(los_output),
            target_crs=STUDY_AREA.epsg_projected,
            resolution=INSAR.hyp3_resolution,
            reference_path=str(PATHS.dem_tif),
        )
        clip_to_aoi(
            str(coherence_candidates[0]),
            str(coherence_output),
            target_crs=STUDY_AREA.epsg_projected,
            resolution=INSAR.hyp3_resolution,
            reference_path=str(PATHS.dem_tif),
        )

        valid_pixels = None
        mean_coherence = None
        import rasterio
        with rasterio.open(coherence_output) as coherence_raster:
            coherence = coherence_raster.read(1, masked=True)
            valid_pixels = int(np.count_nonzero(~coherence.mask))
            values = coherence.compressed()
            mean_coherence = float(np.mean(values)) if values.size else None

        self.db.update_insar_pair(
            pair_id,
            processing_status="PROCESSED",
            los_disp_tif=str(los_output),
            coherence_tif=str(coherence_output),
            valid_pixels=valid_pixels,
            mean_coherence=mean_coherence,
            quality_notes=(
                "LOS and coherence rasters aligned to the Tirumala 80 m grid; "
                "LOS is not a vertical displacement measurement."
            ),
            error_message=None,
        )
        return {
            "status": "PROCESSED",
            "pairs_processed": 1,
            "message": f"Processed and aligned HyP3 outputs for {pair_id}.",
        }


class SNAPProcessor:
    """
    Local InSAR processing using ESA SNAP Graph Processing Tool (gpt).
    
    WARNING: Processing full Sentinel-1 SLC scenes locally requires significant
    RAM (16-32 GB). This mode uses sub-swath splitting focused on Tirumala AOI
    to reduce memory usage to ~8 GB.
    """

    def __init__(self):
        self.db = get_db()
        self.output_dir = PATHS.processed_dinsar
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_snap_graph(
        self, ref_safe: str, sec_safe: str, output_prefix: str
    ) -> str:
        """Generate SNAP GPT XML processing graph for DInSAR."""
        bbox = STUDY_AREA.bbox
        graph_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<graph id="TirumalaInSAR">
  <version>1.0</version>
  
  <!-- Step 1: Read Reference SLC -->
  <node id="Read-Ref">
    <operator>Read</operator>
    <parameters><file>{ref_safe}</file></parameters>
  </node>
  
  <!-- Step 2: Read Secondary SLC -->
  <node id="Read-Sec">
    <operator>Read</operator>
    <parameters><file>{sec_safe}</file></parameters>
  </node>
  
  <!-- Step 3: Apply Orbit Files -->
  <node id="Orbit-Ref">
    <operator>Apply-Orbit-File</operator>
    <sources><sourceProduct refid="Read-Ref"/></sources>
    <parameters>
      <orbitType>Sentinel Precise (Auto Download)</orbitType>
      <polyDegree>3</polyDegree>
    </parameters>
  </node>
  
  <node id="Orbit-Sec">
    <operator>Apply-Orbit-File</operator>
    <sources><sourceProduct refid="Read-Sec"/></sources>
    <parameters>
      <orbitType>Sentinel Precise (Auto Download)</orbitType>
      <polyDegree>3</polyDegree>
    </parameters>
  </node>
  
  <!-- Step 4: Back-Geocoding (Co-registration) -->
  <node id="BackGeocoding">
    <operator>Back-Geocoding</operator>
    <sources>
      <sourceProduct refid="Orbit-Ref"/>
      <sourceProduct.1 refid="Orbit-Sec"/>
    </sources>
    <parameters>
      <demName>Copernicus 30m Global DEM</demName>
      <demResamplingMethod>BICUBIC_INTERPOLATION</demResamplingMethod>
    </parameters>
  </node>
  
  <!-- Step 5: Interferogram Formation -->
  <node id="Interferogram">
    <operator>Interferogram</operator>
    <sources><sourceProduct refid="BackGeocoding"/></sources>
    <parameters>
      <subtractFlatEarthPhase>true</subtractFlatEarthPhase>
      <srpPolynomialDegree>5</srpPolynomialDegree>
      <srpNumberPoints>501</srpNumberPoints>
      <orbitDegree>3</orbitDegree>
      <includeCoherence>true</includeCoherence>
      <cohWinAz>3</cohWinAz>
      <cohWinRg>10</cohWinRg>
    </parameters>
  </node>
  
  <!-- Step 6: Topographic Phase Removal -->
  <node id="TopoPhaseRemoval">
    <operator>TopoPhaseRemoval</operator>
    <sources><sourceProduct refid="Interferogram"/></sources>
    <parameters>
      <demName>Copernicus 30m Global DEM</demName>
      <tileExtensionPercent>100</tileExtensionPercent>
    </parameters>
  </node>
  
  <!-- Step 7: Multilooking -->
  <node id="Multilook">
    <operator>Multilook</operator>
    <sources><sourceProduct refid="TopoPhaseRemoval"/></sources>
    <parameters>
      <nRgLooks>4</nRgLooks>
      <nAzLooks>1</nAzLooks>
    </parameters>
  </node>
  
  <!-- Step 8: Goldstein Phase Filtering -->
  <node id="GoldsteinFilter">
    <operator>GoldsteinPhaseFiltering</operator>
    <sources><sourceProduct refid="Multilook"/></sources>
    <parameters>
      <alpha>{INSAR.hyp3_phase_filter}</alpha>
      <FFTSizeString>64</FFTSizeString>
      <windowSizeString>3</windowSizeString>
    </parameters>
  </node>
  
  <!-- Step 9: Subset to Tirumala AOI -->
  <node id="Subset">
    <operator>Subset</operator>
    <sources><sourceProduct refid="GoldsteinFilter"/></sources>
    <parameters>
      <geoRegion>POLYGON(({bbox[0]} {bbox[1]}, {bbox[2]} {bbox[1]}, {bbox[2]} {bbox[3]}, {bbox[0]} {bbox[3]}, {bbox[0]} {bbox[1]}))</geoRegion>
    </parameters>
  </node>
  
  <!-- Step 10: Terrain Correction (Geocoding) -->
  <node id="TerrainCorrection">
    <operator>Terrain-Correction</operator>
    <sources><sourceProduct refid="Subset"/></sources>
    <parameters>
      <demName>Copernicus 30m Global DEM</demName>
      <pixelSpacingInMeter>{INSAR.hyp3_resolution}</pixelSpacingInMeter>
      <mapProjection>EPSG:{STUDY_AREA.epsg_projected}</mapProjection>
    </parameters>
  </node>
  
  <!-- Step 11: Write Output -->
  <node id="Write">
    <operator>Write</operator>
    <sources><sourceProduct refid="TerrainCorrection"/></sources>
    <parameters>
      <file>{output_prefix}</file>
      <formatName>GeoTIFF</formatName>
    </parameters>
  </node>
</graph>"""
        return graph_xml

    def process_pair(self, ref_safe: str, sec_safe: str, 
                     reference_date: str, secondary_date: str) -> Optional[Path]:
        """Process an InSAR pair using SNAP GPT."""
        import subprocess

        output_prefix = str(
            self.output_dir / f"insar_{reference_date}_{secondary_date}"
        )
        graph_path = self.output_dir / f"graph_{reference_date}_{secondary_date}.xml"

        # Generate and save graph
        graph_xml = self._generate_snap_graph(ref_safe, sec_safe, output_prefix)
        graph_path.write_text(graph_xml, encoding="utf-8")
        logger.info("SNAP graph saved: %s", graph_path)

        # Run GPT
        gpt_cmd = [
            INSAR.snap_gpt_path,
            str(graph_path),
            f"-J-Xmx{INSAR.snap_max_memory_gb}G",
        ]
        logger.info("Running SNAP GPT: %s", " ".join(gpt_cmd))

        try:
            result = subprocess.run(
                gpt_cmd, capture_output=True, text=True, timeout=7200
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"SNAP GPT failed (exit {result.returncode}): "
                    f"{result.stderr[:2000]}"
                )
            logger.info("SNAP GPT completed successfully.")
            return Path(output_prefix)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"SNAP GPT not found at '{INSAR.snap_gpt_path}'. Install ESA SNAP "
                "and add gpt to PATH, or use --mode hyp3."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("SNAP GPT timed out after 2 hours.") from exc


def convert_phase_to_displacement(phase_rad: np.ndarray) -> np.ndarray:
    """
    Convert unwrapped phase (radians) to LOS displacement (meters).
    
    d_LOS = -λ/(4π) × Δφ
    
    Where λ = 0.05546 m (C-band wavelength).
    
    IMPORTANT: This gives line-of-sight displacement, NOT vertical displacement.
    Converting LOS to vertical requires incidence angle decomposition.
    """
    return -(INSAR.wavelength_m / (4 * np.pi)) * phase_rad


def apply_coherence_mask(
    data: np.ndarray, coherence: np.ndarray,
    threshold: float = 0.50
) -> np.ndarray:
    """
    Mask displacement values where coherence is below threshold.
    
    Low coherence indicates temporal decorrelation (e.g., vegetation changes)
    or geometric decorrelation, making phase measurements unreliable.
    """
    masked = data.copy()
    masked[coherence < threshold] = np.nan
    return masked


def process_new_insar_pairs(db=None) -> dict:
    """
    Automated InSAR processing pipeline evaluator.

    Checks for pending InSAR pairs, inspects ESA SNAP / ASF HyP3 prerequisites,
    and safely blocks execution if credentials or raw files are absent,
    preventing any synthetic or fake raster generation.
    """
    db = db or get_db()
    from scripts.process_insar import HyP3Processor

    submitted_processor = HyP3Processor(db=db)
    downloaded_files = submitted_processor.check_and_download("all")
    processed_count = 0
    for pair in db.get_insar_pairs(status="DOWNLOADED"):
        result = submitted_processor.process_downloaded_products(pair["pair_id"])
        if result.get("status") == "PROCESSED":
            processed_count += 1
        elif result.get("status") == "WAITING":
            logger.warning("HyP3 products waiting for processing: %s", result["message"])

    if processed_count:
        return {
            "status": "SUCCESS",
            "pairs_processed": processed_count,
            "message": f"Processed {processed_count} downloaded HyP3 InSAR pair(s).",
        }

    if CREDENTIALS.earthdata_username and CREDENTIALS.earthdata_password:
        downloaded_s1 = db.get_acquisitions_by_status(
            "Sentinel-1", download_status="DOWNLOADED", processing_status="UNPROCESSED"
        )
        downloaded_s1 = [
            acquisition for acquisition in downloaded_s1
            if acquisition.get("product_type") == "SLC"
        ]
        pair_registrations = 0
        for reference in downloaded_s1:
            try:
                reference_date = datetime.strptime(
                    reference["acquisition_date"], "%Y-%m-%d"
                ).date()
            except (KeyError, TypeError, ValueError):
                continue
            for secondary in downloaded_s1:
                try:
                    secondary_date = datetime.strptime(
                        secondary["acquisition_date"], "%Y-%m-%d"
                    ).date()
                except (KeyError, TypeError, ValueError):
                    continue
                baseline = (secondary_date - reference_date).days
                if baseline <= 0 or baseline < INSAR.min_temporal_baseline_days:
                    continue
                if baseline > INSAR.max_temporal_baseline_days:
                    continue
                pair_id = (
                    f"PAIR_{reference_date:%Y%m%d}_{secondary_date:%Y%m%d}"
                )
                if db.acquisition_exists(reference["acquisition_id"]) and db.acquisition_exists(
                    secondary["acquisition_id"]
                ):
                    existing = [
                        pair for pair in db.get_insar_pairs()
                        if pair["pair_id"] == pair_id
                    ]
                    if existing:
                        continue
                    try:
                        submitted_processor.submit_pair(
                            reference["acquisition_id"],
                            secondary["acquisition_id"],
                            reference_date.isoformat(),
                            secondary_date.isoformat(),
                        )
                        pair_registrations += 1
                    except (ValueError, RuntimeError) as exc:
                        logger.warning("Could not submit candidate pair %s: %s", pair_id, exc)
                        continue
        if pair_registrations:
            return {
                "status": "SUCCESS",
                "pairs_processed": pair_registrations,
                "message": f"Submitted {pair_registrations} new HyP3 InSAR pair(s).",
            }

    pending_pairs = db.get_pending_insar_pairs() if hasattr(db, "get_pending_insar_pairs") else []
    if not pending_pairs:
        with db.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM insar_pairs WHERE processing_status = 'PENDING'"
            ).fetchall()
            pending_pairs = [dict(r) for r in rows]

    if not pending_pairs:
        return {
            "status": "UP_TO_DATE",
            "pairs_processed": 0,
            "message": "All registered InSAR pairs are already processed. No pending pairs."
        }

    # Evaluate execution capability
    has_earthdata = bool(CREDENTIALS.earthdata_username and CREDENTIALS.earthdata_password)
    has_snap = False
    import shutil
    if shutil.which(INSAR.snap_gpt_path) or Path("C:/Program Files/esa-snap/bin/gpt.exe").exists():
        has_snap = True

    if not has_earthdata and not has_snap:
        msg = (
            "BLOCKED: InSAR processing requires either ASF HyP3 cloud credentials "
            "(EARTHDATA_USERNAME / EARTHDATA_PASSWORD in .env) or a local ESA SNAP desktop installation. "
            "Stage blocked safely; no synthetic rasters generated."
        )
        logger.warning(msg)
        return {
            "status": "BLOCKED",
            "reason": "Missing Earthdata credentials and ESA SNAP",
            "pairs_processed": 0,
            "message": msg
        }

    if not has_earthdata and has_snap:
        # SNAP is installed locally; check if raw Sentinel-1 SLC archives exist
        raw_s1_files = list(PATHS.raw_sentinel1.glob("*.zip")) + list(PATHS.raw_sentinel1.glob("*.SAFE"))
        if not raw_s1_files:
            msg = (
                "BLOCKED: ESA SNAP gpt is available, but no raw Sentinel-1 SLC scenes "
                "exist in data/raw/sentinel1. Download must succeed before SNAP graph execution."
            )
            logger.warning(msg)
            return {
                "status": "BLOCKED",
                "reason": "Raw SLC scenes missing for SNAP execution",
                "pairs_processed": 0,
                "message": msg
            }

    return {
        "status": "READY",
        "pending_count": len(pending_pairs),
        "pairs_processed": 0,
        "message": f"{len(pending_pairs)} pairs pending processing."
    }


def main():
    parser = argparse.ArgumentParser(
        description="Process Sentinel-1 InSAR pairs for Tirumala Hills."
    )
    parser.add_argument(
        "--mode", choices=["hyp3", "snap"], default="hyp3",
        help="Processing mode: 'hyp3' (cloud API) or 'snap' (local GPT).",
    )
    parser.add_argument("--reference-date", help="Reference date (YYYY-MM-DD).")
    parser.add_argument("--secondary-date", help="Secondary date (YYYY-MM-DD).")
    parser.add_argument("--reference-granule", help="Reference SLC granule ID or SAFE path.")
    parser.add_argument("--secondary-granule", help="Secondary SLC granule ID or SAFE path.")
    parser.add_argument("--check-status", action="store_true",
                        help="Check status of pending HyP3 jobs.")
    args = parser.parse_args()

    if args.check_status:
        proc = HyP3Processor()
        proc.check_and_download("all")
        return

    if not args.reference_date or not args.secondary_date:
        logger.error("--reference-date and --secondary-date are required.")
        parser.print_help()
        return

    if args.mode == "hyp3":
        proc = HyP3Processor()
        if args.reference_granule and args.secondary_granule:
            pair_id = proc.submit_pair(
                args.reference_granule, args.secondary_granule,
                args.reference_date, args.secondary_date,
            )
            print(json.dumps({"pair_id": pair_id, "status": "SUBMITTED"}))
        else:
            logger.error("HyP3 mode requires --reference-granule and --secondary-granule.")
    elif args.mode == "snap":
        proc = SNAPProcessor()
        if args.reference_granule and args.secondary_granule:
            result = proc.process_pair(
                args.reference_granule, args.secondary_granule,
                args.reference_date, args.secondary_date,
            )
            print(json.dumps({"output": str(result) if result else None}))
        else:
            logger.error("SNAP mode requires --reference-granule and --secondary-granule (SAFE paths).")


if __name__ == "__main__":
    main()
