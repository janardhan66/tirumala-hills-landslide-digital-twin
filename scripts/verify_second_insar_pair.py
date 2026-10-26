import rasterio
from pathlib import Path
import numpy as np


PROJECT = Path(__file__).resolve().parents[1]

pair_dir = Path(
    r"C:\S1\HyP3\Tirumala\extracted\pair_05_17"
)

pair_dir = next(pair_dir.glob("S1DD_*"))

print("\nSECOND INSAR PAIR VERIFICATION")
print("================================")
print("Pair:", pair_dir.name)

files = {
    "LOS displacement": next(pair_dir.glob("*_los_disp.tif")),
    "Correlation": next(pair_dir.glob("*_corr.tif")),
    "DEM": next(pair_dir.glob("*_dem.tif")),
    "Vertical displacement": next(pair_dir.glob("*_vert_disp.tif")),
    "Unwrapped phase": next(pair_dir.glob("*_unw_phase.tif")),
}


for name, file in files.items():

    with rasterio.open(file) as src:

        data = src.read(1)

        nodata = src.nodata

        if nodata is not None:
            valid = data[data != nodata]
        else:
            valid = data[np.isfinite(data)]

        valid = valid[np.isfinite(valid)]

        print(f"\n{name}")
        print("-" * len(name))
        print("File:", file.name)
        print("CRS:", src.crs)
        print("Shape:", src.height, "x", src.width)
        print("Resolution:", src.res)
        print("Bounds:", src.bounds)
        print("NoData:", src.nodata)

        if len(valid) > 0:
            print("Valid pixels:", len(valid))
            print("Min:", float(valid.min()))
            print("Max:", float(valid.max()))
            print("Mean:", float(valid.mean()))


print("\nVerification complete.")