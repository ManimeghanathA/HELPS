import math
import os
from pathlib import Path

import geopandas as gpd
import requests
from dotenv import load_dotenv


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_PATH = PROJECT_ROOT / ".env"

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_entire_region.geojson"
)

DATE = "2026-06-01"

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Sentinel2"
    / DATE
)

TILE_DIR = OUTPUT_DIR / "tiles"


# ============================================================
# CONFIGURATION
# ============================================================

TARGET_CRS = "EPSG:32643"

RESOLUTION = 10.0

# Keep comfortably below the API request limit
MAX_TILE_PIXELS = 2400

START_TIME = f"{DATE}T00:00:00Z"
END_TIME = f"{DATE}T23:59:59Z"

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/protocol/openid-connect/token"
)

PROCESS_URL = (
    "https://sh.dataspace.copernicus.eu/api/v1/process"
)


# ============================================================
# LOAD CREDENTIALS
# ============================================================

load_dotenv(ENV_PATH)

CLIENT_ID = os.getenv("CDSE_CLIENT_ID")
CLIENT_SECRET = os.getenv("CDSE_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError(
        "CDSE_CLIENT_ID or CDSE_CLIENT_SECRET missing from .env"
    )


# ============================================================
# AUTHENTICATION
# ============================================================

def get_access_token():

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=60,
    )

    response.raise_for_status()

    token = response.json().get("access_token")

    if not token:
        raise RuntimeError(
            "Authentication succeeded, but access token was not returned."
        )

    return token


# ============================================================
# LOAD AOI
# ============================================================

if not AOI_PATH.exists():
    raise FileNotFoundError(
        f"AOI not found:\n{AOI_PATH}"
    )

aoi = gpd.read_file(AOI_PATH)

if aoi.crs is None:
    raise ValueError(
        "AOI has no CRS."
    )

# Convert Bhadra to UTM 43N so all dimensions are in metres
aoi_utm = aoi.to_crs(TARGET_CRS)

minx, miny, maxx, maxy = aoi_utm.total_bounds


# ============================================================
# ALIGN BOUNDS TO 10 M GRID
# ============================================================

minx = math.floor(minx / RESOLUTION) * RESOLUTION
miny = math.floor(miny / RESOLUTION) * RESOLUTION

maxx = math.ceil(maxx / RESOLUTION) * RESOLUTION
maxy = math.ceil(maxy / RESOLUTION) * RESOLUTION


total_width = int(round((maxx - minx) / RESOLUTION))
total_height = int(round((maxy - miny) / RESOLUTION))


cols = math.ceil(total_width / MAX_TILE_PIXELS)
rows = math.ceil(total_height / MAX_TILE_PIXELS)


# ============================================================
# PRINT SUMMARY
# ============================================================

print("=" * 72)
print("BHADRA SENTINEL-2 L2A TILED DOWNLOAD")
print("=" * 72)

print(f"AOI file        : {AOI_PATH.name}")
print(f"Date            : {DATE}")
print(f"CRS             : {TARGET_CRS}")
print(f"Resolution      : {RESOLUTION:.0f} m")

print(
    f"Projected bounds: "
    f"{minx:.2f}, {miny:.2f}, {maxx:.2f}, {maxy:.2f}"
)

print(
    f"Full grid       : "
    f"{total_width} x {total_height} pixels"
)

print(
    f"Tile layout     : "
    f"{cols} columns x {rows} rows"
)

print(
    f"Total tiles     : "
    f"{cols * rows}"
)

print("=" * 72)


# ============================================================
# CREATE OUTPUT DIRECTORIES
# ============================================================

TILE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# EVALSCRIPT — 6 SPECTRAL BANDS
# ============================================================

SPECTRAL_EVALSCRIPT = """
//VERSION=3

function setup() {
    return {
        input: [{
            bands: [
                "B02",
                "B03",
                "B04",
                "B08",
                "B11",
                "B12"
            ],
            units: "REFLECTANCE"
        }],

        output: {
            id: "default",
            bands: 6,
            sampleType: "FLOAT32",
            nodataValue: -9999
        }
    };
}

function evaluatePixel(sample) {

    return [
        sample.B02,
        sample.B03,
        sample.B04,
        sample.B08,
        sample.B11,
        sample.B12
    ];
}
"""


# ============================================================
# EVALSCRIPT — SCL
# ============================================================

SCL_EVALSCRIPT = """
//VERSION=3

function setup() {
    return {
        input: [{
            bands: ["SCL"]
        }],

        output: {
            id: "default",
            bands: 1,
            sampleType: "UINT8",
            nodataValue: 0
        }
    };
}

function evaluatePixel(sample) {
    return [sample.SCL];
}
"""


# ============================================================
# PROCESS API REQUEST
# ============================================================

def download_process_tile(
    access_token,
    bbox,
    width,
    height,
    evalscript,
    output_path,
):

    payload = {

        "input": {

            "bounds": {

                "bbox": bbox,

                "properties": {
                    "crs": (
                        "http://www.opengis.net/"
                        "def/crs/EPSG/0/32643"
                    )
                },
            },

            "data": [
                {
                    "type": "sentinel-2-l2a",

                    "dataFilter": {

                        "timeRange": {
                            "from": START_TIME,
                            "to": END_TIME,
                        },

                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },

        "output": {

            "width": width,
            "height": height,

            "responses": [
                {
                    "identifier": "default",

                    "format": {
                        "type": "image/tiff"
                    },
                }
            ],
        },

        "evalscript": evalscript,
    }


    response = requests.post(
        PROCESS_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "image/tiff",
        },
        timeout=180,
    )


    if response.status_code != 200:

        print()
        print("PROCESS API ERROR")
        print("-" * 72)

        print(
            f"HTTP status: "
            f"{response.status_code}"
        )

        print(
            response.text
        )

        raise RuntimeError(
            "Sentinel Hub Process API request failed."
        )


    with open(
        output_path,
        "wb",
    ) as file:

        file.write(
            response.content
        )


# ============================================================
# AUTHENTICATE
# ============================================================

print()
print("Authenticating...")

access_token = get_access_token()

print("Authentication successful.")


# ============================================================
# GENERATE AND DOWNLOAD REQUEST TILES
# ============================================================

tile_number = 0


for row in range(rows):

    # Start from top of raster
    tile_top = maxy - (
        row
        * MAX_TILE_PIXELS
        * RESOLUTION
    )

    tile_bottom = max(
        miny,
        tile_top
        - (
            MAX_TILE_PIXELS
            * RESOLUTION
        )
    )


    tile_height = int(
        round(
            (tile_top - tile_bottom)
            / RESOLUTION
        )
    )


    for col in range(cols):

        tile_number += 1

        tile_left = minx + (
            col
            * MAX_TILE_PIXELS
            * RESOLUTION
        )

        tile_right = min(
            maxx,
            tile_left
            + (
                MAX_TILE_PIXELS
                * RESOLUTION
            )
        )


        tile_width = int(
            round(
                (tile_right - tile_left)
                / RESOLUTION
            )
        )


        bbox = [
            tile_left,
            tile_bottom,
            tile_right,
            tile_top,
        ]


        tile_name = (
            f"r{row + 1:02d}_"
            f"c{col + 1:02d}"
        )


        print()
        print("=" * 72)

        print(
            f"TILE {tile_number}/{rows * cols} "
            f"({tile_name})"
        )

        print(
            f"Size : "
            f"{tile_width} x "
            f"{tile_height}"
        )

        print(
            f"BBox : "
            f"{tile_left:.2f}, "
            f"{tile_bottom:.2f}, "
            f"{tile_right:.2f}, "
            f"{tile_top:.2f}"
        )


        # ----------------------------------------------------
        # SPECTRAL DATA
        # ----------------------------------------------------

        spectral_output = (
            TILE_DIR
            / f"{tile_name}_spectral.tif"
        )


        if spectral_output.exists():

            print(
                "Spectral tile already exists — skipping."
            )

        else:

            print(
                "Downloading spectral bands "
                "(B02 B03 B04 B08 B11 B12)..."
            )

            download_process_tile(
                access_token=access_token,
                bbox=bbox,
                width=tile_width,
                height=tile_height,
                evalscript=SPECTRAL_EVALSCRIPT,
                output_path=spectral_output,
            )

            print(
                f"Saved: {spectral_output.name}"
            )


        # ----------------------------------------------------
        # SCL DATA
        # ----------------------------------------------------

        scl_output = (
            TILE_DIR
            / f"{tile_name}_SCL.tif"
        )


        if scl_output.exists():

            print(
                "SCL tile already exists — skipping."
            )

        else:

            print(
                "Downloading SCL..."
            )

            download_process_tile(
                access_token=access_token,
                bbox=bbox,
                width=tile_width,
                height=tile_height,
                evalscript=SCL_EVALSCRIPT,
                output_path=scl_output,
            )

            print(
                f"Saved: {scl_output.name}"
            )


# ============================================================
# DONE
# ============================================================

print()
print("=" * 72)
print("BHADRA SENTINEL DOWNLOAD COMPLETE")
print("=" * 72)

print()
print(f"Date       : {DATE}")
print(f"Tiles      : {rows * cols}")
print(f"Raw folder : {TILE_DIR}")

print()

print(
    "Each spectral tile contains:"
)

print(
    "Band 1 = B02\n"
    "Band 2 = B03\n"
    "Band 3 = B04\n"
    "Band 4 = B08\n"
    "Band 5 = B11\n"
    "Band 6 = B12"
)

print()

print(
    "Each matching SCL file contains "
    "the Sentinel-2 Scene Classification Layer."
)