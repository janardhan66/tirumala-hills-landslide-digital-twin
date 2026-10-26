import os
import rasterio

folder = r"data\processed\dinsar\tirumala\clipped"

files = [
    "tirumala_dem_80m.tif",
    "tirumala_slope_80m.tif",
    "tirumala_corr_80m.tif",
    "tirumala_masked_los_disp_80m.tif",
]

reference = None

for filename in files:
    path = os.path.join(folder, filename)

    with rasterio.open(path) as src:
        info = {
            "size": (src.width, src.height),
            "crs": str(src.crs),
            "transform": src.transform,
            "bounds": src.bounds,
            "resolution": src.res,
        }

        print("\nFILE:", filename)
        print("SIZE:", info["size"])
        print("CRS:", info["crs"])
        print("RESOLUTION:", info["resolution"])
        print("BOUNDS:", info["bounds"])
        print("TRANSFORM:", info["transform"])

        if reference is None:
            reference = info
            print("REFERENCE: YES")
        else:
            aligned = (
                info["size"] == reference["size"]
                and info["crs"] == reference["crs"]
                and info["transform"] == reference["transform"]
                and info["bounds"] == reference["bounds"]
            )

            print("ALIGNED:", aligned)

print("\nAlignment check completed.")