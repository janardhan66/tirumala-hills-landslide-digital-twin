from pathlib import Path
import json

from shapely.geometry import shape, Point
from shapely.ops import transform
from pyproj import CRS, Transformer

files = [
    Path("data/raw/aoi/tirumala_aoi.geojson"),
    Path("data/raw/aoi/tirumala_hills_aoi.geojson"),
    Path("data/raw/aoi/tirumala_hills_gsi_map_aoi.geojson"),
    Path("data/raw/aoi/tirumala/tirumala_hills_aoi.geojson"),
]

events = [
    ("Tirumala 2013", 13.653, 79.344),
    ("Tirumala Road 2017", 13.665, 79.357),
]

for path in files:
    print("\n" + "=" * 75)
    print("FILE:", path)

    if not path.exists():
        print("FILE NOT FOUND")
        continue

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        features = data.get("features", [])

        if data.get("type") == "Feature":
            features = [data]

        if not features and data.get("type") in ("Polygon", "MultiPolygon"):
            geom = shape(data)
        else:
            geometries = [
                shape(f["geometry"])
                for f in features
                if f.get("geometry")
            ]
            from shapely.ops import unary_union
            geom = unary_union(geometries)

        print("Geometry type:", geom.geom_type)
        print("Valid geometry:", geom.is_valid)
        print("Bounds (lon_min, lat_min, lon_max, lat_max):", geom.bounds)

        # GeoJSON coordinates are assumed to be WGS84 longitude/latitude.
        project = Transformer.from_crs(
            "EPSG:4326", "EPSG:32644", always_xy=True
        ).transform
        area_km2 = transform(project, geom).area / 1_000_000
        print("Approximate area (km²):", round(area_km2, 3))

        for name, lat, lon in events:
            point = Point(lon, lat)
            inside = geom.covers(point)
            distance_km = 0.0 if inside else (
                transform(project, point).distance(
                    transform(project, geom)
                ) / 1000
            )
            print(
                f"{name}: inside={inside}, "
                f"distance_to_boundary_km={distance_km:.3f}"
            )

        if features:
            print("First feature properties:",
                  features[0].get("properties", {}))

    except Exception as e:
        print("ERROR:", repr(e))
