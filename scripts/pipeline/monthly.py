"""Bounded authenticated CDSE catalog discovery; metadata is not clear-ground QA."""
from datetime import date, timedelta
from pathlib import Path
import json
import os
import math
import requests
from shapely.geometry import shape
from shapely.ops import unary_union
from pyproj import Transformer
from shapely.ops import transform
from scripts.knowledge.chronology import observation_date

CATALOG_URL='https://sh.dataspace.copernicus.eu/catalog/v1/search'
TOKEN_URL='https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'


def month_buckets(end_date,start_date=None):
    end=observation_date(end_date)
    if end>date.today():raise ValueError('Search end date cannot be in the future')
    first=observation_date(start_date) if start_date else None
    if first and first>end:raise ValueError('Search start date cannot follow its end date')
    count=(end.year-first.year)*12+end.month-first.month+1 if first else 12
    if count>120:raise ValueError('Search is limited to 120 months; choose a more recent start date')
    buckets=[]
    for offset in reversed(range(count)):
        index=end.year*12+end.month-1-offset
        year,month=divmod(index,12);month+=1
        start=date(year,month,1)
        next_month=date(year+int(month==12),1 if month==12 else month+1,1)
        stop=min(end,next_month-timedelta(days=1))
        buckets.append({'month':start.strftime('%Y-%m'),'start_date':max(start,first).isoformat() if first else start.isoformat(),'end_date':stop.isoformat()})
    return buckets


def group_monthly(buckets,products,aoi=None):
    groups={}
    for product in products:
        day=product['date'];observation_date(day)
        if not any(b['start_date']<=day<=b['end_date'] for b in buckets):continue
        groups.setdefault(day,{})[product['id']]=product
    observations=[]
    for day,by_id in sorted(groups.items()):
        items=list(by_id.values());ids=sorted(by_id)
        footprints=[shape(p['geometry']) for p in items if p.get('geometry')]
        coverage=None
        if aoi is not None and footprints:
            # Equal-area projection avoids treating longitude/latitude degrees as metres.
            project=Transformer.from_crs(4326,6933,always_xy=True).transform
            region=transform(project,aoi);covered=transform(project,unary_union(footprints)).intersection(region)
            coverage=min(1.0,covered.area/region.area)
        elif items and all(p.get('coverage_fraction') is not None for p in items):
            # Without footprints the union is unknown; only a conservative lower bound.
            coverage=max(p['coverage_fraction'] for p in items)
        clouds=[p.get('cloud_fraction') for p in items if p.get('cloud_fraction') is not None]
        row={'date':day,'product_ids':ids,'timestamps':sorted({p.get('timestamp',day) for p in items}),'qa_state':'metadata_only','cloud_fraction':sum(clouds)/len(clouds) if clouds else None,'coverage_fraction':coverage,'usable_support':None,'cloud_shadow_fraction':None,'products':items,'qa_note':'Catalog cloud fraction is product metadata; AOI clear ground has not been measured'}
        observations.append(row)
    months=[]
    for bucket in buckets:
        rows=[r for r in observations if bucket['start_date']<=r['date']<=bucket['end_date']]
        def rank(r):
            return (0 if r['qa_state']=='measured' else 1,-(r['usable_support'] or 0),r['cloud_shadow_fraction'] if r['cloud_shadow_fraction'] is not None else (r['cloud_fraction'] if r['cloud_fraction'] is not None else 1),-(r['coverage_fraction'] or 0),r['date'],r['product_ids'])
        rows.sort(key=rank)
        months.append({**bucket,'status':'available' if rows else 'missing','observations':rows,'recommended_date':rows[0]['date'] if rows else None})
    return months


def catalog_search(aoi,end_date,root,log=lambda message:None,session=None,max_pages_per_month=3,measure_shortlist=True,start_date=None):
    from dotenv import load_dotenv
    from scripts.ui.unified_api import load_credentials
    load_credentials(root)
    if not os.getenv('CDSE_CLIENT_ID') or not os.getenv('CDSE_CLIENT_SECRET'):
        raise ValueError('Copernicus imagery search requires configured CDSE_CLIENT_ID and CDSE_CLIENT_SECRET; no provider acquisition was performed')
    session=session or requests.Session()
    try:
        response=session.post(TOKEN_URL,data={'grant_type':'client_credentials','client_id':os.environ['CDSE_CLIENT_ID'],'client_secret':os.environ['CDSE_CLIENT_SECRET']},timeout=(10,30));response.raise_for_status()
        token=response.json()['access_token']
    except (requests.RequestException,ValueError,KeyError):raise ValueError('Copernicus authentication failed; verify configured client access') from None
    region=aoi.to_crs(4326).geometry.union_all();buckets=month_buckets(end_date,start_date);products=[];errors=[]
    for bucket in buckets:
        log(f'Searching {bucket["month"]} (bounded catalog shortlist)')
        query={'collections':['sentinel-2-l2a'],'bbox':list(region.bounds),'datetime':bucket['start_date']+'T00:00:00Z/'+bucket['end_date']+'T23:59:59Z','limit':100}
        try:
            for page in range(max_pages_per_month):
                response=session.post(CATALOG_URL,json=query,headers={'Authorization':'Bearer '+token},timeout=(10,30));response.raise_for_status();data=response.json()
                for feature in data.get('features',[]):
                    props=feature['properties'];stamp=props['datetime'];cloud=props.get('eo:cloud_cover')
                    products.append({'id':feature['id'],'date':stamp[:10],'timestamp':stamp,'geometry':feature['geometry'],'cloud_fraction':None if cloud is None else min(1,max(0,float(cloud)/100))})
                next_page=data.get('context',{}).get('next')
                if next_page is None:break
                query['next']=next_page
            else:errors.append({'month':bucket['month'],'error':'Catalog shortlist limit reached; additional products were not inspected','bounded':True})
        except (requests.RequestException,ValueError,KeyError):errors.append({'month':bucket['month'],'error':'Copernicus catalog request failed or returned invalid metadata','bounded':True})
    months=group_monthly(buckets,products,region)
    if measure_shortlist:
        # Two candidate days per month bound processing requests and memory. All
        # other observations retain their honest metadata-only quality status.
        for month in months:
            if not month['observations']:continue
            for observation in month['observations'][:2]:
                log(f'Inspecting shortlisted SCL ground quality for {observation["date"]}')
                try:
                    observation.update(acquire_scl_quality(session,token,aoi,observation['date'],root,log=log))
                except (ValueError,OSError,requests.RequestException) as exc:
                    observation['qa_note']='SCL inspection unavailable; catalog metadata does not prove usable AOI ground'
                    errors.append({'month':month['month'],'date':observation['date'],'error':'Cloud inspection unavailable; catalog cloud estimates are still available','stage':'scl_quality','failure_kind':('http_'+str(exc.response.status_code)) if isinstance(exc,requests.HTTPError) and exc.response is not None else type(exc).__name__,'bounded':True})
            month['observations'].sort(key=lambda r:(0 if r['qa_state']=='measured' else 1,-(r['usable_support'] or 0),r['cloud_shadow_fraction'] if r['cloud_shadow_fraction'] is not None else (r['cloud_fraction'] if r['cloud_fraction'] is not None else 1),-(r['coverage_fraction'] or 0),r['date'],r['product_ids']))
            best=month['observations'][0]
            month['recommended_date']=best['date'] if best['qa_state']=='measured' and best['usable_support']>0 else None
            month['qa_scope']='Bounded two-day monthly shortlist; other days retain product cloud metadata only'
            if best['qa_state']=='measured' and best['usable_support']==0:month['status']='no_usable_measured_observation'
    failed={e['month'] for e in errors if 'failed' in e['error']}
    for month in months:
        if month['month'] in failed:month['status']='failed'
    observations=[r for m in months for r in m['observations']]
    return {'status':'partial' if errors else 'completed','months':months,'observations':observations,'errors':errors,'provider':'Copernicus Data Space Sentinel Hub catalog','qa_state':'mixed' if any(r['qa_state']=='measured' for r in observations) else 'metadata_only','search_end_date':end_date}


def acquire_scl_quality(session,token,aoi,day,root,log=lambda message:None):
    """A bounded same-day native-20m SCL mosaic, cached by geometry and date."""
    import hashlib
    import rasterio
    from rasterio.io import MemoryFile
    from scripts.knowledge.repository import _atomic_json
    crs=aoi.estimate_utm_crs();region=aoi.to_crs(crs).geometry.union_all()
    key=hashlib.sha256(region.wkb+day.encode()+str(crs).encode()+b'ground-support-v2-water-excluded').hexdigest()[:24]
    folder=Path(root)/'data/knowledge/monthly-cache';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(key+'-scl.tif');metadata=folder/(key+'-qa.json')
    if path.exists() and metadata.exists():
        record=json.loads(metadata.read_text(encoding='utf-8'))
        from scripts.knowledge.sources import file_sha256
        if record.get('sha256')==file_sha256(path):return {k:v for k,v in record.items() if k not in ('sha256','path')}
    left,bottom,right,top=region.bounds
    left=math.floor(left/20)*20;bottom=math.floor(bottom/20)*20;right=math.ceil(right/20)*20;top=math.ceil(top/20)*20
    width=round((right-left)/20);height=round((top-bottom)/20)
    if width*height>10_000_000:raise ValueError('AOI SCL shortlist exceeds bounded 10 million native cells')
    payload={'input':{'bounds':{'bbox':[left,bottom,right,top],'properties':{'crs':f'http://www.opengis.net/def/crs/EPSG/0/{crs.to_epsg()}'}},'data':[{'type':'sentinel-2-l2a','dataFilter':{'timeRange':{'from':day+'T00:00:00Z','to':day+'T23:59:59Z'},'mosaickingOrder':'leastCC'}}]},'output':{'width':width,'height':height,'responses':[{'identifier':'default','format':{'type':'image/tiff'}}]},'evalscript':'//VERSION=3\nfunction setup(){return {input:["SCL"],output:{bands:1,sampleType:"UINT8",nodataValue:0}};}\nfunction evaluatePixel(s){return [s.SCL];}'}
    import copy
    import numpy as np
    from rasterio.transform import from_origin
    from rasterio.windows import Window
    from uuid import uuid4
    staged=path.with_name(path.name+'.'+uuid4().hex+'.staging')
    try:
        with rasterio.open(staged,'w',driver='GTiff',count=1,dtype='uint8',crs=crs,
                           width=width,height=height,transform=from_origin(left,top,20,20),nodata=0,compress='deflate') as dst:
            for row in range(0,height,2400):
                for col in range(0,width,2400):
                    w,h=min(2400,width-col),min(2400,height-row)
                    x,y=left+col*20,top-row*20
                    tile=copy.deepcopy(payload)
                    tile['input']['bounds']['bbox']=[x,y-h*20,x+w*20,y]
                    tile['output'].update(width=w,height=h)
                    from .sentinel_requests import process_request
                    response=process_request(session,tile,token,log,timeout=(10,90))
                    with MemoryFile(response.content) as mem,mem.open() as src:
                        if src.crs!=crs or src.count!=1 or src.width!=w or src.height!=h:raise ValueError('Unexpected Sentinel SCL response grid')
                        if not np.allclose(tuple(src.bounds),(x,y-h*20,x+w*20,y),rtol=0,atol=1e-4):raise ValueError('Sentinel SCL response bounds do not match requested AOI tile')
                        values=src.read(1)
                        if not set(np.unique(values)).issubset(set(range(12))):raise ValueError('Invalid Sentinel SCL classes')
                        dst.write(values,1,window=Window(col,row,w,h))
        # Check the staged mosaic before advertising it as a reusable source.
        quality=measure_scl_quality(staged,aoi)
        os.replace(staged,path)
    finally:staged.unlink(missing_ok=True)
    quality.update(observation_date=day,measurement_resolution_m=20,product_identity_status='Same-day process mosaic; exact tile identity not returned by provider')
    from scripts.knowledge.sources import file_sha256
    _atomic_json(metadata,{**quality,'sha256':file_sha256(path)})
    return quality


def measure_scl_quality(path,aoi):
    """AOI SCL measured support with exact state-cell areas and unknown gaps."""
    import rasterio
    import numpy as np
    from rasterio.windows import from_bounds,Window
    from rasterio.features import shapes
    frame=aoi
    with rasterio.open(path) as ds:
        if ds.crs is None:raise ValueError('SCL CRS missing')
        from pyproj import CRS
        crs=CRS.from_user_input(ds.crs)
        if not crs.is_projected or any(abs(a.unit_conversion_factor-1)>1e-8 for a in crs.axis_info[:2]):raise ValueError('SCL QA requires metric projected grid')
        if ds.transform.b or ds.transform.d:raise ValueError('Rotated SCL QA grid unsupported')
        geom=frame.to_crs(ds.crs).geometry.union_all();raw=from_bounds(*geom.bounds,transform=ds.transform)
        c0=max(0,int(math.floor(raw.col_off)));r0=max(0,int(math.floor(raw.row_off)));c1=min(ds.width,int(math.ceil(raw.col_off+raw.width)));r1=min(ds.height,int(math.ceil(raw.row_off+raw.height)))
        usable=cloud=covered=0.0
        for row in range(r0,r1,256):
            for col in range(c0,c1,256):
                window=Window(col,row,min(256,c1-col),min(256,r1-row))
                values=ds.read(1,window=window)
                if not set(np.unique(values)).issubset(set(range(12))):raise ValueError('Invalid Sentinel SCL classes')
                for polygon,state in shapes(values,mask=values!=0,transform=ds.window_transform(window)):
                    area=geom.intersection(shape(polygon)).area
                    covered+=area
                    if state in (4,5):usable+=area
                    elif state in (3,8,9,10):cloud+=area
        return {'qa_state':'measured','usable_support':usable/geom.area,'cloud_shadow_fraction':cloud/geom.area,'coverage_fraction':covered/geom.area,'qa_note':'Measured SCL vegetation/bare ground support; water excluded, vegetation remains subject to candidate screening'}
