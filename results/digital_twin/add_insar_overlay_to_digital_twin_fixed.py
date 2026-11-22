from pathlib import Path
import base64
import re

BASE_DIR = Path(__file__).resolve().parent.parent
DIGITAL_TWIN_DIR = BASE_DIR / "results" / "digital_twin"
BACKUP_FILE = DIGITAL_TWIN_DIR / "tirumala_final_digital_twin_backup.html"
HTML_FILE = DIGITAL_TWIN_DIR / "tirumala_final_digital_twin.html"
OVERLAY_FILE = DIGITAL_TWIN_DIR / "tirumala_insar_los_overlay.png"

WEST, SOUTH = 79.3292463736464, 13.63915149344645
EAST, NORTH = 79.42062161334384, 13.701210154056298

if not BACKUP_FILE.is_file():
    raise FileNotFoundError(f"Clean HTML backup not found: {BACKUP_FILE}")
if not OVERLAY_FILE.is_file():
    raise FileNotFoundError(f"InSAR overlay PNG not found: {OVERLAY_FILE}")

# Always rebuild from the clean backup: rerunning this script is safe.
html = BACKUP_FILE.read_text(encoding="utf-8")
image_data = base64.b64encode(OVERLAY_FILE.read_bytes()).decode("ascii")
image_url = f"data:image/png;base64,{image_data}"

map_match = re.search(r"var\s+(map_[A-Za-z0-9_]+)\s*=\s*L\.map\(", html)
if not map_match:
    raise RuntimeError("Could not find the Folium Leaflet map initialization.")
map_variable = map_match.group(1)

if "tile.openstreetmap.org/{z}/{x}/{y}.png" not in html:
    map_init = re.search(
        rf"var\s+{re.escape(map_variable)}\s*=\s*L\.map\([\s\S]*?\n\s*\);",
        html,
    )
    if not map_init:
        raise RuntimeError("Could not locate the end of Leaflet map initialization.")
    tile_code = (
        f"\nL.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{\n"
        "    maxZoom: 19,\n"
        "    attribution: '&copy; OpenStreetMap contributors'\n"
        f"}}).addTo({map_variable});\n"
    )
    html = html[:map_init.end()] + tile_code + html[map_init.end():]

if "TIRUMALA_INSAR_OVERLAY_ADDED" in html:
    raise RuntimeError("Overlay marker already exists in backup; restore a clean backup first.")

dictionary_match = re.search(r"var\s+layer_control_[A-Za-z0-9_]+_layers\s*=\s*\{", html)
if not dictionary_match:
    raise RuntimeError("Could not find the Leaflet layer-control dictionary.")
insert_at = html.rfind("\n", 0, dictionary_match.start()) + 1

overlay_code = f'''// TIRUMALA_INSAR_OVERLAY_ADDED
var tirumalaInsarOverlay = L.imageOverlay(
    "{image_url}",
    [[{SOUTH}, {WEST}], [{NORTH}, {EAST}]],
    {{ opacity: 0.78, interactive: false,
      alt: "Tirumala Hills InSAR line-of-sight displacement" }}
);
var tirumalaInsarLegend = L.control({{ position: "bottomleft" }});
tirumalaInsarLegend.onAdd = function(map) {{
    var div = L.DomUtil.create("div", "info legend");
    div.style.background = "white";
    div.style.padding = "8px 10px";
    div.style.border = "1px solid #888";
    div.style.borderRadius = "4px";
    div.style.lineHeight = "1.5";
    div.innerHTML = "<b>InSAR LOS displacement</b><br>" +
        "Display range: -39.70 to -10.54 mm<br>" +
        "<span style='color:#0000ff'>Blue</span> to " +
        "<span style='color:#ff0000'>Red</span><br>" +
        "<small>Not a landslide probability map</small>";
    return div;
}};
tirumalaInsarLegend.addTo({map_variable});

'''
html = html[:insert_at] + overlay_code + html[insert_at:]

overlays_match = re.search(r"overlays\s*:\s*\{", html)
if not overlays_match:
    raise RuntimeError("Could not find overlays object in the layer-control dictionary.")
html = (
    html[:overlays_match.end()]
    + '\n                    "InSAR LOS Displacement (80 m)": tirumalaInsarOverlay,'
    + html[overlays_match.end():]
)

options_match = re.search(
    r'("position"\s*:\s*)"topright"(,\s*\n\s*"collapsed"\s*:\s*)true', html
)
if not options_match:
    raise RuntimeError("Could not find the expected layer-control position/options.")
html = (
    html[:options_match.start()]
    + options_match.group(1) + '"bottomright"'
    + options_match.group(2) + 'false'
    + html[options_match.end():]
)

style = """\n<style>\n/* Keep Leaflet layer selector clear of the fixed information card. */\n.leaflet-control-layers { z-index: 1200 !important; }\n.leaflet-control-layers-expanded { max-height: 42vh; overflow-y: auto; background: #fff; }\n.leaflet-control-layers-list { display: block; visibility: visible; }\n.leaflet-control-layers label { display: block; margin: 4px 0; }\n</style>\n"""
html = html.replace("</head>", style + "</head>", 1)

# Validate the generated artifact before writing it.
assert html.index("var tirumalaInsarOverlay = L.imageOverlay") < html.index("var layer_control_")
assert '"InSAR LOS Displacement (80 m)": tirumalaInsarOverlay' in html
assert '"position": "bottomright"' in html and '"collapsed": false' in html
HTML_FILE.write_text(html, encoding="utf-8")
print("Updated:", HTML_FILE)
print("Layer control is bottom-right and expanded by default.")
print("InSAR overlay is declared before the layer-control dictionary.")
