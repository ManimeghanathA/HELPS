"""Exclusive native-cell slope bands, clipped to exact candidate boundaries.

These are measured surface displays, separate from operational geometry gates.
No cumulative overlay, smoothing, positive boundary tolerance or mean-based fill.
"""
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import geometry_mask, shapes
from rasterio.windows import from_bounds, Window
from shapely.geometry import mapping, shape, MultiPolygon, box
from shapely.ops import transform, unary_union
from pyproj import CRS, Transformer
from functools import lru_cache
import gzip
import hashlib
import json

BREAKS=(0,2,4,6,8,12,15)
UNKNOWN=len(BREAKS)+1
BAND_COUNT=UNKNOWN+1
COLORS=('#91dcba','#c5ee6d','#a6cd5b','#e1d46b','#efb65b','#e38d69','#bd6592','#893d5c','#767d8c')
LABELS=tuple(str(value)+'°' for value in BREAKS)+('>15°','Unknown')


def classify_slope(values):
    values=np.asarray(values)
    labels=np.searchsorted(BREAKS,values,side='left').astype('uint8')
    labels[~np.isfinite(values)|(values<0)|(values>90)]=UNKNOWN
    return labels


def band_properties(index):
    return dict(band_id=index,label=LABELS[index],color=COLORS[index],unit='degrees',
                lower=None if index in (0,UNKNOWN) else BREAKS[index-1],
                upper=BREAKS[index] if index<len(BREAKS) else None,
                lower_inclusive=index==0,upper_inclusive=index<len(BREAKS),
                evidence='unknown' if index==UNKNOWN else 'measured',method='native_cell_exact_boundary_clip')


def compute_slope_bands(parent_geometries,parent_crs,slope_path):
    parents=unary_union([g for g in parent_geometries if g is not None and not g.is_empty])
    if parents.is_empty:return []
    if not parents.is_valid:raise ValueError('Candidate boundary is invalid')
    with rasterio.open(slope_path) as ds:
        if not ds.crs:raise ValueError('Slope raster CRS is missing')
        metric_crs=CRS.from_user_input(ds.crs)
        if not metric_crs.is_projected or any(axis.unit_conversion_factor!=1 for axis in metric_crs.axis_info[:2]):
            raise ValueError('Measured slope display requires the native projected metre grid')
        if CRS.from_user_input(parent_crs)!=CRS.from_user_input(ds.crs):
            project=Transformer.from_crs(parent_crs,ds.crs,always_xy=True)
            parents=transform(project.transform,parents)
        values=ds.read(1,masked=True)
        labels=classify_slope(values.filled(np.nan))
        labels[np.ma.getmaskarray(values)]=UNKNOWN
        grouped={i:[] for i in range(BAND_COUNT)}
        # Clip in bounded, disconnected candidate parts. Intersecting each
        # global band with thousands of intricate parents is unnecessarily slow.
        parts=list(parents.geoms) if parents.geom_type=='MultiPolygon' else [parents]
        for part in parts:
            bounds=from_bounds(*part.bounds,transform=ds.transform)
            left=max(0,int(np.floor(bounds.col_off))-1)
            top=max(0,int(np.floor(bounds.row_off))-1)
            right=min(ds.width,int(np.ceil(bounds.col_off+bounds.width))+1)
            bottom=min(ds.height,int(np.ceil(bounds.row_off+bounds.height))+1)
            if left>=right or top>=bottom:
                grouped[UNKNOWN].append(part)
                continue
            window=Window(left,top,right-left,bottom-top)
            tile=labels[top:bottom,left:right]
            transform_grid=ds.window_transform(window)
            touched=geometry_mask([mapping(part)],out_shape=tile.shape,transform=transform_grid,
                                  all_touched=True,invert=True)
            for geom,value in shapes(tile,mask=touched,transform=transform_grid,connectivity=4):
                clipped=shape(geom).intersection(part)
                if not clipped.is_empty and clipped.area>0:grouped[int(value)].append(clipped)
            outside=part.difference(box(*ds.bounds))
            if not outside.is_empty and outside.area>0:grouped[UNKNOWN].append(outside)
    records=[]
    def polygons(geometry):
        if geometry.geom_type=='Polygon':return [geometry]
        if hasattr(geometry,'geoms'):
            return [p for part in geometry.geoms for p in polygons(part)]
        return []
    for index,geometries in grouped.items():
        parts=[p for g in geometries for p in polygons(g) if p.area>0]
        if not parts:continue
        # Classified connected components and disconnected parent parts have
        # disjoint interiors. Packing them preserves exact coordinates while
        # avoiding expensive repeated global dissolution of the same cells.
        clipped=parts[0] if len(parts)==1 else MultiPolygon(parts)
        if not clipped.is_valid:
            clipped=unary_union(parts)
        records.append({**band_properties(index),'geometry':clipped,'area_m2':clipped.area})
    return records


def slope_bands_geojson(package_path,slope_path=None):
    import geopandas as gpd
    package_path=Path(package_path)
    slope_path=Path(slope_path) if slope_path is not None else package_path.parent/'rasters/slope.tif'
    if not slope_path.is_file():raise LookupError('Measured slope raster unavailable')
    parents=gpd.read_file(package_path,layer='terrain')
    with rasterio.open(slope_path) as ds:
        crs=ds.crs
        resolution=tuple(abs(v) for v in ds.res)
    bands=compute_slope_bands(parents.geometry,parents.crs,slope_path)
    project=Transformer.from_crs(crs,'EPSG:4326',always_xy=True)
    return dict(type='FeatureCollection',features=[dict(type='Feature',
        geometry=mapping(transform(project.transform,row['geometry'])),
        properties={k:v for k,v in row.items() if k!='geometry'}) for row in bands],
        unit='degrees',resolution_m=resolution,exclusive=True,
        legend=[band_properties(i) for i in range(BAND_COUNT)])


@lru_cache(maxsize=4)
def cached_slope_bands(package_path,package_mtime_ns,slope_mtime_ns,slope_path=None):
    """Cache only a bounded number of immutable package/raster identities."""
    identity=hashlib.sha256((str(package_path)+str(package_mtime_ns)+str(slope_mtime_ns)+str(slope_path)).encode()
                            +Path(__file__).read_bytes()).hexdigest()
    cache_path=Path(package_path).parent/'display-cache'/('slope-'+identity+'.json.gz')
    if cache_path.exists():
        try:
            return json.loads(gzip.decompress(cache_path.read_bytes()))
        except (OSError,EOFError,ValueError):
            pass  # Interrupted display cache is recoverable from authoritative evidence.
    result=slope_bands_geojson(package_path,slope_path)
    cache_path.parent.mkdir(exist_ok=True)
    cache_path.write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode('utf-8')))
    return result
