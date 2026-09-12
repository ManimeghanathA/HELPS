from pathlib import Path
import json
import requests
import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_entire_region.geojson"
)


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

START_DATE = "2026-06-01"
END_DATE = "2026-08-31"

MAX_CLOUD = 30
LIMIT = 50


# --------------------------------------------------
# LOAD AOI
# --------------------------------------------------

aoi = gpd.read_file(AOI_PATH).to_crs("EPSG:4326")

minx, miny, maxx, maxy = aoi.total_bounds

bbox_wkt = (
    f"POLYGON(("
    f"{minx} {miny},"
    f"{maxx} {miny},"
    f"{maxx} {maxy},"
    f"{minx} {maxy},"
    f"{minx} {miny}"
    f"))"
)

# --------------------------------------------------
# CDSE ODATA SEARCH
# --------------------------------------------------

url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"

filter_query = (
    "Collection/Name eq 'SENTINEL-2' "
    "and contains(Name,'MSIL2A') "
    f"and ContentDate/Start ge {START_DATE}T00:00:00.000Z "
    f"and ContentDate/Start le {END_DATE}T23:59:59.999Z "
    f"and OData.CSC.Intersects("
    f"area=geography'SRID=4326;{bbox_wkt}')"
)

params = {
    "$filter": filter_query,
    "$expand": "Attributes",
    "$orderby": "ContentDate/Start desc",
    "$top": LIMIT,
}

response = requests.get(
    url,
    params=params,
    timeout=60,
)

response.raise_for_status()

products = response.json().get("value", [])


print("=" * 80)
print("BHADRA SENTINEL-2 LEVEL-2A SEARCH")
print("=" * 80)

print(f"Date range : {START_DATE} → {END_DATE}")
print(f"Products   : {len(products)}")

print()

for i, product in enumerate(products, start=1):

    name = product.get("Name")
    product_id = product.get("Id")

    content_date = product.get("ContentDate", {})
    acquisition = content_date.get("Start")

    cloud_cover = None

    for attribute in product.get("Attributes", []):
        if attribute.get("Name") == "cloudCover":
            cloud_cover = attribute.get("Value")
            break

    print(f"[{i}]")
    print(f"Name  : {name}")
    print(f"Date  : {acquisition}")
    print(f"Cloud : {cloud_cover}%")
    print(f"ID    : {product_id}")
    print("-" * 80)