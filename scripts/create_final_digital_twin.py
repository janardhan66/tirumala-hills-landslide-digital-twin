import pandas as pd
import geopandas as gpd
import folium
import rasterio
from pathlib import Path
from pyproj import Transformer

PROJECT = Path(__file__).resolve().parents[1]

agent_file = (
    PROJECT
    / "data"
    / "features"
    / "tirumala_final_agent_evidence.csv"
)

aoi_file = (
    PROJECT
    / "data"
    / "raw"
    / "aoi"
    / "tirumala_hills_gsi_map_aoi.geojson"
)

inventory_file = (
    PROJECT
    / "data"
    / "raw"
    / "inventory"
    / "tirumala_gsi_fig32_map_derived_inventory.csv"
)

rainfall_file = (
    PROJECT
    / "data"
    / "processed"
    / "rainfall"
    / "tirumala"
    / "tirumala_rainfall_features_20260801_20260829.csv"
)

reference_raster = (
    PROJECT
    / "data"
    / "processed"
    / "dinsar"
    / "tirumala"
    / "gsi_aoi"
    / "tirumala_temporal_los_change_05_17_to_17_29.tif"
)

output_dir = PROJECT / "results" / "digital_twin"
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "tirumala_final_digital_twin.html"

print("\nFINAL DIGITAL TWIN")
print("===================")

# ------------------------------------------------
# Load agent evidence
# ------------------------------------------------
df = pd.read_csv(agent_file)

print("Agent observations:", len(df))

# ------------------------------------------------
# Load AOI
# ------------------------------------------------
aoi = gpd.read_file(aoi_file)

# Calculate centroid correctly in projected CRS
aoi_projected = aoi.to_crs("EPSG:32644")
center_projected = aoi_projected.geometry.centroid
center_wgs84 = center_projected.to_crs("EPSG:4326")

center_lat = center_wgs84.y.mean()
center_lon = center_wgs84.x.mean()

print("Map center:", center_lat, center_lon)

# ------------------------------------------------
# Load GSI historical points
# ------------------------------------------------
inventory = pd.read_csv(inventory_file)

print("GSI historical points:", len(inventory))

# ------------------------------------------------
# Load rainfall
# ------------------------------------------------
rainfall = pd.read_csv(rainfall_file)

rainfall["date"] = pd.to_datetime(rainfall["date"])

latest = rainfall.iloc[-1]

# Correct rainfall column names
latest_daily = latest["rainfall_mean_mm"]
latest_3day = latest["rainfall_3day_mm"]
latest_7day = latest["rainfall_7day_mm"]
latest_14day = latest["rainfall_14day_mm"]

print(
    "Latest rainfall:",
    latest_daily,
    "mm"
)

# ------------------------------------------------
# Create map
# ------------------------------------------------
m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=12,
    tiles=None,
    control_scale=True
)
# ------------------------------------------------
# AOI boundary
# ------------------------------------------------
aoi_wgs84 = aoi.to_crs("EPSG:4326")

folium.GeoJson(
    aoi_wgs84,
    name="GSI Figure 3.2 approximate AOI",
    style_function=lambda feature: {
        "color": "black",
        "weight": 3,
        "fill": False
    }
).add_to(m)

# ------------------------------------------------
# Evidence colors
# ------------------------------------------------
colors = {
    "Multiple spatial + temporal evidence": "#d73027",
    "Multiple spatial evidence": "#fc8d59",
    "InSAR + temporal evidence": "#4575b4",
    "InSAR monitoring evidence": "#74add1",
    "Terrain + temporal evidence": "#fdae61",
    "Terrain evidence": "#fee090",
    "Temporal-change evidence": "#8073ac",
    "No high spatial evidence": "#bdbdbd"
}

# ------------------------------------------------
# Raster coordinate transformer
# ------------------------------------------------
transformer = Transformer.from_crs(
    "EPSG:32644",
    "EPSG:4326",
    always_xy=True
)

# ------------------------------------------------
# Add agent evidence
# ------------------------------------------------
agent_group = folium.FeatureGroup(
    name="Intelligent Agent Evidence"
)

with rasterio.open(reference_raster) as src:

    transform = src.transform

    print("Reference raster:")
    print("  CRS:", src.crs)
    print("  Shape:", src.height, "x", src.width)

    plotted = 0
    skipped = 0

    for _, row in df.iterrows():

        category = row["final_agent_evidence"]

        # Skip observations without usable raster coordinates
        if pd.isna(row["row"]) or pd.isna(row["col"]):
            skipped += 1
            continue

        raster_row = int(row["row"])
        raster_col = int(row["col"])

        # Convert raster row/column to projected coordinates
        x, y = rasterio.transform.xy(
            transform,
            raster_row,
            raster_col,
            offset="center"
        )

        # Convert UTM -> latitude/longitude
        lon, lat = transformer.transform(x, y)

        color = colors.get(
            category,
            "#bdbdbd"
        )

        popup_text = (
            f"<b>Agent Evidence</b><br>"
            f"Category: {category}<br>"
            f"Raster row: {raster_row}<br>"
            f"Raster column: {raster_col}"
        )

        folium.CircleMarker(
            location=[lat, lon],
            radius=3,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            weight=1,
            popup=folium.Popup(
                popup_text,
                max_width=320
            )
        ).add_to(agent_group)

        plotted += 1

print("Agent points plotted:", plotted)
print("Agent points skipped:", skipped)

agent_group.add_to(m)

# ------------------------------------------------
# Add GSI historical evidence
# ------------------------------------------------
historical_group = folium.FeatureGroup(
    name="GSI Figure 3.2 map-derived historical evidence"
)

for _, row in inventory.iterrows():

    popup_text = (
        f"<b>{row['inventory_id']}</b><br>"
        f"Source: GSI Figure 3.2<br>"
        f"Coordinate quality: map-derived approximate<br>"
        f"Latitude: {row['latitude']:.6f}<br>"
        f"Longitude: {row['longitude']:.6f}"
    )

    folium.CircleMarker(
        location=[
            row["latitude"],
            row["longitude"]
        ],
        radius=5,
        color="black",
        fill=True,
        fill_color="black",
        fill_opacity=0.9,
        popup=folium.Popup(
            popup_text,
            max_width=300
        )
    ).add_to(historical_group)

historical_group.add_to(m)

# ------------------------------------------------
# Evidence counts
# ------------------------------------------------
counts = df["final_agent_evidence"].value_counts()

temporal_available = int(
    df["temporal_available"].sum()
)

temporal_unavailable = int(
    (~df["temporal_available"]).sum()
)

# ------------------------------------------------
# Information panel
# ------------------------------------------------
panel = f"""
<div style="
position: fixed;
top: 20px;
right: 20px;
width: 350px;
background-color: white;
border: 2px solid black;
z-index: 9999;
padding: 15px;
font-size: 13px;
box-shadow: 0 0 10px rgba(0,0,0,0.3);
">

<h3 style="margin-top:0;">
Tirumala Hills Digital Twin
</h3>

<b>Case study:</b><br>
Tirumala Hills, Tirupati, Andhra Pradesh

<hr>

<b>Spatial observations:</b>
{len(df)}

<br><br>

<b>Temporal InSAR:</b><br>
05–17 Aug 2026<br>
17–29 Aug 2026

<br><br>

<b>Temporal evidence available:</b>
{temporal_available}

<br>

<b>Temporal evidence unavailable:</b>
{temporal_unavailable}

<hr>

<b>Agent Evidence</b><br><br>

Multiple spatial + temporal:
{counts.get("Multiple spatial + temporal evidence", 0)}

<br>

Multiple spatial:
{counts.get("Multiple spatial evidence", 0)}

<br>

InSAR + temporal:
{counts.get("InSAR + temporal evidence", 0)}

<br>

Terrain + temporal:
{counts.get("Terrain + temporal evidence", 0)}

<br>

Temporal-change:
{counts.get("Temporal-change evidence", 0)}

<br>

Terrain:
{counts.get("Terrain evidence", 0)}

<br>

InSAR:
{counts.get("InSAR monitoring evidence", 0)}

<br>

No high spatial evidence:
{counts.get("No high spatial evidence", 0)}

<hr>

<b>Rainfall Context</b><br>

Latest date:
{latest["date"].strftime("%d %b %Y")}

<br>

Daily rainfall:
{latest_daily:.1f} mm

<br>

3-day:
{latest_3day:.1f} mm

<br>

7-day:
{latest_7day:.1f} mm

<br>

14-day:
{latest_14day:.1f} mm

<hr>

<b>Interpretation</b><br>

The intelligent agent integrates terrain,
InSAR monitoring and temporal-change evidence.
The categories represent explainable evidence
integration and are not calibrated landslide
probabilities.

<br><br>

<b>Historical data note:</b><br>

Black points represent map-derived approximate
locations interpreted from GSI Figure 3.2.
They are not exact official GSI coordinates.

</div>
"""

m.get_root().html.add_child(
    folium.Element(panel)
)

# ------------------------------------------------
# Legend
# ------------------------------------------------
legend = """
<div style="
position: fixed;
bottom: 30px;
left: 30px;
width: 285px;
background-color: white;
border: 2px solid black;
z-index: 9999;
padding: 10px;
font-size: 12px;
">

<b>Agent Evidence Legend</b><br><br>

<span style="color:#d73027;">●</span>
Multiple spatial + temporal<br>

<span style="color:#fc8d59;">●</span>
Multiple spatial<br>

<span style="color:#4575b4;">●</span>
InSAR + temporal<br>

<span style="color:#74add1;">●</span>
InSAR monitoring<br>

<span style="color:#fdae61;">●</span>
Terrain + temporal<br>

<span style="color:#fee090;">●</span>
Terrain<br>

<span style="color:#8073ac;">●</span>
Temporal-change<br>

<span style="color:#bdbdbd;">●</span>
No high spatial evidence<br>

<br>

● Black = GSI Figure 3.2
map-derived historical point

</div>
"""

m.get_root().html.add_child(
    folium.Element(legend)
)

# ------------------------------------------------
# Layer control
# ------------------------------------------------
folium.LayerControl().add_to(m)

# ------------------------------------------------
# Save
# ------------------------------------------------
m.save(output_file)

print("\nDigital Twin created successfully.")
print("Output:")
print(output_file)