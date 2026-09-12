import geopandas as gpd
import matplotlib.pyplot as plt

path = "data/processed/aoi/bhadra_wls_osm.geojson"

gdf = gpd.read_file(path)

gdf.plot()

plt.title("Bhadra AOI")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.show()