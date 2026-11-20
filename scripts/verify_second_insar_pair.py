import rasterio
from pathlib import Path
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]

pair_dir = Path(
    r"C:\S1\HyP3\Tirumala\extracted"
    r"\S1DD_20260817T003059_20260829T003100_VVP012_INT80_G_ueF_3158"
)

print("\nSECOND INSAR PAIR VERIFICATION")
print("================================")
print("Expected pair: 17–29 August 2026")
print("Product directory:", pair_dir)

if not pair_dir.is_dir():
    raise FileNotFoundError(f"Pair 2 directory not found: {pair_dir}")

patterns = {
    "LOS displacement": "*_los_disp.tif",
    "Correlation": "*_corr.tif",
    "DEM": "*_dem.tif",
    "Vertical displacement": "*_vert_disp.tif",
    "Unwrapped phase": "*_unw_phase.tif",
}

for name, pattern in patterns.items():
    matches = list(pair_dir.glob(pattern))

    print(f"\n{name}")
    print("-" * len(name))

    if not matches:
        print("File not found; skipped.")
        continue

    file = matches[0]

    with rasterio.open(file) as src:
        data = src.read(1)
        valid_mask = np.isfinite(data)

        if src.nodata is not None:
            valid_mask &= data != src.nodata

        valid = data[valid_mask]

        print("File:", file.name)
        print("CRS:", src.crs)
        print("Shape:", src.height, "x", src.width)
        print("Resolution:", src.res)
        print("Bounds:", src.bounds)
        print("NoData:", src.nodata)
        print("Valid pixels:", int(valid.size))

        if valid.size:
            print("Min:", float(valid.min()))
            print("Max:", float(valid.max()))
            print("Mean:", float(valid.mean()))

print("\nVerification complete.")
