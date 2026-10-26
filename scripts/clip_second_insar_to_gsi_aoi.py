import rasterio
from rasterio.mask import mask
import geopandas as gpd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

pair_dir = Path(
    r"C:\S1\HyP3\Tirumala\extracted\pair_05_17"
)

pair_dir = next(pair_dir.glob("S1DD_*"))

aoi_file = PROJECT / "data" / "raw" / "aoi" / "tirumala_hills_gsi_map_aoi.geojson"

output_dir = PROJECT / "data" / "processed" / "dinsar" / "tirumala" / "gsi_aoi" / "pair_05_17"
output_dir.mkdir(parents=True, exist_ok=True)

aoi = gpd.read_file(aoi_file)

files = {
    "los_disp": next(pair_dir.glob("*_los_disp.tif")),
    "corr": next(pair_dir.glob("*_corr.tif")),
    "dem": next(pair_dir.glob("*_dem.tif")),
}

print("\nCLIPPING SECOND INSAR PAIR TO GSI AOI")
print("======================================")
print("Pair:", pair_dir.name)

for name, input_file in files.items():

    with rasterio.open(input_file) as src:

        aoi_proj = aoi.to_crs(src.crs)

        clipped, transform = mask(
            src,
            aoi_proj.geometry,
            crop=True,
            nodata=0
        )

        profile = src.profile.copy()
        profile.update(
            height=clipped.shape[1],
            width=clipped.shape[2],
            transform=transform,
            nodata=0
        )

        output_file = output_dir / f"tirumala_{name}_80m_gsi_aoi_pair_05_17.tif"

        with rasterio.open(output_file, "w", **profile) as dst:
            dst.write(clipped)

        print("\n", name)
        print("Input :", input_file.name)
        print("Output:", output_file.name)
        print("Shape :", clipped.shape[1], "x", clipped.shape[2])
        print("CRS   :", src.crs)
        print("Resolution:", src.res)

print("\nClipping complete.")