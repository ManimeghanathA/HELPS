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


def polygons(frame):
    if frame is None or len(frame) == 0:
        return gpd.GeoDataFrame(geometry=[], crs=getattr(frame, 'crs', None))
    if isinstance(frame, gpd.GeoSeries):
        crs = frame.crs
        frame = frame.to_frame('geometry')
        frame.crs = crs
    elif not isinstance(frame, gpd.GeoDataFrame):
        frame = gpd.GeoDataFrame(geometry=frame)
    frame = frame.copy()
    frame['geometry'] = frame.geometry.map(make_valid)
    frame = frame.explode(index_parts=False).reset_index(drop=True)
    return frame[frame.geom_type.isin(['Polygon', 'MultiPolygon']) & ~frame.is_empty].copy()


# NEW: OSM waterway=* features (canals, drains, streams, ditches) come back as
# LineString/MultiLineString centerlines with no inherent width. `polygons()`
# above drops non-polygon geometry types entirely, so canals were being
# silently filtered out before `subtract_buildings` ever ran on them. Buffer
# line geometries into polygons first so they survive. Must be called AFTER
# reprojecting to a projected (metric) CRS -- buffering in degrees is wrong.
# 5 m is a rough half-width for a small/medium canal; widen it if your AOI's
# canals are wider, or set per-feature using an OSM `width` tag if you track one.
def buffer_line_features(frame, buffer_m=5.0):
    frame = frame.copy()
    if frame.empty:
        return frame
    line_types = {'LineString', 'MultiLineString'}
    is_line = frame.geometry.geom_type.isin(line_types)
    frame.loc[is_line, 'geometry'] = frame.loc[is_line, 'geometry'].buffer(buffer_m)
    return frame


# NEW: reservoirs/dams fluctuate seasonally, so a mapped water polygon (usually
# surveyed near full pool) rarely matches the waterline on any given Sentinel
# acquisition date -- land that's dry today can still be soft, recently-submerged
# sediment. Rather than subtracting only the exact current/mapped water extent,
# grow every water feature outward by a safety margin before subtracting, so a
# setback from the waterline survives regardless of which side the OSM snapshot
# or the imagery date happens to disagree on. Tune safety_margin_m to your risk
# tolerance / the reservoir's typical seasonal drawdown distance.
def prepare_water_exclusion(frame, line_width_m=5.0, safety_margin_m=20.0):
    frame = buffer_line_features(frame, buffer_m=line_width_m)
    frame = frame.copy()
    if not frame.empty:
        frame['geometry'] = frame.geometry.buffer(safety_margin_m)
    return frame


def prepare_facility_exclusion(frame, uncertainty_m=20.0):
    """Preserve point/line hazards with an explicit, unsurveyed uncertainty margin."""
    frame = frame.copy()
    if not frame.empty:
        # Legacy OSM adapters may encode an area facility as a closed way.
        # Exclude its interior as well as its uncertain perimeter. Explicit
        # area=no remains a line; open linear facilities stay buffered lines.
        from shapely.geometry import Polygon
        closed=frame.geometry.map(lambda g:g.geom_type=='LineString' and g.is_ring)
        if 'area' in frame:closed &= frame['area'].fillna('').ne('no')
        frame.loc[closed,'geometry']=frame.loc[closed,'geometry'].map(lambda g:Polygon(g.coords))
        frame.geometry = frame.geometry.map(make_valid).buffer(uncertainty_m)
    return polygons(frame)


def save_layer(frame, path, layer):
    frame.to_file(path, layer=layer, driver='GPKG')


def audit(zones, buildings, state, scl, transform, log=print, exclusions=None):
    mask = rasterize([(g, 1) for g in zones.geometry], out_shape=state.shape,
                     transform=transform, dtype='uint8') if len(zones) else np.zeros_like(state)
    unknown = int(np.count_nonzero((mask == 1) & (state == 255)))
    clouds = int(np.count_nonzero((mask == 1) & np.isin(scl, [3,8,9,10])))
    non_open = int(np.count_nonzero((mask == 1) & (state == 0)))
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
                  non_open_overlap_pixels=non_open,
                  zone_overlap_pairs=overlap_pairs, building_overlap_m2=building_overlap,
                  valid_geometries=valid, thresholds_passed=thresholds,
                  unique_ids=bool(zones.zone_id.is_unique), stored_areas_consistent=stored)
    exclusion_overlap = {}
    for name, frame in (exclusions or {}).items():
        if frame.crs != zones.crs:
            frame = frame.to_crs(zones.crs)
        union = frame.geometry.union_all()
        exclusion_overlap[name] = float(zones.intersection(union).area.sum()) if len(frame) else 0.0
    result['exclusion_overlap_m2'] = exclusion_overlap
    # GEOMETRIC TOLERANCE NOTE:
    # 1e-4 m² (1 cm² across the entire AOI) is the legitimate geometric tolerance for
    # cumulative GEOS floating-point coordinate roundoff along shared boundaries.
    # In UTM coordinates (~1.5e6 m), the morphological erosion-dilation filter
    # (buffer(-15).buffer(+15)) followed by .intersection(candidate) introduces sub-micron
    # coordinate jitter (~50 nm wide) on shared building edges. Across 2,694 zones and
    # 33,896 buildings, this micro-jitter sums to ~1.1e-6 m² (approx 1 mm² total).
    # A threshold of 1e-4 m² strictly rejects genuine building collisions while accommodating
    # IEEE 754 float64 multi-zone boundary accumulation.
    result['passed'] = bool(not unknown and not clouds and not non_open and not overlap_pairs and
                            all(area <= 1e-4 for area in exclusion_overlap.values()) and
                            building_overlap <= 1e-4 and valid and thresholds and stored and result['unique_ids'])
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


# CHANGED: process_inputs takes `exclusions`, a dict of {layer_name: GeoDataFrame}
# (e.g. water, industrial) that get subtracted the same way buildings do, after the
# building subtraction and before the geometry gate.
def process_inputs(spectral_path, scl_path, buildings, exclusions, aoi, output, name, log=print,
                   screening_profile='conservative', landcover_path=None, experimental=False):
    neha_baseline = screening_profile == 'neha-236c34c'
    required = {'water', 'industrial'} if neha_baseline else {'water', 'industrial', 'facilities'}
    missing = sorted(required-set(exclusions))
    if missing and not experimental:
        raise ValueError(f'Missing required exclusions: {missing}')
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
    generate_possible_open_mask(spectral_path, scl_path, intermediates/'possible_open.tif', cloud_buffer_pixels=3,
                                screening_profile=screening_profile)
    with rasterio.open(intermediates/'possible_open.tif') as src:
        state, transform, crs = src.read(1), src.transform, src.crs
        state_profile = src.profile.copy()
    landcover_summary = None
    if landcover_path is not None:
        from scripts.processing.landcover_screening import screen_landcover, EXCLUDED_CLASSES
        with rasterio.open(landcover_path) as src:
            if src.crs != crs or src.transform != transform or (src.height,src.width) != state.shape:
                raise ValueError('Land-cover evidence must match the source raster grid exactly.')
            cover = src.read(1)
        previous_open = state == 1
        apply_landcover_exclusion = screening_profile == 'conservative'
        if apply_landcover_exclusion:
            state, excluded = screen_landcover(state,cover,buffer_pixels=1)
        landcover_summary = {'reference_year':2021,'excluded_classes':list(EXCLUDED_CLASSES) if apply_landcover_exclusion else [],
                             'applied_as_exclusion':apply_landcover_exclusion,
                             'uncertainty_buffer_pixels':1,
                             'open_pixels_withheld':int(np.count_nonzero(previous_open & (state != 1))),
                             'missing_coverage_pixels':int(np.count_nonzero(cover == 0))}
        with rasterio.open(intermediates/'screened_open.tif','w',**state_profile) as dst: dst.write(state,1)
        log(f'Land-cover exclusion: {landcover_summary}')
    log('Polygonizing connected open terrain')
    components = polygonize_open_mask(state, transform, crs)
    # Repair point-touch self-intersections before subsequent geometric operations.
    save_layer(components, intermediates/'stages.gpkg', 'open_components')
    if not neha_baseline:
        components = polygons(components)
    # Legacy obstacle snapshots stop at the AOI edge. Withhold an edge strip
    # covering the largest current hazard margin (water: 5 + 20 m).
    edge_buffer_m = 30.0 if screening_profile == 'conservative' else 0.0
    usable_aoi = aoi.to_crs(crs).geometry.union_all().buffer(-edge_buffer_m)
    if not neha_baseline:
        components.geometry = components.geometry.intersection(usable_aoi)
        components = polygons(components)
    buildings = polygons(buildings.to_crs(crs))
    building_sources = buildings.copy()
    if screening_profile == 'conservative':
        from scripts.processing.conservative_screening import BUILDING_UNCERTAINTY_BUFFER_M
        buildings['geometry'] = buildings.geometry.buffer(BUILDING_UNCERTAINTY_BUFFER_M)
    log(f'Subtracting {len(buildings):,} building footprints')
    fragments = subtract_buildings(components, buildings, progress=log)
    save_layer(fragments, intermediates/'stages.gpkg', 'building_cleaned')
    # NEW: subtract every other exclusion layer (water, industrial, ...) the same way.
    prepared_exclusions = {}
    for layer_name, exclusion_frame in exclusions.items():
        if len(exclusion_frame):
            exclusion_frame = exclusion_frame.to_crs(crs)
            if layer_name == 'water':
                # Line-width fix-up plus a shoreline safety setback -- see
                # prepare_water_exclusion for why a fixed margin beats an
                # exact-waterline subtraction here.
                exclusion_frame = prepare_water_exclusion(exclusion_frame, line_width_m=5.0, safety_margin_m=20.0)
            elif layer_name == 'facilities':
                exclusion_frame = prepare_facility_exclusion(exclusion_frame)
            exclusion_frame = polygons(exclusion_frame)
        prepared_exclusions[layer_name] = exclusion_frame
        log(f'Subtracting {len(exclusion_frame):,} {layer_name} exclusion features')
        fragments = subtract_buildings(fragments, exclusion_frame, progress=log)
        save_layer(fragments, intermediates/'stages.gpkg', f'{layer_name}_cleaned')
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
    audits = audit(zones, buildings, state, scl, transform, log, exclusions=prepared_exclusions)
    save_layer(zones, output/'final_zones.gpkg', 'final_open_land_zones')
    if centers:
        save_layer(gpd.GeoDataFrame(centers, geometry='geometry', crs=crs), output/'final_zones.gpkg', 'maximum_clearance_centers')
    (output/'final_zones.geojson').write_text(zones.to_crs(4326).to_json(), encoding='utf-8')
    log('Rendering polygons over Sentinel imagery')
    render_map(spectral_path, aoi, zones, output/'final_zones.png')
    summary = dict(screening_profile=screening_profile, landing_safety_certified=False,
                   experimental=experimental, sources_complete=not missing,
                   missing_required_exclusions=missing, landcover=landcover_summary,
                   aoi_edge_withheld_m=edge_buffer_m,
                   building_source_count=len(building_sources),
                   exclusion_feature_counts={key:len(value) for key,value in prepared_exclusions.items()},
                   open_pixels=int(np.count_nonzero(state == 1)),
                   unknown_pixels=int(np.count_nonzero((state == 255) & (scl != 0))),
                   aoi_pixels=int(np.count_nonzero(scl != 0)),
                   open_components=len(components), building_cleaned_fragments=len(fragments),
                   parent_candidates=len(candidates), raw_operational_zones=raw_count,
                   geometry_passed_zones=geometry_count, final_zones=len(zones),
                   final_area_km2=float(zones.geometry.area.sum()/1e6), audits=audits)
    if screening_profile == 'conservative':
        from scripts.processing.conservative_screening import POLICY_ID, NDVI_MAX, BUILDING_UNCERTAINTY_BUFFER_M
        summary['screening_policy'] = {'id':POLICY_ID, 'allowed_scl_classes':[5],
            'ndvi_max':NDVI_MAX, 'building_uncertainty_buffer_m':BUILDING_UNCERTAINTY_BUFFER_M,
            'facility_uncertainty_buffer_m':20.0, 'water_setback_m':20.0,
            'water_line_half_width_m':5.0, 'aoi_edge_withheld_m':edge_buffer_m,
            'accuracy_measured':False}
    elif screening_profile in ('calibrated','neha-236c34c'):
        from scripts.processing.open_land_detector import V2_NDVI_BARE_MAX,V2_NDVI_VEG_MAX,V2_MNDWI_OPEN_MAX
        summary['screening_policy']={'id':'calibrated-ground-v2','allowed_scl_classes':[4,5],
            'ndvi_bare_max':V2_NDVI_BARE_MAX,'ndvi_vegetation_max':V2_NDVI_VEG_MAX,
            'mndwi_open_max':V2_MNDWI_OPEN_MAX,'historical_landcover_hard_exclusion':False,
            'building_uncertainty_buffer_m':0.0,'facility_uncertainty_buffer_m':20.0,
            'water_setback_m':20.0,'water_line_half_width_m':5.0,
            'aoi_edge_withheld_m':edge_buffer_m,'accuracy_measured':False}
        if neha_baseline:
            summary['screening_policy'].update(id='neha-236c34c',source_revision='236c34c',
                component_handling='original 8-connected components until building difference',
                original_exclusion_layers=['water','industrial'])
    (output/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    log(json.dumps(summary, indent=2))
    return summary
