import geopandas as gpd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_valid_region.geojson"
)

aoi = gpd.read_file(AOI_PATH)

print("=" * 60)
print("BHADRA VALID REGION")
print("=" * 60)

print(f"CRS: {aoi.crs}")
print(f"Features: {len(aoi)}")

print("\nBounds:")
minx, miny, maxx, maxy = aoi.total_bounds

print(f"West  : {minx}")
print(f"South : {miny}")
print(f"East  : {maxx}")
print(f"North : {maxy}")

print("\nArea:")
print(f"Area: {aoi.to_crs(32643).area.sum() / 1_000_000:.6f} km²")