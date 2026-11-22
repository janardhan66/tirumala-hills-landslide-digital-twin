"""
General Satellite Data Preprocessing

Clips, reprojects, and validates satellite rasters for the Tirumala study area.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import PATHS, STUDY_AREA, setup_logging

logger = setup_logging("preprocess_data")


def clip_to_aoi(
    input_path: str, output_path: str,
    target_crs: int = 32644, resolution: float = 80.0,
    bounds: Optional[Tuple[float, float, float, float]] = None,
    reference_path: Optional[str] = None,
) -> str:
    """
    Clip a raster to the Tirumala AOI, reproject to target CRS, and resample.

    Parameters
    ----------
    input_path : str
        Path to input GeoTIFF
    output_path : str
        Path for output GeoTIFF
    target_crs : int
        Target EPSG code (default: 32644, UTM Zone 44N)
    resolution : float
        Target pixel size in CRS units (meters for UTM)
    bounds : tuple, optional
        (west, south, east, north) in target CRS coordinates

    Returns
    -------
    str
        Output path on success. Raises a descriptive error on invalid input.
    """
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.features import geometry_mask
    from rasterio.mask import mask as rio_mask
    from rasterio.warp import calculate_default_transform, reproject, transform_geom
    from shapely.geometry import box

    reference = Path(reference_path) if reference_path else PATHS.dem_tif
    if not reference_path and not reference.exists():
        reference = None

    with rasterio.open(input_path) as src:
        if src.crs is None:
            raise ValueError(f"Input raster has no CRS: {input_path}")
        logger.info(
            "Input: %s, CRS: %s, Shape: %s, Resolution: %s",
            Path(input_path).name, src.crs, src.shape, src.res,
        )

        if bounds:
            aoi_geometry = box(*bounds).__geo_interface__
            aoi_source_crs = f"EPSG:{target_crs}"
        else:
            aoi_geometry = box(*STUDY_AREA.bbox).__geo_interface__
            aoi_source_crs = f"EPSG:{STUDY_AREA.epsg_geographic}"
        source_geometry = transform_geom(aoi_source_crs, src.crs, aoi_geometry)
        try:
            clipped, clipped_transform = rio_mask(
                src, [source_geometry], crop=True, filled=False
            )
        except ValueError as exc:
            raise ValueError(
                f"Study area does not overlap input raster: {input_path}"
            ) from exc

        source_data = np.asarray(clipped.data, dtype=np.float32)
        source_data[np.ma.getmaskarray(clipped)] = np.nan
        target_crs_obj = rasterio.crs.CRS.from_epsg(target_crs)

        if reference:
            with rasterio.open(reference) as reference_dataset:
                if reference_dataset.crs != target_crs_obj:
                    raise ValueError(
                        f"Reference raster CRS {reference_dataset.crs} does not "
                        f"match requested EPSG:{target_crs}."
                    )
                transform = reference_dataset.transform
                width = reference_dataset.width
                height = reference_dataset.height
        else:
            transform, width, height = calculate_default_transform(
                src.crs,
                target_crs_obj,
                source_data.shape[2],
                source_data.shape[1],
                *rasterio.transform.array_bounds(
                    source_data.shape[1], source_data.shape[2], clipped_transform
                ),
                resolution=resolution,
            )

        destination = np.full(
            (source_data.shape[0], height, width), np.nan, dtype=np.float32
        )
        for band_idx, band in enumerate(source_data):
            reproject(
                source=band,
                destination=destination[band_idx],
                src_transform=clipped_transform,
                src_crs=src.crs,
                src_nodata=np.nan,
                dst_transform=transform,
                dst_crs=target_crs_obj,
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
                init_dest_nodata=True,
            )

    destination_aoi = transform_geom(
        f"EPSG:{STUDY_AREA.epsg_geographic}",
        target_crs_obj,
        box(*STUDY_AREA.bbox).__geo_interface__,
    )
    outside_aoi = geometry_mask(
        [destination_aoi], out_shape=(height, width), transform=transform
    )
    destination[:, outside_aoi] = np.nan

    out_meta = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": destination.shape[0],
        "dtype": "float32",
        "crs": target_crs_obj,
        "transform": transform,
        "nodata": np.nan,
        "compress": "lzw",
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **out_meta) as dst:
        dst.write(destination)

    logger.info(
        "Output: %s, CRS: EPSG:%d, Shape: (%d, %d), Res: %.1f m",
        Path(output_path).name, target_crs, height, width, resolution,
    )
    return output_path


def validate_alignment(raster_path: str, expected_crs: int = 32644) -> dict:
    """Validate a raster's CRS, resolution, and bounds."""
    try:
        import rasterio
        with rasterio.open(raster_path) as src:
            crs_ok = src.crs and src.crs.to_epsg() == expected_crs
            return {
                "path": raster_path,
                "crs": str(src.crs),
                "crs_ok": crs_ok,
                "shape": src.shape,
                "resolution": src.res,
                "transform": tuple(src.transform),
                "bounds": src.bounds,
                "nodata": src.nodata,
                "dtype": str(src.dtypes[0]),
                "valid": crs_ok,
            }
    except Exception as e:
        return {"path": raster_path, "valid": False, "error": str(e)}


def preprocess_new_acquisitions(db=None) -> dict:
    """
    Automated preprocessing worker for newly downloaded satellite acquisitions.

    Validates file archives, clips to Tirumala AOI, reprojects to EPSG:32644,
    and aligns to the 80m reference grid. Avoids repeating work for already
    processed acquisitions.
    """
    import zipfile
    from src.data.db import get_db

    db = db or get_db()
    unprocessed = db.get_unprocessed_acquisitions() if hasattr(db, "get_unprocessed_acquisitions") else []
    if not unprocessed:
        with db.cursor() as cur:
            rows = cur.execute(
                "SELECT * FROM acquisitions WHERE download_status = 'DOWNLOADED' AND processing_status = 'UNPROCESSED'"
            ).fetchall()
            unprocessed = [dict(r) for r in rows]

    preprocessed_count = 0
    errors = []

    for acq in unprocessed:
        acq_id = acq["acquisition_id"]
        sat = acq.get("satellite", "")
        file_path_str = acq.get("file_path")
        if not file_path_str:
            errors.append(f"Downloaded acquisition {acq_id} has no recorded file path.")
            continue

        if not Path(file_path_str).exists():
            errors.append(
                f"Downloaded acquisition {acq_id} file does not exist: {file_path_str}"
            )
            continue

        file_path = Path(file_path_str)
        logger.info("Preprocessing acquisition %s (%s)...", acq_id, sat)

        try:
            if sat in {"Sentinel-1", "Sentinel-2"} and file_path.suffix.lower() == ".zip":
                if not zipfile.is_zipfile(file_path):
                    raise IOError(f"Corrupt {sat} archive: {file_path}")
                with zipfile.ZipFile(file_path) as archive:
                    members = archive.namelist()
                    if not members:
                        raise IOError(f"Empty {sat} archive: {file_path}")
                    if not any(
                        name.lower().endswith("manifest.safe")
                        for name in members
                    ):
                        raise IOError(
                            f"{sat} archive is missing manifest.safe: {file_path}"
                        )
                    if sat == "Sentinel-2":
                        from tempfile import TemporaryDirectory

                        with TemporaryDirectory(prefix="tirumala_s2_") as temporary:
                            archive.extractall(temporary)
                            extracted_root = Path(temporary)
                            band_files = {}
                            for candidate in extracted_root.rglob("*"):
                                if candidate.is_file():
                                    match = __import__("re").search(
                                        r"(?:^|[_-])B(0[1-9]|1[0-2])(?:[_\-.]|$)",
                                        candidate.stem,
                                        __import__("re").IGNORECASE,
                                    )
                                    if match and candidate.suffix.lower() in {".tif", ".tiff", ".jp2"}:
                                        band_files.setdefault(int(match.group(1)), candidate)

                            missing = sorted(set(range(1, 13)) - set(band_files))
                            if missing:
                                raise ValueError(
                                    "Sentinel-2 archive is missing bands: "
                                    + ", ".join(f"B{number:02d}" for number in missing)
                                )

                            output_dir = PATHS.processed_sentinel2
                            output_dir.mkdir(parents=True, exist_ok=True)
                            for band_number in range(1, 13):
                                output_path = output_dir / f"B{band_number:02d}.tif"
                                clip_to_aoi(
                                    str(band_files[band_number]),
                                    str(output_path),
                                    target_crs=32644,
                                    resolution=80.0,
                                    reference_path=str(PATHS.dem_tif),
                                )

                        preprocessed_count += 1
                        with db.cursor() as cur:
                            cur.execute(
                                "UPDATE acquisitions SET processing_status = 'PROCESSED', "
                                "error_message = NULL, updated_at = CURRENT_TIMESTAMP "
                                "WHERE acquisition_id = ?",
                                (acq_id,),
                            )
                    else:
                        extracted_dir = PATHS.raw_sentinel1 / "extracted" / acq_id
                        extracted_dir.mkdir(parents=True, exist_ok=True)
                        with zipfile.ZipFile(file_path) as archive:
                            archive.extractall(extracted_dir)
                        safe_dirs = list(extracted_dir.rglob("*.SAFE"))
                        file_path_value = str(safe_dirs[0]) if safe_dirs else str(extracted_dir)
                        with db.cursor() as cur:
                            cur.execute(
                                "UPDATE acquisitions SET processing_status = 'UNPROCESSED', "
                                "file_path = ?, error_message = 'SAFE archive extracted and "
                                "validated; pair registration is required before InSAR processing.', "
                                "updated_at = CURRENT_TIMESTAMP WHERE acquisition_id = ?",
                                (file_path_value, acq_id),
                            )
                        logger.info(
                            "Validated Sentinel-1 archive %s; awaiting InSAR pair registration.",
                            acq_id,
                        )
            elif sat in {"Sentinel-1", "Sentinel-2"}:
                errors.append(
                    f"{sat} product is not a supported ZIP archive; left UNPROCESSED: {file_path}"
                )
        except Exception as exc:
            err = f"Failed to preprocess {acq_id}: {exc}"
            logger.error(err)
            errors.append(err)
            with db.cursor() as cur:
                cur.execute(
                    "UPDATE acquisitions SET processing_status = 'FAILED', error_message = ? WHERE acquisition_id = ?",
                    (str(exc), acq_id)
                )
                db.conn.commit()

    # Validate baseline rasters readiness
    base_valid = PATHS.dem_tif.exists() and PATHS.slope_tif.exists()
    status_msg = (
        f"Preprocessed {preprocessed_count} new granules. Baseline terrain layers: {'READY' if base_valid else 'MISSING'}."
    )
    if errors:
        status_msg += f" Errors encountered: {len(errors)}"

    return {
        "preprocessed": preprocessed_count,
        "baseline_ready": base_valid,
        "errors": errors,
        "message": status_msg
    }



def main():
    parser = argparse.ArgumentParser(description="Preprocess satellite rasters for Tirumala.")
    parser.add_argument("--input", required=True, help="Input GeoTIFF path.")
    parser.add_argument("--output", required=True, help="Output GeoTIFF path.")
    parser.add_argument("--target-crs", type=int, default=32644, help="Target EPSG (default: 32644).")
    parser.add_argument("--resolution", type=float, default=80.0, help="Pixel size in meters.")
    parser.add_argument(
        "--reference",
        help="Reference raster whose exact CRS, transform, and dimensions are used.",
    )
    parser.add_argument("--validate-only", action="store_true", help="Only validate, don't process.")
    args = parser.parse_args()

    if args.validate_only:
        result = validate_alignment(args.input, args.target_crs)
        import json
        print(json.dumps(result, indent=2, default=str))
    else:
        result = clip_to_aoi(
            args.input,
            args.output,
            args.target_crs,
            args.resolution,
            reference_path=args.reference,
        )
        print(f"Output: {result}")


if __name__ == "__main__":
    main()
