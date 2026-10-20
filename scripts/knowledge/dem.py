"""Native-scale metric elevation, Horn slope and 3x3 detrended RMS."""
from pathlib import Path
import json
import math
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from rasterio.features import geometry_mask
from .contracts import TerrainRasterAssets
from .sources import file_sha256


def compute_derivatives(elevation, valid, dx_m, dy_m):
    if not np.isfinite([dx_m,dy_m]).all() or min(dx_m,dy_m)<=0:
        raise ValueError('positive finite metric grid spacing required')
    z=np.asarray(elevation,dtype=np.float64)
    valid=np.asarray(valid,dtype=bool)&np.isfinite(z)
    if z.ndim!=2 or z.shape!=valid.shape: raise ValueError('elevation and valid must share a 2D grid')
    slope=np.full(z.shape,np.nan,dtype='float32'); rough=slope.copy(); supported=np.zeros(z.shape,bool)
    if min(z.shape)<3: return slope,rough,supported
    windows=np.lib.stride_tricks.sliding_window_view(z,(3,3))
    mask=np.lib.stride_tricks.sliding_window_view(valid,(3,3)).all(axis=(-2,-1))
    gx=((windows[:,:,0,2]+2*windows[:,:,1,2]+windows[:,:,2,2])-(windows[:,:,0,0]+2*windows[:,:,1,0]+windows[:,:,2,0]))/(8*dx_m)
    gy=((windows[:,:,2,0]+2*windows[:,:,2,1]+windows[:,:,2,2])-(windows[:,:,0,0]+2*windows[:,:,0,1]+windows[:,:,0,2]))/(8*dy_m)
    angles=np.degrees(np.arctan(np.hypot(gx,gy)))
    # The orthogonal 3x3 plane basis gives an exact least-squares fit.
    xs=np.tile(np.array([-dx_m,0,dx_m]),(3,1)); ys=np.tile(np.array([-dy_m,0,dy_m])[:,None],(1,3))
    mean=windows.mean(axis=(-2,-1))
    bx=(windows*xs).sum(axis=(-2,-1))/(xs*xs).sum()
    by=(windows*ys).sum(axis=(-2,-1))/(ys*ys).sum()
    residual=windows-mean[:,:,None,None]-bx[:,:,None,None]*xs-by[:,:,None,None]*ys
    rms=np.sqrt(np.mean(residual*residual,axis=(-2,-1)))
    supported[1:-1,1:-1]=mask
    slope[1:-1,1:-1]=np.where(mask,angles,np.nan)
    rough[1:-1,1:-1]=np.where(mask,rms,np.nan)
    return slope,rough,supported


def metric_crs(frame):
    if frame.crs is None: raise ValueError('AOI CRS required')
    if frame.crs.is_projected and all(abs(axis.unit_conversion_factor-1)<1e-8 for axis in frame.crs.axis_info[:2]):
        return frame.crs
    crs=frame.estimate_utm_crs()
    if crs is None: raise ValueError('cannot determine local metric CRS')
    return crs


def prepare_terrain_rasters(dem,aoi,output_dir,resolution_m=30.0):
    if not np.isfinite(resolution_m) or resolution_m<=0: raise ValueError('resolution_m must be finite and positive')
    if dem.units not in ('m','metre','meter','ft','feet','foot'): raise ValueError('DEM vertical units required')
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    crs=metric_crs(aoi); metric=aoi.to_crs(crs)
    left,bottom,right,top=metric.total_bounds
    # Align AOI to native-scale grid and add the required derivative halo.
    left=math.floor(left/resolution_m)*resolution_m-resolution_m
    bottom=math.floor(bottom/resolution_m)*resolution_m-resolution_m
    right=math.ceil(right/resolution_m)*resolution_m+resolution_m
    top=math.ceil(top/resolution_m)*resolution_m+resolution_m
    width=round((right-left)/resolution_m); height=round((top-bottom)/resolution_m)
    transform=from_origin(left,top,resolution_m,resolution_m)
    elevation=np.full((height,width),np.nan,dtype='float32')
    with rasterio.open(dem.path) as src:
        if src.crs is None: raise ValueError('DEM CRS required')
        source=src.read(1,masked=True).astype('float32')
        source_valid=~np.ma.getmaskarray(source)&np.isfinite(source.data)
        data=np.where(source_valid,source.data,np.nan).astype('float32')
        if dem.units in ('ft','feet','foot'): data*=np.float32(.3048)
        reproject(data,elevation,src_transform=src.transform,src_crs=src.crs,src_nodata=np.nan,dst_transform=transform,dst_crs=crs,dst_nodata=np.nan,resampling=Resampling.bilinear)
        support=np.zeros(elevation.shape,dtype='float32')
        reproject(source_valid.astype('float32'),support,src_transform=src.transform,src_crs=src.crs,dst_transform=transform,dst_crs=crs,dst_nodata=0,resampling=Resampling.bilinear)
        original={'crs':src.crs.to_string(),'resolution':list(src.res),'nodata':src.nodata,'tags':src.tags()}
    valid=np.isfinite(elevation)&(support>=1-1e-6)
    elevation[~valid]=np.nan
    slope,roughness,derivative_valid=compute_derivatives(elevation,valid,resolution_m,resolution_m)
    aoi_mask=geometry_mask(metric.geometry,transform=transform,out_shape=elevation.shape,invert=True)
    denominator=max(1,int(aoi_mask.sum()))
    manifest={'source_id':dem.source_id,'source_sha256':file_sha256(dem.path),'source_date':dem.date,'source_units':dem.units,'source':original,'crs':crs.to_string(),'resolution_m':resolution_m,'elevation_unit':'m','slope_unit':'degree','roughness_unit':'m','slope_method':'Horn 3x3','roughness_method':'least-squares plane residual RMS 3x3','derivative_halo_cells':1,'aoi_elevation_valid_fraction':float((valid&aoi_mask).sum()/denominator),'aoi_derivative_valid_fraction':float((derivative_valid&aoi_mask).sum()/denominator),'vertical_datum':dem.metadata.get('vertical_datum','unknown'),'attribution':dem.metadata.get('attribution','unknown'),'license':dem.metadata.get('license','unknown')}
    paths={}
    for name,array,dtype,nodata in [('elevation',elevation,'float32',np.nan),('slope',slope,'float32',np.nan),('roughness',roughness,'float32',np.nan),('valid',derivative_valid.astype('uint8'),'uint8',0)]:
        path=output_dir/f'{name}.tif'; paths[name]=path
        with rasterio.open(path,'w',driver='GTiff',width=width,height=height,count=1,dtype=dtype,crs=crs,transform=transform,nodata=nodata,compress='deflate',tiled=True) as dst:
            dst.write(array,1)
            dst.update_tags(dataset_source=dem.source_id,method=manifest.get(name+'_method','source elevation'))
    manifest_path=output_dir/'rasters.json'; manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return TerrainRasterAssets(paths['elevation'],paths['slope'],paths['roughness'],paths['valid'],crs.to_string(),resolution_m,manifest,manifest_path)
