import os
import geopandas as gpd
import folium


# ============================================================
# PATHS
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

BHADRA_DIR = os.path.join(
    PROJECT_ROOT,
    "data",
    "raw",
    "Bhadra"
)

ENTIRE_PATH = os.path.join(
    BHADRA_DIR,
    "bhadra_entire_region.geojson"
)

VALID_PATH = os.path.join(
    BHADRA_DIR,
    "bhadra_valid_region.geojson"
)

INVALID_PATH = os.path.join(
    BHADRA_DIR,
    "bhadra_invalid_region.geojson"
)

OUTPUT_PATH = os.path.join(
    SCRIPT_DIR,
    "view_bhadra.html"
)


# ============================================================
# LOAD
# ============================================================

print("Loading Bhadra geometries...")

entire = gpd.read_file(ENTIRE_PATH)
valid = gpd.read_file(VALID_PATH)
invalid = gpd.read_file(INVALID_PATH)

print(f"Entire region : {len(entire)} feature(s)")
print(f"Valid region  : {len(valid)} feature(s)")
print(f"Invalid region: {len(invalid)} feature(s)")


# ============================================================
# CRS
# ============================================================

# Folium / Leaflet expects geographic coordinates.
entire = entire.to_crs(epsg=4326)
valid = valid.to_crs(epsg=4326)
invalid = invalid.to_crs(epsg=4326)


# ============================================================
# MAP CENTER
# ============================================================

minx, miny, maxx, maxy = entire.total_bounds

center_lat = (miny + maxy) / 2
center_lon = (minx + maxx) / 2


# ============================================================
# MAP
# ============================================================

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=10,
    tiles="OpenStreetMap",
    control_scale=True
)

map_name = m.get_name()


# ============================================================
# VALID REGION
# ============================================================

valid_layer = folium.GeoJson(
    valid,
    name="Valid Region",

    style_function=lambda feature: {
        "fillColor": "#22c55e",
        "color": "#15803d",
        "weight": 2,
        "fillOpacity": 0.35
    }
)

valid_layer.add_to(m)


# ============================================================
# INVALID REGION
# ============================================================

invalid_layer = folium.GeoJson(
    invalid,
    name="Invalid / Restricted Region",

    style_function=lambda feature: {
        "fillColor": "#ef4444",
        "color": "#b91c1c",
        "weight": 1.5,
        "fillOpacity": 0.30
    }
)

invalid_layer.add_to(m)


# ============================================================
# ENTIRE BHADRA REGION
#
# This is the IMPORTANT part.
#
# fillOpacity = 0.01 means:
#
# visually -> almost completely transparent
# technically -> clickable / hoverable
# ============================================================

entire_layer = folium.GeoJson(
    entire,
    name="Entire Bhadra Region",

    style_function=lambda feature: {
        "fillColor": "#2563eb",
        "color": "#8b5cf6",
        "weight": 3,
        "fillOpacity": 0.01
    }
)

entire_layer.add_to(m)


# ============================================================
# JAVASCRIPT HOVER BEHAVIOUR
# ============================================================

entire_name = entire_layer.get_name()

hover_script = f"""
<script>

var bhadraMap = {map_name};
var entireRegion = {entire_name};


// ------------------------------------------------------------
// ENABLE FRACTIONAL ZOOM
// ------------------------------------------------------------

bhadraMap.options.zoomSnap = 0.5;
bhadraMap.options.zoomDelta = 0.5;


// ------------------------------------------------------------
// Track current hover state
// ------------------------------------------------------------

var bhadraHoverActive = false;
var previousZoom = null;


// ------------------------------------------------------------
// Attach events to every polygon in the entire-region layer
// ------------------------------------------------------------

entireRegion.eachLayer(function(layer) {{

    layer.on({{

        // ====================================================
        // MOUSE ENTER
        // ====================================================

        mouseover: function(e) {{

            if (bhadraHoverActive) {{
                return;
            }}

            bhadraHoverActive = true;

            // Save current zoom
            previousZoom = bhadraMap.getZoom();


            // ------------------------------------------------
            // Highlight entire Bhadra boundary
            // ------------------------------------------------

            layer.setStyle({{
                color: "#2563eb",
                weight: 6,
                fillColor: "#3b82f6",
                fillOpacity: 0.08
            }});

            layer.bringToFront();


            // ------------------------------------------------
            // Zoom exactly +0.5
            // ------------------------------------------------

            bhadraMap.setZoom(
                previousZoom + 0.5,
                {{
                    animate: true,
                    duration: 0.35
                }}
            );
        }},


        // ====================================================
        // MOUSE LEAVE
        // ====================================================

        mouseout: function(e) {{

            bhadraHoverActive = false;


            // ------------------------------------------------
            // Restore boundary
            // ------------------------------------------------

            layer.setStyle({{
                color: "#8b5cf6",
                weight: 3,
                fillColor: "#2563eb",
                fillOpacity: 0.01
            }});


            // ------------------------------------------------
            // Restore original zoom
            // ------------------------------------------------

            if (previousZoom !== null) {{

                bhadraMap.setZoom(
                    previousZoom,
                    {{
                        animate: true,
                        duration: 0.35
                    }}
                );

                previousZoom = null;
            }}
        }}

    }});

}});

</script>
"""

m.get_root().html.add_child(
    folium.Element(hover_script)
)


# ============================================================
# CLICK INFORMATION
# ============================================================

folium.GeoJson(
    entire,
    name="Bhadra Information",
    style_function=lambda feature: {
        "fillOpacity": 0,
        "weight": 0
    },
    tooltip=folium.Tooltip(
        "Bhadra Entire Region"
    )
).add_to(m)


# ============================================================
# LEGEND
# ============================================================

legend_html = """
<div style="
    position: fixed;
    bottom: 30px;
    left: 30px;
    z-index: 9999;

    background: rgba(20,20,20,0.95);
    color: white;

    padding: 16px 20px;
    border-radius: 8px;

    font-family: Arial, sans-serif;
    font-size: 14px;

    box-shadow: 0 2px 10px rgba(0,0,0,0.4);
">

<div style="
    font-size:17px;
    font-weight:bold;
    margin-bottom:14px;
">
Bhadra HELPSs Region
</div>


<div style="margin-bottom:10px;">
    <span style="
        display:inline-block;
        width:18px;
        height:12px;
        background:#22c55e;
        margin-right:8px;
    "></span>
    Valid Region
</div>


<div style="margin-bottom:10px;">
    <span style="
        display:inline-block;
        width:18px;
        height:12px;
        background:#ef4444;
        margin-right:8px;
    "></span>
    Invalid / Restricted
</div>


<div>
    <span style="
        display:inline-block;
        width:18px;
        height:3px;
        background:#8b5cf6;
        margin-right:8px;
        vertical-align:middle;
    "></span>
    Entire Bhadra Region
</div>

</div>
"""

m.get_root().html.add_child(
    folium.Element(legend_html)
)


# ============================================================
# LAYER CONTROL
# ============================================================

folium.LayerControl(
    collapsed=False
).add_to(m)


# ============================================================
# FIT MAP TO BHADRA
# ============================================================

m.fit_bounds(
    [
        [miny, minx],
        [maxy, maxx]
    ]
)


# ============================================================
# SAVE
# ============================================================

m.save(OUTPUT_PATH)


print()
print("=" * 60)
print("BHADRA MAP CREATED")
print("=" * 60)
print()
print(f"Output: {OUTPUT_PATH}")
print()