import os
import glob
import rasterio
import numpy as np

folder = r"data\processed\dinsar\tirumala\clipped"

for f in glob.glob(os.path.join(folder, "*.tif")):
    with rasterio.open(f) as src:
        a = src.read(1, masked=True)

        print("\nFILE:", os.path.basename(f))
        print("SIZE:", src.width, "x", src.height)
        print("CRS:", src.crs)
        print("BOUNDS:", src.bounds)
        print("NODATA:", src.nodata)
        print("VALID PIXELS:", a.count())

        if a.count() > 0:
            print("MIN:", float(a.min()))
            print("MAX:", float(a.max()))
            print("MEAN:", float(a.mean()))
        else:
            print("MIN: NONE")
            print("MAX: NONE")
            print("MEAN: NONE")