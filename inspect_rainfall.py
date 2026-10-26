import glob
import os
import rasterio
import numpy as np

folder = r"data\raw\rainfall\tirumala"

files = sorted(glob.glob(os.path.join(folder, "*.tif")))

print("Number of files:", len(files))
print()

for path in files:
    with rasterio.open(path) as src:
        data = src.read(1)

        valid = data[np.isfinite(data)]

        print("=" * 70)
        print("FILE:", os.path.basename(path))
        print("CRS:", src.crs)
        print("SIZE:", src.width, "x", src.height)
        print("RESOLUTION:", src.res)
        print("BOUNDS:", src.bounds)
        print("NODATA:", src.nodata)
        print("DTYPE:", src.dtypes[0])

        if src.nodata is not None:
            valid = valid[valid != src.nodata]

        print("VALID PIXELS:", len(valid))

        if len(valid) > 0:
            print("RAW MIN:", float(np.min(valid)))
            print("RAW MAX:", float(np.max(valid)))
            print("RAW MEAN:", float(np.mean(valid)))

print("=" * 70)