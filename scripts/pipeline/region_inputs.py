"""Source-specific adapters for the region raw/processed input lifecycle."""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import box

from .source_store import SourceStore
from scripts.knowledge.contracts import SourceAsset
from scripts.knowledge.sources import file_sha256


class RegionInputs:
    def __init__(self,root,region_id,aoi):
        self.store=SourceStore(root,region_id,aoi);self.root=self.store.root;self.aoi=aoi

    def validate(self,kind,day=None):
        def check(paths,metadata):
            if kind=='sentinel':
                with rasterio.open(paths['spectral']) as spectral,rasterio.open(paths['scl']) as scl:
                    if spectral.count!=6 or scl.count!=1 or spectral.crs is None or spectral.crs!=scl.crs or spectral.transform!=scl.transform or spectral.shape!=scl.shape:
                        raise ValueError('Sentinel bands or shared grid invalid')
                    extent=box(*spectral.bounds)
                    if not extent.buffer(max(spectral.res)*1e-6).covers(self.aoi.to_crs(spectral.crs).geometry.union_all()):raise ValueError('Sentinel extent does not cover region')
                    for src in (spectral,scl):
                        for key in ('date','observation_date','acquisition_date','DATE_ACQUIRED'):
                            if src.tags().get(key) and src.tags()[key][:10]!=day:raise ValueError('Sentinel source date mismatch')
                    if metadata.get('observation_date',day)!=day:raise ValueError('Sentinel manifest date mismatch')
            elif kind=='osm':
                from .acquisition import GROUPS,osm_complete
                if not osm_complete(paths['osm'],include_context=True):raise ValueError('OSM missing required layers')
                for layer in GROUPS:
                    frame=gpd.read_file(paths['osm'],layer=layer)
                    if frame.crs is None or frame.geometry.isna().any() or not frame.is_valid.all():raise ValueError('OSM layer geometry or CRS invalid')
            elif kind=='overture':
                frame=gpd.read_file(paths['overture'])
                if frame.crs is None or frame.geometry.isna().any() or not frame.is_valid.all() or not frame.geom_type.isin(['Polygon','MultiPolygon']).all():raise ValueError('Overture building geometry or CRS invalid')
            elif kind=='dem':
                from .elevation import verify_dem_coverage
                verify_dem_coverage(SourceAsset('resolved-dem',paths['dem'],kind='dem',units=metadata.get('units'),sha256=file_sha256(paths['dem'])),self.aoi)
            elif kind=='landcover':
                with rasterio.open(paths['landcover']) as src:
                    if src.crs is None or src.count!=1 or not box(*src.bounds).buffer(max(src.res)*1e-6).covers(self.aoi.to_crs(src.crs).geometry.union_all()):raise ValueError('Land-cover coverage invalid')
        def validated(paths,metadata):
            from pyogrio.errors import DataSourceError,DataLayerError
            try:check(paths,metadata)
            except (rasterio.errors.RasterioError,DataSourceError,DataLayerError,OSError) as exc:
                raise ValueError(f'{kind} evidence cannot be read or validated') from exc
        return validated

    @staticmethod
    def prepare(raw,folder,metadata):
        files={}
        for key,path in raw.items():
            # Provider evidence remains in raw; only analysis-ready adapter outputs
            # are copied here. Source arrays and attributes are preserved exactly.
            if key.startswith('native_'):continue
            target=folder/path.name;shutil.copyfile(path,target);files[key]=target.name
        return files,metadata

    def _download(self,kind,day):
        def run(folder):
            from . import acquisition as acq
            now=datetime.now(timezone.utc).isoformat()
            metadata={'acquired_at':now,'snapshot_date':now[:10],
                      'date_status':'acquisition-time mapped snapshot; not the imagery observation date',
                      'coverage_note':'provider query for this region plus obstacle halo; unmapped features remain unknown'}
            log=self._log
            if kind=='sentinel':
                acq.sentinel(self.aoi,day,folder,log)
                metadata.update(observation_date=day,date_status='same-day Sentinel-2 observation',
                                raw_layout='Original provider tiles/responses retained under archive; spectral/SCL mosaics are adapter intermediates.')
                files={'spectral':'spectral.tif','scl':'scl.tif'}
            elif kind=='osm':
                provenance=acq.osm(self.aoi,folder/'osm.gpkg',log,include_context=True)
                metadata['raw_layout']='Original Overpass JSON/XML under archive; GeoPackage is adapter intermediate.'
                if provenance:metadata.update(provenance)
                files={'osm':'osm.gpkg'}
            elif kind=='overture':
                acq.overture(self.aoi,folder/'overture.geojson',log)
                metadata['raw_layout']='Original bounding-box export under archive; GeoJSON is adapter intermediate.'
                files={'overture':'overture.geojson'}
            else:raise ValueError('Unsupported automatic source')
            self.validate(kind,day)({k:folder/v for k,v in files.items()},metadata)
            return files,metadata
        return run

    def resolve_context(self,day,refresh=False,log=print,required=('sentinel','osm','overture'),local_only=False):
        self._log=log;results={}
        if local_only:
            if refresh:raise ValueError('Date-only scans reuse local obstacle data; refresh is disabled')
            for kind in required:
                if kind=='sentinel':continue
                if not any(self.store._find(phase,kind,None,self.validate(kind))[0] for phase in ('processed','raw')):
                    raise ValueError(f'Validated local {kind.upper()} data is missing. Restore the local baseline before a date-only scan; static data will not be downloaded.')
        for kind in required:
            def local_required(folder,source=kind):
                raise ValueError(f'Validated local {source.upper()} data is missing; date-only scans never download static inputs')
            results[kind]=self.store.resolve(kind,day if kind=='sentinel' else None,
                local_required if local_only and kind!='sentinel' else self._download(kind,day),self.prepare,self.validate(kind,day),
                refresh=refresh and kind in ('osm','overture'),log=log)
        return results

    def resolve_dem(self,selected=None,log=print,local_only=False):
        from .elevation import acquire_dem,KNOWN_FABDEM_SHA256,FABDEM_METADATA
        if selected is not None:
            metadata={**selected.metadata,'units':selected.units,'original_source_id':selected.source_id}
            if selected.sha256 and file_sha256(selected.path)!=selected.sha256:raise ValueError('Selected DEM checksum mismatch')
            self.validate('dem')({'dem':selected.path},metadata)
            # Explicit selections must not be replaced by a previously resolved
            # automatic DEM. Keep their identity in the build, register a copy of
            # their provenance separately only if no other processed DEM exists.
            if Path(selected.path).resolve().is_relative_to(self.root/'data'):
                self.store.adopt('dem',None,{'dem':selected.path},metadata,self.validate('dem'))
            return selected
        local=self.root/'data/raw/DEM/FABDEM_N13E075.tif'
        if self.store.inspect('dem')['action']=='download' and local.is_file() and file_sha256(local)==KNOWN_FABDEM_SHA256:
            try:self.store.adopt('dem',None,{'dem':local},{**FABDEM_METADATA,'units':'m','legacy_source':str(local)},self.validate('dem'))
            except ValueError:pass  # Known tile may not cover a different region.
        def download(folder):
            if local_only:raise ValueError('Validated local elevation is missing; date-only scans never download static inputs')
            asset=acquire_dem(self.aoi,self.root,log,raw_directory=folder/'native')
            target=folder/'dem.tif';shutil.copyfile(asset.path,target)
            files={'dem':target.name}
            for i,path in enumerate(sorted((folder/'native').glob('*.tif'))):files['native_'+str(i)]=path.relative_to(folder).as_posix()
            return files,{**asset.metadata,'units':asset.units,'source_id':asset.source_id,
                          'raw_layout':'Native provider windows retained where acquired; dem.tif is the bounded adapter derivative. Cache reuse may reference earlier provider provenance.'}
        result=self.store.resolve('dem',None,download,self.prepare,self.validate('dem'),log=log)
        return SourceAsset(result['metadata'].get('source_id','region-dem-'+result['snapshot_id']),result['paths']['dem'],kind='dem',
                           units=result['metadata']['units'],sha256=file_sha256(result['paths']['dem']),
                           coverage_state='verified',metadata={**result['metadata'],'input_manifest':str(result['manifest_path'])})

    def resolve_landcover(self,reference,log=print,local_only=False):
        from .landcover import acquire_worldcover
        def download(folder):
            if local_only:raise ValueError('Validated local land cover is missing or incompatible; date-only scans never download static inputs')
            path,metadata=acquire_worldcover(reference,folder,log)
            return {'landcover':Path(path).name},metadata
        def validate(paths,metadata):
            self.validate('landcover')(paths,metadata)
            with rasterio.open(reference) as ref,rasterio.open(paths['landcover']) as src:
                if src.crs!=ref.crs or src.transform!=ref.transform or src.shape!=ref.shape:
                    raise ValueError('Land-cover grid differs from selected Sentinel grid')
        def align(raw,folder,metadata):
            from rasterio.warp import reproject,Resampling
            crops=sorted(raw['landcover'].parent.glob('*crop.tif')) or [raw['landcover']]
            with rasterio.open(reference) as ref:
                profile=ref.profile.copy();profile.update(count=1,dtype='uint8',nodata=0,compress='deflate')
                data=np.zeros(ref.shape,dtype='uint8')
                for path in crops:
                    with rasterio.open(path) as src:
                        reproject(rasterio.band(src,1),data,src_transform=src.transform,src_crs=src.crs,
                            dst_transform=ref.transform,dst_crs=ref.crs,src_nodata=0,dst_nodata=0,
                            resampling=Resampling.nearest,init_dest_nodata=False)
                with rasterio.open(folder/'landcover.tif','w',**profile) as dst:dst.write(data,1)
            return {'landcover':'landcover.tif'},{**metadata,'reference_path':str(reference),'reference_sha256':file_sha256(reference)}
        return self.store.resolve('landcover',None,download,align,validate,log=log)

    def readiness(self,day,refresh=False):
        return [self.store.inspect(kind,day if kind=='sentinel' else None,refresh=refresh and kind in ('osm','overture')) for kind in ('sentinel','dem','osm','overture','landcover')]

    def adopt_bhadra(self,log=print):
        """Register known Bhadra evidence; do not guess geographic coverage from
        feature extents or search arbitrary files on the user's machine.
        """
        if self.store.region_id!='bhadra':return []
        from .inputs import load_aoi
        boundary=self.root/'data/raw/Bhadra/bhadra_entire_region.geojson'
        if not boundary.is_file() or not load_aoi(boundary).geometry.union_all().equals(self.aoi.to_crs(4326).geometry.union_all()):return []
        marker=self.root/'data/processed'/self.store.region_id/'.legacy-inputs-registered.json'
        if marker.is_file():
            try:
                if json.loads(marker.read_text(encoding='utf-8')).get('aoi_hash')==self.store.aoi_hash:return []
            except (ValueError,OSError):raise ValueError('Legacy registration record is unreadable; restore it before building') from None
        adopted=[];base=self.root/'data/processed/Bhadra'
        for folder in sorted((base/'sentinel2').glob('????-??-??')):
            paths={'spectral':folder/'bhadra_spectral.tif','scl':folder/'bhadra_scl.tif'}
            if not all(p.is_file() for p in paths.values()):continue
            try:
                self.store.adopt('sentinel',folder.name,paths,{'observation_date':folder.name,'date_status':'legacy dated Bhadra source','original_layout':str(folder)},self.validate('sentinel',folder.name));adopted.append('sentinel '+folder.name)
            except (OSError,ValueError,rasterio.errors.RasterioError) as exc:log(f'Legacy Sentinel not adopted: {type(exc).__name__}')
        for folder in sorted((self.root/'data/raw/Sentinel2').glob('????-??-??')):
            paths={'spectral':folder/'spectral.tif','scl':folder/'scl.tif'}
            if not all(p.is_file() for p in paths.values()):continue
            try:
                self.store.adopt('sentinel',folder.name,paths,{'observation_date':folder.name,'date_status':'legacy dated Bhadra raw bundle','original_layout':str(folder)},self.validate('sentinel',folder.name),phase='raw')
            except ValueError as exc:log(f'Legacy raw Sentinel not adopted: {type(exc).__name__}')
        for kind,paths in [('osm',{'osm':base/'osm/bhadra_osm_context.gpkg'}),('overture',{'overture':base/'buildings/bhadra_overture_buildings.geojson'})]:
            if not all(p.is_file() for p in paths.values()):continue
            try:
                self.store.adopt(kind,None,paths,{'date_status':'legacy mapped snapshot; acquisition date unknown',
                    'coverage_note':'declared original Bhadra input; geographic completeness unverified','snapshot_date':None},self.validate(kind))
                adopted.append(kind)
            except (OSError,ValueError) as exc:log(f'Legacy {kind} not adopted: {type(exc).__name__}; required evidence will be acquired')
        from scripts.knowledge.repository import _atomic_json
        _atomic_json(marker,{'aoi_hash':self.store.aoi_hash,'registered':adopted,
                           'policy':'One-time registration; changed legacy sources must not be silently re-adopted.'})
        return adopted


def resolve_region_inputs(root,region_id,aoi,day,log=print,refresh=False,existing=None,static_only=False):
    service=RegionInputs(root,region_id,aoi)
    service.adopt_bhadra(log)
    existing=existing or {}
    if static_only and 'landcover' not in existing:
        if not any(service.store._find(phase,'landcover',None,service.validate('landcover'))[0] for phase in ('processed','raw')):
            raise ValueError('Validated local land cover is missing; restore the Bhadra baseline before downloading a new observation')
    required=['sentinel']
    if not {'osm_buildings','water','industrial','facilities','roads','power','man_made','barriers'}.issubset(existing):required.append('osm')
    if 'buildings' not in existing:required.append('overture')
    results=service.resolve_context(day,refresh=refresh,log=log,required=required,local_only=static_only)
    paths={key:path for result in results.values() for key,path in result['paths'].items()}
    if 'landcover' not in existing:
        cover=service.resolve_landcover(paths['spectral'],log,local_only=static_only)
        paths.update(cover['paths']);results['landcover']=cover
    return paths,{'date':day,'region_id':region_id,'input_snapshots':{
        kind:{'snapshot_id':r['snapshot_id'],'manifest_path':str(r['manifest_path']),'metadata':r['metadata']} for kind,r in results.items()},
        'files':{key:{'path':str(path.relative_to(Path(root).resolve())),'sha256':file_sha256(path)} for key,path in paths.items()},
        'context_note':'OSM/Overture retain their independent acquisition dates; not historical imagery-date truth.'}
