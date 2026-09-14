"""Run established algorithms and fail closed on final audit violations."""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from shapely import make_valid

from scripts.processing.open_land_detector import generate_possible_open_mask
from scripts.processing.candidate_polygonization import polygonize_open_mask
from scripts.processing.building_subtraction import subtract_buildings
from scripts.processing.candidate_geometry_filter import measure_candidate_geometry, passes_geometry_gate
from scripts.processing.operational_zone_extraction import extract_operational_zones
from scripts.processing.maximum_clearance import measure_maximum_clearance

BUILDING_OVERLAP_TOLERANCE_M2 = 1e-4


def polygons(frame):
    frame = frame.copy()
    frame.geometry = frame.geometry.map(make_valid)
    frame = frame.explode(index_parts=False).reset_index(drop=True)
    return frame[frame.geom_type.isin(['Polygon', 'MultiPolygon']) & ~frame.is_empty].copy()


def save_layer(frame, path, layer):
    frame.to_file(path, layer=layer, driver='GPKG')


def audit(zones, buildings, state, scl, transform, log=print):
    mask = rasterize([(g, 1) for g in zones.geometry], out_shape=state.shape,
                     transform=transform, dtype='uint8') if len(zones) else np.zeros_like(state)
    unknown = int(np.count_nonzero((mask == 1) & (state == 255)))
    clouds = int(np.count_nonzero((mask == 1) & np.isin(scl, [3,8,9,10])))
    overlap_pairs = 0
    building_overlap = 0.0
    union = buildings.geometry.union_all()
    index = zones.sindex
    for i, geom in enumerate(zones.geometry):
        if i % 500 == 0:
            log(f'Final topology audit: {i:,} / {len(zones):,} zones')
        building_overlap += geom.intersection(union).area
        for j in index.query(geom, predicate='intersects'):
            if j > i and geom.intersection(zones.geometry.iloc[j]).area > 1e-6:
                overlap_pairs += 1
    valid = bool(zones.is_valid.all() and not zones.is_empty.any())
    thresholds = all(passes_geometry_gate(g) for g in zones.geometry)
    thresholds = thresholds and bool((zones['max_clear_diameter_m'] >= 30).all())
    stored = bool(np.allclose(zones.geometry.area, zones['area_m2'], atol=1e-6, rtol=0))
    result = dict(unknown_overlap_pixels=unknown, cloud_overlap_pixels=clouds,
                  zone_overlap_pairs=overlap_pairs, building_overlap_m2=building_overlap,
                  valid_geometries=valid, thresholds_passed=thresholds,
                  unique_ids=bool(zones.zone_id.is_unique), stored_areas_consistent=stored)
    result['passed'] = bool(not unknown and not clouds and not overlap_pairs and
                            building_overlap <= BUILDING_OVERLAP_TOLERANCE_M2 and
                            valid and thresholds and stored and result['unique_ids'])
    if not result['passed']:
        raise ValueError(f'Final audit failed: {result}')
    return result


def render_map(spectral_path, aoi, zones, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from rasterio.plot import plotting_extent
    with rasterio.open(spectral_path) as src:
        scale = min(1, 1600 / max(src.width, src.height))
        rgb = src.read([3,2,1], out_shape=(3,max(1,int(src.height*scale)),max(1,int(src.width*scale))))
        extent, crs = plotting_extent(src), src.crs
    rgb = np.moveaxis(rgb, 0, -1)
    rgb = np.clip(np.nan_to_num(rgb) / .3, 0, 1)
    fig, ax = plt.subplots(figsize=(10, 10), facecolor='#121918')
    ax.imshow(rgb, extent=extent)
    aoi.to_crs(crs).boundary.plot(ax=ax, color='white', linewidth=.8)
    if len(zones):
        zones.boundary.plot(ax=ax, color='#20efbd', linewidth=.45)
    ax.set_xlim(extent[:2]); ax.set_ylim(extent[2:])
    ax.set_axis_off()
    fig.savefig(output, dpi=160, bbox_inches='tight', pad_inches=0)
    plt.close(fig)


def process_inputs(spectral_path, scl_path, buildings, aoi, output, name, log=print):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    intermediates = output/'archive'
    intermediates.mkdir(exist_ok=True)
    log('Classifying possible-open terrain; applying 30 m cloud buffer')
    with rasterio.open(spectral_path) as spectral, rasterio.open(scl_path) as scl_src:
        if spectral.crs is None or not spectral.crs.is_projected or not np.allclose(spectral.res, (10,10)):
            raise ValueError('Processing requires projected 10 m imagery.')
        scl = scl_src.read(1)
        if not np.any(np.isin(scl, [4,5,6])):
            raise ValueError('No observable Sentinel pixels for this AOI/date; choose another date.')
    generate_possible_open_mask(spectral_path, scl_path, intermediates/'possible_open.tif', cloud_buffer_pixels=3)
    with rasterio.open(intermediates/'possible_open.tif') as src:
        state, transform, crs = src.read(1), src.transform, src.crs
    log('Polygonizing connected open terrain')
    components = polygonize_open_mask(state, transform, crs)
    # Eight-connected raster components can have point-touch self-intersections.
    # Preserve the historical difference behavior; do not split them before subtraction.
    save_layer(components, intermediates/'stages.gpkg', 'open_components')
    buildings = polygons(buildings.to_crs(crs))
    log(f'Subtracting {len(buildings):,} building footprints')
    fragments = subtract_buildings(components, buildings, progress=log)
    save_layer(fragments, intermediates/'stages.gpkg', 'building_cleaned')
    candidates = fragments[[passes_geometry_gate(g) for g in fragments.geometry]].copy() if len(fragments) else fragments.copy()
    save_layer(candidates, intermediates/'stages.gpkg', 'candidates')
    log(f'Extracting clearance zones from {len(candidates):,} candidates')
    rows, centers = [], []
    raw_count = geometry_count = 0
    for parent, geom in enumerate(candidates.geometry, 1):
        if parent % 500 == 0:
            log(f'Clearance and MIC: {parent:,} / {len(candidates):,} parents')
        for zone in extract_operational_zones(geom, clearance_radius_m=15):
            raw_count += 1
            if not passes_geometry_gate(zone):
                continue
            geometry_count += 1
            mic = measure_maximum_clearance(zone, tolerance_m=.5)
            if mic['diameter_m'] < 30:
                continue
            zone_id = f'{name}_ZONE_{len(rows)+1:06d}'
            rows.append(dict(zone_id=zone_id, parent_candidate_id=parent,
                             **measure_candidate_geometry(zone), max_clear_diameter_m=mic['diameter_m'],
                             max_clear_radius_m=mic['radius_m'], geometry=zone))
            centers.append(dict(zone_id=zone_id, geometry=mic['center']))
    columns = ['zone_id','parent_candidate_id','area_m2','length_m','width_m',
               'max_clear_diameter_m','max_clear_radius_m','geometry']
    zones = gpd.GeoDataFrame(rows, columns=columns, geometry='geometry', crs=crs)
    for col in ['area_m2','length_m','width_m','max_clear_diameter_m','max_clear_radius_m']:
        zones[col] = zones[col].astype(float)
    log('Auditing geometry, building overlap, cloud/UNKNOWN and zone overlap')
    audits = audit(zones, buildings, state, scl, transform, log)
    save_layer(zones, output/'final_zones.gpkg', 'final_open_land_zones')
    if centers:
        save_layer(gpd.GeoDataFrame(centers, geometry='geometry', crs=crs), output/'final_zones.gpkg', 'maximum_clearance_centers')
    (output/'final_zones.geojson').write_text(zones.to_crs(4326).to_json(), encoding='utf-8')
    log('Rendering polygons over Sentinel imagery')
    render_map(spectral_path, aoi, zones, output/'final_zones.png')
    summary = dict(open_pixels=int(np.count_nonzero(state == 1)),
                   unknown_pixels=int(np.count_nonzero((state == 255) & (scl != 0))),
                   aoi_pixels=int(np.count_nonzero(scl != 0)),
                   open_components=len(components), building_cleaned_fragments=len(fragments),
                   parent_candidates=len(candidates), raw_operational_zones=raw_count,
                   geometry_passed_zones=geometry_count, final_zones=len(zones),
                   final_area_km2=float(zones.geometry.area.sum()/1e6), audits=audits)
    (output/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    log(json.dumps(summary, indent=2))
    return summary
