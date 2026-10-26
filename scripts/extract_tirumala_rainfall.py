import os
import re
import zipfile

import numpy as np
import pandas as pd
import geopandas as gpd
from rasterio.mask import mask
from rasterio.io import MemoryFile


# =========================================================
# PATHS
# =========================================================

ZIP_DIR = r"C:\S1\HyP3\Tirumala"

AOI_FILE = r"data\raw\aoi\tirumala_hills_gsi_map_aoi.geojson"

OUTPUT_DIR = r"data\processed\rainfall\tirumala"

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "tirumala_daily_rainfall_20260801_20260829.csv"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# =========================================================
# READ AOI
# =========================================================

aoi = gpd.read_file(AOI_FILE)

if aoi.empty:
    raise RuntimeError("AOI file is empty.")

print("AOI CRS:", aoi.crs)
print("AOI geometry:", aoi.geometry.iloc[0].geom_type)


# =========================================================
# FIND IMERG FILES
# =========================================================

pattern = re.compile(
    r"3B-DAY-L\.GIS\.IMERG\.(202608\d{2})\.V07C\.zip$"
)

zip_files = []

for filename in os.listdir(ZIP_DIR):

    match = pattern.match(filename)

    if match:

        date_str = match.group(1)

        zip_files.append(
            (
                date_str,
                os.path.join(ZIP_DIR, filename)
            )
        )

zip_files.sort()

print("\nIMERG files found:", len(zip_files))

if len(zip_files) != 29:

    raise RuntimeError(
        f"Expected 29 files, but found {len(zip_files)}."
    )


# =========================================================
# PROCESS EACH DAY
# =========================================================

records = []

for date_str, zip_path in zip_files:

    print(
        "\nProcessing:",
        os.path.basename(zip_path)
    )

    with zipfile.ZipFile(zip_path, "r") as z:

        # -------------------------------------------------
        # Find all TIFF files
        # -------------------------------------------------

        all_tifs = [
            name
            for name in z.namelist()
            if name.lower().endswith(".tif")
        ]

        print(
            "  TIFF files found:",
            len(all_tifs)
        )

        # -------------------------------------------------
        # YOUR LATE RUN FILE FORMAT:
        #
        # Plain .tif = TOTAL PRECIPITATION
        #
        # Exclude:
        # .ice.tif
        # .liquid.tif
        # .liquidPercent.tif
        # .numPrecipHalfHour.tif
        # .numValidHalfHour.tif
        # -------------------------------------------------

        total_tifs = [
            name
            for name in all_tifs
            if (
                name.lower().endswith(".tif")
                and not name.lower().endswith(".ice.tif")
                and not name.lower().endswith(".liquid.tif")
                and not name.lower().endswith(".liquidpercent.tif")
                and not name.lower().endswith(
                    ".numpreciphalfhour.tif"
                )
                and not name.lower().endswith(
                    ".numvalidhalfhour.tif"
                )
            )
        ]

        if len(total_tifs) != 1:

            print("  Candidate total TIFFs:")

            for tif in total_tifs:
                print("   ", tif)

            raise RuntimeError(
                f"Expected exactly one total precipitation TIFF "
                f"but found {len(total_tifs)} in "
                f"{os.path.basename(zip_path)}"
            )

        tif_name = total_tifs[0]

        print(
            "  Selected TOTAL PRECIPITATION TIFF:",
            tif_name
        )

        # -------------------------------------------------
        # Read TIFF
        # -------------------------------------------------

        tif_bytes = z.read(tif_name)

        with MemoryFile(tif_bytes) as memfile:

            with memfile.open() as src:

                print("  CRS:", src.crs)

                print(
                    "  Shape:",
                    src.height,
                    "x",
                    src.width
                )

                # -------------------------------------------------
                # Reproject AOI
                # -------------------------------------------------

                aoi_raster = aoi.to_crs(src.crs)

                # -------------------------------------------------
                # Clip raster to Tirumala AOI
                # -------------------------------------------------

                clipped, transform = mask(
                    src,
                    aoi_raster.geometry,
                    crop=True,
                    filled=False
                )

                data = clipped[0].astype(float)

                # -------------------------------------------------
                # Extract valid pixels
                # -------------------------------------------------

                valid = data.compressed()

                if valid.size == 0:

                    raise RuntimeError(
                        f"No valid rainfall pixels for {date_str}"
                    )

                # -------------------------------------------------
                # Remove invalid values
                # -------------------------------------------------

                valid = valid[
                    np.isfinite(valid)
                ]

                valid = valid[
                    valid >= 0
                ]

                if valid.size == 0:

                    raise RuntimeError(
                        f"No valid non-negative rainfall "
                        f"pixels for {date_str}"
                    )

                # -------------------------------------------------
                # IMERG V07 scaling
                #
                # Daily precipitation:
                # stored value × 0.1 = mm
                # -------------------------------------------------

                rainfall_mm = valid * 0.1

                # -------------------------------------------------
                # Daily statistics
                # -------------------------------------------------

                record = {

                    "date": pd.to_datetime(
                        date_str,
                        format="%Y%m%d"
                    ),

                    "rainfall_mean_mm": float(
                        np.mean(rainfall_mm)
                    ),

                    "rainfall_min_mm": float(
                        np.min(rainfall_mm)
                    ),

                    "rainfall_max_mm": float(
                        np.max(rainfall_mm)
                    ),

                    "grid_cells": int(
                        rainfall_mm.size
                    )
                }

                records.append(record)

                print(
                    f"  Mean: "
                    f"{record['rainfall_mean_mm']:.3f} mm"
                )

                print(
                    f"  Min : "
                    f"{record['rainfall_min_mm']:.3f} mm"
                )

                print(
                    f"  Max : "
                    f"{record['rainfall_max_mm']:.3f} mm"
                )

                print(
                    f"  Valid cells: "
                    f"{record['grid_cells']}"
                )


# =========================================================
# CREATE DATAFRAME
# =========================================================

df = pd.DataFrame(records)

df = df.sort_values(
    "date"
).reset_index(drop=True)


# =========================================================
# SAVE CSV
# =========================================================

df["date"] = df["date"].dt.strftime(
    "%Y-%m-%d"
)

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# =========================================================
# FINAL OUTPUT
# =========================================================

print("\n========================================")
print("Rainfall extraction completed.")
print("Days processed:", len(df))
print("Output:", OUTPUT_FILE)
print("========================================")

print("\nFinal rainfall table:")

print(
    df.to_string(index=False)
)