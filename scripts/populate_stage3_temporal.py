"""Populate traceable per-cell temporal observations from one or more processed pairs."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.db import get_db


def populate_processed_pairs(db=None) -> dict:
    db = db or get_db()
    total = 0
    records_by_pair = {}

    for pair in db.get_insar_pairs(status="PROCESSED"):
        los_path = pair.get("los_disp_tif")
        coherence_path = pair.get("coherence_tif")
        if not los_path or not coherence_path:
            continue
        los_file = Path(los_path)
        coherence_file = Path(coherence_path)
        if not los_file.exists() or not coherence_file.exists():
            continue

        with (
            rasterio.open(los_file) as los_source,
            rasterio.open(coherence_file) as coherence_source,
        ):
            if (
                los_source.shape != coherence_source.shape
                or los_source.crs != coherence_source.crs
                or los_source.transform != coherence_source.transform
            ):
                continue
            los = los_source.read(1, masked=True)
            coherence = coherence_source.read(1, masked=True)

        records = []
        rows, cols = los.shape
        for row in range(rows):
            for col in range(cols):
                los_valid = not np.ma.is_masked(los[row, col])
                coherence_valid = not np.ma.is_masked(coherence[row, col])
                los_value = float(los[row, col]) if los_valid else None
                coherence_value = float(coherence[row, col]) if coherence_valid else None
                valid = (
                    los_value is not None
                    and coherence_value is not None
                    and np.isfinite(los_value)
                    and np.isfinite(coherence_value)
                    and coherence_value >= 0.5
                    and los_value != 0
                )
                records.append({
                    "cell_id": f"R{row}_C{col}",
                    "pair_id": pair["pair_id"],
                    "reference_date": pair["reference_date"],
                    "secondary_date": pair["secondary_date"],
                    "acquisition_date": pair["secondary_date"],
                    "los_displacement_m": los_value if valid else None,
                    "coherence": coherence_value if coherence_valid else None,
                    "quality_status": "VALID" if valid else "INSUFFICIENT",
                    "nodata_status": (
                        "VALID"
                        if los_valid and coherence_valid
                        else "NODATA"
                    ),
                    "source_raster": str(los_file),
                    "processing_metadata": json.dumps({
                        "coherence_raster": str(coherence_file),
                        "coherence_threshold": 0.5,
                        "reference_note": "LOS relative to pair phase reference.",
                    }, sort_keys=True),
                })

        count = db.bulk_upsert_temporal_insar_observations(records)
        records_by_pair[pair["pair_id"]] = count
        total += count

    return {
        "total_upserted": total,
        "records_by_pair": records_by_pair,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Populate traceable temporal InSAR observations without creating fake values."
    )
    args = parser.parse_args()
    print(json.dumps(populate_processed_pairs(), indent=2))


if __name__ == "__main__":
    main()
