"""Read-only comparison of a reported zone against its actual source pixels."""
import json
import sys
from pathlib import Path
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds, Window
from shapely.geometry import mapping

ROOT = Path(__file__).resolve().parents[3]
DRAFT = ROOT / 'HELPS - draft'
sys.path.insert(0, str(DRAFT))
from scripts.processing.open_land_detector import safe_normalized_difference, classify_open_pixels


def main(zone_id):
    base = DRAFT / 'data/processed/Bhadra'
    imagery = base / 'sentinel2/2026-06-01'
    zones = gpd.read_file(imagery / 'bhadra_final_open_land_zones.gpkg', layer='final_open_land_zones')
    zone = zones[zones.zone_id == zone_id].copy()
    if len(zone) != 1:
        raise ValueError(f'Expected exactly one zone: {zone_id}')
    geom = zone.geometry.iloc[0]
    bounds = geom.buffer(100).bounds
    with rasterio.open(imagery / 'bhadra_spectral.tif') as src:
        window = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
        window = window.intersection(Window(0, 0, src.width, src.height))
        bands = src.read(window=window)
        transform = src.window_transform(window)
        crs = src.crs
    with rasterio.open(imagery / 'bhadra_scl.tif') as src:
        scl = src.read(1, window=window)
    ndvi = safe_normalized_difference(bands[3], bands[2])
    mndwi = safe_normalized_difference(bands[1], bands[4])
    state = classify_open_pixels(scl, ndvi, mndwi)
    inside = geometry_mask([geom], out_shape=scl.shape, transform=transform, invert=True)
    bbox4326 = zone.to_crs(4326).geometry.iloc[0].buffer(.002).bounds
    obstacles = {}
    for name, path, layer in [
        ('osm_buildings', base/'osm/bhadra_osm_context.gpkg', 'buildings'),
        ('overture_buildings', base/'buildings/bhadra_overture_buildings.geojson', None),
    ]:
        frame = gpd.read_file(path, bbox=bbox4326, **({'layer':layer} if layer else {})).to_crs(crs)
        obstacles[name] = frame[frame.intersects(geom.buffer(100))].copy()
    def histogram(values):
        keys, counts = np.unique(values, return_counts=True)
        return {int(k): int(v) for k,v in zip(keys, counts)}
    finite = inside & np.isfinite(ndvi)
    result = {
        'zone_id': zone_id, 'area_m2': float(geom.area),
        'clear_diameter_m': float(zone.max_clear_diameter_m.iloc[0]),
        'geometry_wgs84': mapping(zone.to_crs(4326).geometry.iloc[0]),
        'source_date': '2026-06-01', 'source_grid_m': 10,
        'pixel_centres_inside': int(inside.sum()), 'scl_inside': histogram(scl[inside]),
        'reclassified_states_inside': histogram(state[inside]),
        'ndvi_inside': {'min': float(ndvi[finite].min()), 'median': float(np.median(ndvi[finite])), 'max': float(ndvi[finite].max())},
        'mapped_obstacles': {name: {'within_100m_count':len(frame),
            'intersection_area_m2':float(frame.intersection(geom).area.sum())} for name,frame in obstacles.items()},
        'available_osm_layers':gpd.list_layers(base/'osm/bhadra_osm_context.gpkg')['name'].tolist(),
    }
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from rasterio.plot import plotting_extent
    extent = plotting_extent(bands[0], transform)
    rgb = np.clip(np.moveaxis(bands[[2,1,0]],0,-1)/.3,0,1)
    fig, axes = plt.subplots(2,2,figsize=(12,11),constrained_layout=True)
    axes[0,0].imshow(rgb,extent=extent)
    axes[0,0].set_title('June 1 Sentinel RGB + stored candidate outline')
    axes[0,1].imshow(rgb,extent=extent)
    for name, frame in obstacles.items():
        if not frame.empty:
            frame.boundary.plot(ax=axes[0,1],color='#ff5353',linewidth=1.8)
    axes[0,1].set_title('Red: available mapped building footprints')
    image=axes[1,0].imshow(ndvi,extent=extent,cmap='RdYlGn',vmin=-.2,vmax=.8,interpolation='nearest')
    fig.colorbar(image,ax=axes[1,0],shrink=.7,label='NDVI')
    axes[1,0].set_title('Actual NDVI grid (no added detail)')
    colors=['#222222','#777777','#444444','#553355','#287b3c','#c8a877','#226bb5','#bbbbbb','#cccccc','#eeeeee','#aaccff','#ffffff']
    cmap=ListedColormap(colors)
    axes[1,1].imshow(scl,extent=extent,cmap=cmap,norm=BoundaryNorm(np.arange(-.5,12.5),12),interpolation='nearest')
    axes[1,1].set_title('SCL: tan = class 5; green = class 4; blue = water')
    for ax in axes.flat:
        zone.boundary.plot(ax=ax,color='#00d8cd',linewidth=1.8)
        ax.set_xlim(extent[:2]); ax.set_ylim(extent[2:]); ax.set_aspect('equal')
        ax.ticklabel_format(useOffset=False,style='plain')
        ax.set_xlabel('UTM easting (m)'); ax.set_ylabel('UTM northing (m)')
    fig.suptitle(f'{zone_id} — inspect source evidence, not just polygon validity',fontsize=16)
    out = Path(__file__).parent
    fig.savefig(out/f'{zone_id}-source-comparison.png',dpi=150)
    plt.close(fig)
    (out/f'{zone_id}-evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='geometry_wgs84'},indent=2))


if __name__ == '__main__':
    main(sys.argv[1])
