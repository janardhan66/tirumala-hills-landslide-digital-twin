from pathlib import Path

import numpy as np
import rasterio
from plotly import graph_objects as go
from rasterio.errors import RasterioError


class TerrainViewError(ValueError):
    """Raised when local terrain or overlay rasters cannot form one grid."""


TERRAIN_OVERLAYS = (
    "Elevation",
    "Slope",
    "Pair 2 correlation",
    "Pair 2 LOS displacement",
)

_OVERLAY_SETTINGS = {
    "Elevation": {
        "filename": None,
        "colorbar_title": "Elevation (m)",
        "colorscale": "Earth",
        "range": None,
    },
    "Slope": {
        "filename": "tirumala_slope_80m_gsi_aoi.tif",
        "colorbar_title": "Slope (degrees)",
        "colorscale": "Turbo",
        "range": (0.0, 50.0),
    },
    "Pair 2 correlation": {
        "filename": "tirumala_corr_80m_gsi_aoi.tif",
        "colorbar_title": "Correlation (0-1)",
        "colorscale": "Viridis",
        "range": (0.0, 1.0),
    },
    "Pair 2 LOS displacement": {
        "filename": "tirumala_los_disp_80m_gsi_aoi.tif",
        "colorbar_title": "LOS displacement (raster values)",
        "colorscale": "RdBu",
        "range": "symmetric",
    },
}

_GSI_AOI_DIR = Path("data") / "processed" / "dinsar" / "tirumala" / "gsi_aoi"
_DEM_FILENAME = "tirumala_dem_80m_gsi_aoi.tif"


def _read_raster(path):
    try:
        with rasterio.open(path) as dataset:
            if dataset.count != 1:
                raise TerrainViewError(
                    f"{path.name} must contain exactly one raster band."
                )
            values = np.ma.masked_invalid(
                dataset.read(1, masked=True).astype(np.float64)
            )
            return values, dataset.transform, dataset.crs
    except RasterioError as error:
        raise TerrainViewError(f"Could not read raster {path}: {error}") from error


def create_terrain_figure(base_dir, overlay_name, vertical_exaggeration=3.0):
    if overlay_name not in _OVERLAY_SETTINGS:
        raise TerrainViewError(f"Unsupported terrain overlay: {overlay_name}")
    if not np.isfinite(vertical_exaggeration) or vertical_exaggeration <= 0:
        raise TerrainViewError("Vertical exaggeration must be a positive number.")

    raster_dir = Path(base_dir) / _GSI_AOI_DIR
    dem_path = raster_dir / _DEM_FILENAME
    elevation, transform, crs = _read_raster(dem_path)

    if crs is None or crs.to_epsg() != 32644:
        raise TerrainViewError(
            f"The terrain DEM must use EPSG:32644; found {crs}."
        )
    if elevation.count() == 0:
        raise TerrainViewError("The terrain DEM contains no valid elevation values.")
    if transform.b != 0 or transform.d != 0 or transform.a <= 0 or transform.e >= 0:
        raise TerrainViewError(
            "The terrain DEM must be a north-up raster in EPSG:32644."
        )

    settings = _OVERLAY_SETTINGS[overlay_name]
    if settings["filename"] is None:
        overlay = elevation.copy()
    else:
        overlay_path = raster_dir / settings["filename"]
        overlay, overlay_transform, overlay_crs = _read_raster(overlay_path)
        if (
            overlay.shape != elevation.shape
            or overlay_transform != transform
            or overlay_crs != crs
        ):
            raise TerrainViewError(
                f"{overlay_path.name} is not aligned with the terrain DEM."
            )
        overlay = np.ma.masked_where(
            np.ma.getmaskarray(overlay) | np.ma.getmaskarray(elevation),
            overlay,
        )

    if overlay.count() == 0:
        raise TerrainViewError(
            f"The {overlay_name.lower()} overlay contains no valid values."
        )

    height, width = elevation.shape
    eastings = transform.c + (np.arange(width) + 0.5) * transform.a
    northings = transform.f + (np.arange(height) + 0.5) * transform.e
    elevation_values = elevation.filled(np.nan)
    overlay_values = overlay.filled(np.nan)

    color_range = settings["range"]
    if color_range == "symmetric":
        max_abs_value = float(np.max(np.abs(overlay.compressed())))
        color_range = (
            (-max_abs_value, max_abs_value)
            if max_abs_value > 0
            else None
        )

    figure = go.Figure(
        data=[
            go.Surface(
                x=eastings,
                y=northings,
                z=elevation_values,
                surfacecolor=overlay_values,
                colorscale=settings["colorscale"],
                cmin=color_range[0] if color_range else None,
                cmax=color_range[1] if color_range else None,
                colorbar={"title": settings["colorbar_title"]},
                connectgaps=False,
                hovertemplate=(
                    "Easting: %{x:.0f} m<br>"
                    "Northing: %{y:.0f} m<br>"
                    "Elevation: %{z:.1f} m<br>"
                    "Overlay value: %{surfacecolor:.4g}<extra></extra>"
                ),
            )
        ]
    )

    x_span = float(eastings[-1] - eastings[0])
    y_span = float(abs(northings[-1] - northings[0]))
    elevation_values_valid = elevation.compressed()
    z_span = float(np.max(elevation_values_valid) - np.min(elevation_values_valid))
    aspect_z = max(z_span / x_span * float(vertical_exaggeration), 0.01)

    figure.update_layout(
        height=680,
        margin={"l": 0, "r": 0, "t": 35, "b": 0},
        scene={
            "xaxis_title": "Easting (m, UTM 44N)",
            "yaxis_title": "Northing (m, UTM 44N)",
            "zaxis_title": (
                f"Elevation (m; {float(vertical_exaggeration):g}x vertical "
                "exaggeration)"
            ),
            "aspectmode": "manual",
            "aspectratio": {
                "x": 1.0,
                "y": y_span / x_span,
                "z": aspect_z,
            },
        },
        uirevision=overlay_name,
    )
    return figure
