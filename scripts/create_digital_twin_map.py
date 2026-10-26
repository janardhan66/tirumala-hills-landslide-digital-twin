import pandas as pd
import geopandas as gpd
import folium
import rasterio

from pathlib import Path
from pyproj import Transformer


PROJECT = Path(__file__).resolve().parents[1]

data_file = PROJECT / "results" / "agent" / \
    "tirumala_agent_monitoring_report.csv"

aoi_file = PROJECT / "data" / "raw" / "aoi" / \
    "tirumala_hills_gsi_map_aoi.geojson"

gsi_file = PROJECT / "data" / "features" / \
    "tirumala_gsi_historical_component.csv"

raster_file = PROJECT / "data" / "processed" / \
    "dinsar" / "tirumala" / "gsi_aoi" / \
    "tirumala_dem_80m_gsi_aoi.tif"

output_file = PROJECT / "results" / "digital_twin" / \
    "tirumala_digital_twin.html"


# ==================================================
# READ DATA
# ==================================================

df = pd.read_csv(data_file)

aoi = gpd.read_file(aoi_file).to_crs("EPSG:4326")

gsi = pd.read_csv(gsi_file)


# ==================================================
# MAP CENTRE
# ==================================================

bounds = aoi.total_bounds

center_lon = (bounds[0] + bounds[2]) / 2
center_lat = (bounds[1] + bounds[3]) / 2


# ==================================================
# OFFLINE MAP
# ==================================================

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=13,
    tiles=None,
    control_scale=True
)


# ==================================================
# AOI BOUNDARY
# ==================================================

aoi_layer = folium.FeatureGroup(
    name="GSI Approximate Study Area"
)

folium.GeoJson(
    aoi.to_json(),
    style_function=lambda feature: {
        "color": "black",
        "weight": 3,
        "fillColor": "white",
        "fillOpacity": 0.02
    }
).add_to(aoi_layer)

aoi_layer.add_to(m)


# ==================================================
# GSI HISTORICAL EVIDENCE
# ==================================================

gsi_layer = folium.FeatureGroup(
    name="GSI Figure 3.2 Historical Evidence"
)

for _, point in gsi.iterrows():

    folium.Marker(
        location=[
            point["latitude"],
            point["longitude"]
        ],
        popup=folium.Popup(
            f"""
            <div style="width:240px">
            <b>GSI Historical Evidence</b><br><br>

            <b>ID:</b> {point["inventory_id"]}<br>
            <b>Source:</b> GSI Figure 3.2<br>
            <b>Coordinate quality:</b>
            Map-derived approximate
            </div>
            """,
            max_width=280
        ),
        tooltip="GSI historical evidence"
    ).add_to(gsi_layer)

gsi_layer.add_to(m)


# ==================================================
# RASTER TRANSFORMATION
# ==================================================

with rasterio.open(raster_file) as src:

    transform = src.transform
    raster_crs = src.crs


transformer = Transformer.from_crs(
    raster_crs,
    "EPSG:4326",
    always_xy=True
)


# ==================================================
# AGENT LAYERS
# ==================================================

multiple_layer = folium.FeatureGroup(
    name="Agent - Multiple Spatial Evidence"
)

terrain_layer = folium.FeatureGroup(
    name="Agent - Terrain Dominant"
)

insar_layer = folium.FeatureGroup(
    name="Agent - InSAR Dominant"
)


# ==================================================
# AGENT OBSERVATIONS
# ==================================================

for _, row in df.iterrows():

    status = row["agent_monitoring_status"]

    # Ignore observations with no high spatial evidence
    if status == "No high spatial evidence":
        continue


    x, y = rasterio.transform.xy(
        transform,
        int(row["row"]),
        int(row["col"]),
        offset="center"
    )

    lon, lat = transformer.transform(
        x,
        y
    )


    # ------------------------------------------------
    # Select visual representation
    # ------------------------------------------------

    if status == "Multiple spatial evidence":

        layer = multiple_layer
        radius = 5
        fill_color = "#d73027"

    elif status == "Terrain-dominant evidence":

        layer = terrain_layer
        radius = 4
        fill_color = "#fc8d59"

    else:

        layer = insar_layer
        radius = 4
        fill_color = "#4575b4"


    # ------------------------------------------------
    # Popup
    # ------------------------------------------------

    popup = f"""
    <div style="width:300px">

    <b>INTELLIGENT AGENT ASSESSMENT</b>

    <hr>

    <b>Agent Status:</b><br>
    {status}

    <br><br>

    <b>Terrain</b><br>
    Elevation: {row["elevation_m"]:.2f} m<br>
    Slope: {row["slope_deg"]:.2f}°<br>
    Terrain class: {row["terrain_class"]}

    <br><br>

    <b>InSAR</b><br>
    LOS displacement:
    {row["los_disp_m"] * 1000:.2f} mm<br>

    LOS magnitude:
    {row["los_abs_m"] * 1000:.2f} mm<br>

    Correlation:
    {row["correlation"]:.3f}<br>

    Monitoring class:
    {row["insar_monitoring_class"]}

    <br><br>

    <b>Agent Explanation</b><br>
    {row["agent_explanation"]}

    <br><br>

    <b>Recommended Follow-up</b><br>
    {row["agent_recommendation"]}

    </div>
    """


    folium.CircleMarker(
        location=[lat, lon],
        radius=radius,
        popup=folium.Popup(
            popup,
            max_width=330
        ),
        tooltip=status,
        color=fill_color,
        fill=True,
        fill_color=fill_color,
        fill_opacity=0.75
    ).add_to(layer)


# ==================================================
# ADD AGENT LAYERS
# ==================================================

multiple_layer.add_to(m)
terrain_layer.add_to(m)
insar_layer.add_to(m)


# ==================================================
# LEGEND
# ==================================================

legend_html = """
<div style="
position: fixed;
bottom: 30px;
left: 30px;
width: 245px;
z-index: 9999;
background-color: white;
border: 2px solid black;
padding: 12px;
font-size: 13px;
">

<b>MAP LEGEND</b>

<hr>

<div>
<span style="
display:inline-block;
width:12px;
height:12px;
background:#d73027;
border-radius:50%;
margin-right:6px;
"></span>
Multiple spatial evidence
</div>

<br>

<div>
<span style="
display:inline-block;
width:12px;
height:12px;
background:#fc8d59;
border-radius:50%;
margin-right:6px;
"></span>
Terrain-dominant
</div>

<br>

<div>
<span style="
display:inline-block;
width:12px;
height:12px;
background:#4575b4;
border-radius:50%;
margin-right:6px;
"></span>
InSAR-dominant
</div>

<br>

<div>
<span style="
display:inline-block;
width:12px;
height:12px;
background:#000000;
margin-right:6px;
"></span>
GSI historical evidence
</div>

<br>

<span style="
display:inline-block;
width:18px;
height:3px;
background:black;
margin-right:6px;
"></span>
GSI approximate AOI boundary

</div>
"""

m.get_root().html.add_child(
    folium.Element(legend_html)
)


# ==================================================
# INFORMATION PANEL
# ==================================================

info_html = f"""
<div style="
position: fixed;
top: 10px;
right: 10px;
width: 300px;
z-index: 9999;
background: white;
border: 2px solid black;
padding: 13px;
font-size: 13px;
">

<b style="font-size:16px">
TIRUMALA LANDSLIDE DIGITAL TWIN
</b>

<hr>

<b>Study Area</b><br>
Tirumala Hills, Tirupati,
Andhra Pradesh

<br><br>

<b>InSAR Observation</b><br>
17 Aug 2026 → 29 Aug 2026

<br><br>

<b>Spatial Dataset</b><br>
2,650 quality-filtered observations

<br><br>

<b>Intelligent Agent</b><br>
Multiple spatial evidence: 473<br>
Terrain-dominant: 410<br>
InSAR-dominant: 410<br>
No high spatial evidence: 1,357

<br><br>

<b>GSI Historical Evidence</b><br>
48 documented incidences<br>
15 approximate Figure 3.2 locations

<br><br>

<b>Antecedent Rainfall</b><br>

Before 17 Aug:<br>
3-day: 2.3 mm<br>
7-day: 6.7 mm<br>
14-day: 20.0 mm

<br><br>

Before 29 Aug:<br>
3-day: 0.2 mm<br>
7-day: 9.3 mm<br>
14-day: 12.7 mm

<br><br>

<b>Interpretation</b><br>
The agent integrates terrain and InSAR
evidence to identify locations requiring
further monitoring or validation.

<br><br>

<i>
The output is not a calibrated landslide
probability or confirmed landslide detection.
</i>

</div>
"""

m.get_root().html.add_child(
    folium.Element(info_html)
)


# ==================================================
# LAYER CONTROL
# ==================================================

folium.LayerControl(
    collapsed=False
).add_to(m)


# ==================================================
# SAVE
# ==================================================

output_file.parent.mkdir(
    parents=True,
    exist_ok=True
)

m.save(output_file)


print("\nPRESENTATION-READY DIGITAL TWIN")
print("================================")

print(
    "Multiple spatial evidence:",
    (
        df["agent_monitoring_status"]
        == "Multiple spatial evidence"
    ).sum()
)

print(
    "Terrain-dominant:",
    (
        df["agent_monitoring_status"]
        == "Terrain-dominant evidence"
    ).sum()
)

print(
    "InSAR-dominant:",
    (
        df["agent_monitoring_status"]
        == "InSAR-dominant evidence"
    ).sum()
)

print(
    "GSI historical points:",
    len(gsi)
)

print("\nOutput:")
print(output_file)