"""
Tirumala 14-Channel Patch Builder for U-Net Inference

DISCLAIMER: This module creates input patches compatible with the Landslide4Sense
14-channel U-Net model. The model was trained on Landslide4Sense benchmark data,
NOT on Tirumala-specific imagery. Predictions should be treated as exploratory
indicators, not as validated landslide detections for Tirumala Hills.

Channel mapping:
  0-11: Sentinel-2 L2A optical bands (B01-B12 equivalents)
  12:   Topographic Slope (degrees)
  13:   Digital Elevation Model (meters)
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import PATHS, setup_logging

logger = setup_logging("patch_builder")


class TirumalaPatchBuilder:
    """
    Builds 14-channel (128×128) image patches from available Tirumala data.
    
    Sentinel-2 channels are required by default. Zero-filled optical channels
    are available only through the explicit experimental opt-in.
    """

    def __init__(
        self,
        patch_size: int = 128,
        stride: int = 64,
        dem_path: Optional[str] = None,
        slope_path: Optional[str] = None,
    ):
        self.patch_size = patch_size
        self.stride = stride
        self.dem_path = dem_path or str(PATHS.dem_tif)
        self.slope_path = slope_path or str(PATHS.slope_tif)
        self._dem_data: Optional[np.ndarray] = None
        self._slope_data: Optional[np.ndarray] = None
        self._s2_data: Optional[np.ndarray] = None
        self._dem_valid_mask: Optional[np.ndarray] = None
        self._has_optical = False
        self._transform = None
        self._crs = None

    def _load_raster(self, path: str) -> Optional[Tuple[np.ndarray, dict]]:
        """Load a GeoTIFF and return (data, metadata)."""
        try:
            import rasterio
            with rasterio.open(path) as src:
                masked_data = src.read(1, masked=True).astype(np.float32)
                valid_mask = ~np.ma.getmaskarray(masked_data)
                data = np.asarray(masked_data.filled(0.0), dtype=np.float32)
                valid_mask &= np.isfinite(data)
                data[~valid_mask] = 0.0
                meta = {
                    "transform": src.transform,
                    "crs": src.crs,
                    "shape": src.shape,
                    "valid_mask": valid_mask,
                }
                return data, meta
        except Exception as e:
            logger.error("Failed to load %s: %s", path, e)
            return None

    def _load_sentinel2(self, s2_dir: str) -> Optional[np.ndarray]:
        """
        Load 12 Sentinel-2 bands from a directory of band GeoTIFFs.
        
        Expected files: B01.tif, B02.tif, ..., B12.tif or similar naming.
        All bands are resampled to the DEM grid (80m, 69×110).
        """
        s2_path = Path(s2_dir)
        if not s2_path.exists():
            logger.warning("Sentinel-2 directory not found: %s", s2_dir)
            return None

        try:
            import rasterio
            from rasterio.enums import Resampling
            from rasterio.warp import reproject

            band_files = list(s2_path.glob("*.tif")) + list(s2_path.glob("*.jp2"))
            files_by_band = {}
            for band_file in band_files:
                match = re.search(r"(?:^|[_-])B(0[1-9]|1[0-2])(?:[_\-.]|$)", band_file.name, re.IGNORECASE)
                if match:
                    band_number = int(match.group(1))
                    if band_number in files_by_band:
                        raise ValueError(f"Multiple Sentinel-2 files found for B{band_number:02d}.")
                    files_by_band[band_number] = band_file

            missing = sorted(set(range(1, 13)) - set(files_by_band))
            if missing:
                logger.warning(
                    "Missing Sentinel-2 bands: %s.",
                    ", ".join(f"B{band:02d}" for band in missing),
                )
                return None

            if self._transform is None or self._crs is None:
                raise ValueError("Load the reference DEM before the Sentinel-2 bands.")
            target_shape = self._dem_data.shape
            bands = np.full((12, *target_shape), np.nan, dtype=np.float32)

            for band_number in range(1, 13):
                band_index = band_number - 1
                band_file = files_by_band[band_number]
                with rasterio.open(band_file) as src:
                    if src.crs is None:
                        raise ValueError(f"Sentinel-2 band has no CRS: {band_file}")
                    source = src.read(1, masked=True).astype(np.float32)
                    source_data = np.asarray(source.filled(np.nan), dtype=np.float32)
                    destination = np.full(target_shape, np.nan, dtype=np.float32)
                    reproject(
                        source=source_data,
                        destination=destination,
                        src_transform=src.transform,
                        src_crs=src.crs,
                        src_nodata=np.nan,
                        dst_transform=self._transform,
                        dst_crs=self._crs,
                        dst_nodata=np.nan,
                        resampling=Resampling.bilinear,
                        init_dest_nodata=True,
                    )
                    bands[band_index] = destination

            valid_pixels = self._dem_valid_mask
            if valid_pixels is not None and np.any(
                ~np.isfinite(bands[:, valid_pixels])
            ):
                logger.warning("Sentinel-2 bands do not fully cover valid DEM cells.")
                return None
            if not np.any(np.isfinite(bands[:, valid_pixels])):
                logger.warning("Sentinel-2 bands contain no valid values on the DEM grid.")
                return None
            if valid_pixels is not None:
                bands[:, ~valid_pixels] = 0.0

            logger.info("Loaded 12 ordered Sentinel-2 bands from %s.", s2_dir)
            return bands

        except Exception as e:
            logger.error("Sentinel-2 loading failed: %s", e)
            return None

    def prepare(self, s2_dir: Optional[str] = None, allow_incomplete: bool = False) -> bool:
        """Load all data sources and prepare for patch extraction."""
        # Load DEM
        result = self._load_raster(self.dem_path)
        if result is None:
            logger.error("Cannot proceed without DEM.")
            return False
        self._dem_data, dem_meta = result
        self._transform = dem_meta["transform"]
        self._crs = dem_meta["crs"]
        self._dem_valid_mask = dem_meta["valid_mask"]

        # Load Slope
        result = self._load_raster(self.slope_path)
        if result is None:
            logger.error("Cannot proceed without a valid slope raster.")
            return False
        self._slope_data, slope_meta = result
        if (
            slope_meta["shape"] != dem_meta["shape"]
            or slope_meta["crs"] != dem_meta["crs"]
            or slope_meta["transform"] != dem_meta["transform"]
        ):
            logger.error("Slope raster is not aligned to the reference DEM.")
            return False

        optical_dir = s2_dir or str(PATHS.processed_sentinel2)
        self._s2_data = self._load_sentinel2(optical_dir)

        if self._s2_data is None:
            if allow_incomplete:
                logger.warning(
                    "Sentinel-2 optical bands not available in %s; filling optical channels with zeros. "
                    "Inference will be marked as EXPERIMENTAL terrain screening.", optical_dir
                )
                target_shape = self._dem_data.shape
                self._s2_data = np.zeros((12, *target_shape), dtype=np.float32)
                self._has_optical = False
            else:
                logger.error("Valid Sentinel-2 bands are required; inference was not prepared.")
                return False
        else:
            self._has_optical = True

        logger.info(
            "Patch builder prepared. Grid: %s, DEM: ✓, Slope: ✓, S2: %s",
            self._dem_data.shape,
            "✓ (12 aligned bands)" if self._has_optical else "⚠️ (Zero-filled optical channels: Experimental screening)",
        )
        return True

    def _normalize(self, data: np.ndarray) -> np.ndarray:
        """Min-max normalize to [0, 1] range."""
        vmin = np.nanmin(data) if np.any(~np.isnan(data)) else 0
        vmax = np.nanmax(data) if np.any(~np.isnan(data)) else 1
        if vmax - vmin < 1e-10:
            return np.zeros_like(data)
        return (data - vmin) / (vmax - vmin)

    def extract_patches(self) -> List[Dict]:
        """
        Extract overlapping 128×128 patches covering the Tirumala grid.
        
        Returns list of dicts with keys:
          - 'tensor': np.ndarray shape (14, 128, 128), float32
          - 'row_start', 'col_start': patch origin in the grid
          - 'has_optical': bool, True if real Sentinel-2 data
          - 'valid_fraction': fraction of non-zero pixels
        """
        if (
            self._dem_data is None
            or self._slope_data is None
            or self._s2_data is None
        ):
            logger.error("Call prepare() with valid DEM, slope, and optical data before extracting patches.")
            return []

        H, W = self._dem_data.shape
        patches = []

        # Pad arrays to allow full patches
        pad_h = max(0, self.patch_size - H)
        pad_w = max(0, self.patch_size - W)

        dem_padded = np.pad(self._dem_data, ((0, pad_h), (0, pad_w)), mode="edge")
        slope_padded = np.pad(self._slope_data, ((0, pad_h), (0, pad_w)), mode="edge")
        s2_padded = np.pad(
            self._s2_data,
            ((0, 0), (0, pad_h), (0, pad_w)),
            mode="edge",
        )

        padded_H, padded_W = dem_padded.shape

        row_starts = list(range(0, padded_H - self.patch_size + 1, self.stride))
        if not row_starts or row_starts[-1] + self.patch_size < padded_H:
            row_starts.append(max(0, padded_H - self.patch_size))

        col_starts = list(range(0, padded_W - self.patch_size + 1, self.stride))
        if not col_starts or col_starts[-1] + self.patch_size < padded_W:
            col_starts.append(max(0, padded_W - self.patch_size))

        for rs in row_starts:
            for cs in col_starts:
                re = rs + self.patch_size
                ce = cs + self.patch_size

                # Build 14-channel tensor
                tensor = np.zeros((14, self.patch_size, self.patch_size), dtype=np.float32)

                # Channels 0-11: Sentinel-2
                for ch in range(12):
                    tensor[ch] = self._normalize(s2_padded[ch, rs:re, cs:ce])

                # Channel 12: Slope
                tensor[12] = self._normalize(slope_padded[rs:re, cs:ce])

                # Channel 13: DEM
                tensor[13] = self._normalize(dem_padded[rs:re, cs:ce])

                # Compute valid fraction
                valid_pixels = np.sum(dem_padded[rs:re, cs:ce] > 0)
                total_pixels = self.patch_size * self.patch_size
                valid_fraction = valid_pixels / total_pixels

                has_optical = self._has_optical

                patches.append({
                    "tensor": tensor,
                    "row_start": rs,
                    "col_start": cs,
                    "has_optical": has_optical,
                    "valid_fraction": round(float(valid_fraction), 3),
                })

        logger.info(
            "Extracted %d patches (size=%d, stride=%d) from %d×%d grid.",
            len(patches), self.patch_size, self.stride, H, W,
        )
        return patches

    def patches_to_torch(self, patches: List[Dict]):
        """Convert patch list to a PyTorch batch tensor."""
        try:
            import torch
            tensors = [torch.from_numpy(p["tensor"]) for p in patches]
            batch = torch.stack(tensors)
            logger.info("PyTorch batch: %s", batch.shape)
            return batch
        except ImportError:
            logger.error("PyTorch not installed.")
            return None
