"""Verified, reusable regional OSM snapshots independent of Overpass workers."""
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

import requests
from shapely.geometry import Polygon
from shapely.ops import unary_union

MAX_BYTES=750_000_000
BASE='https://download.geofabrik.de/asia/india/southern-zone'
ZONES=('southern-zone','northern-zone','central-zone','eastern-zone','western-zone','north-eastern-zone')


def snapshot_timestamp(path):
    """Read the bounded OSM PBF header's replication timestamp (protobuf field 32)."""
    import struct,zlib
    from datetime import datetime,timezone
    def fields(data):
        offset=0
        def varint():
            nonlocal offset
            value=0
            for shift in range(0,70,7):
                byte=data[offset];offset+=1;value|=(byte&127)<<shift
                if byte<128:return value
            raise ValueError('Malformed OSM PBF varint')
        result={}
        while offset<len(data):
            key=varint();wire=key&7
            if wire==0:value=varint()
            elif wire==2:
                size=varint();value=data[offset:offset+size];offset+=size
            elif wire in (1,5):
                size=8 if wire==1 else 4;value=data[offset:offset+size];offset+=size
            else:raise ValueError('Unsupported OSM PBF header wire type')
            result[key>>3]=value
        return result
    with Path(path).open('rb') as stream:
        size=struct.unpack('>I',stream.read(4))[0]
        if size>65536:raise ValueError('OSM header exceeds size limit')
        header=fields(stream.read(size))
        if header.get(1)!=b'OSMHeader' or not 0<header.get(3,0)<32*1024*1024:raise ValueError('Invalid OSM PBF header')
        blob=fields(stream.read(header[3]))
    if 1 in blob:data=blob[1]
    elif 3 in blob:
        decoder=zlib.decompressobj();data=decoder.decompress(blob[3],32*1024*1024)
        if not decoder.eof:raise ValueError('Invalid or oversized compressed OSM header')
    else:raise ValueError('Unsupported OSM header compression')
    timestamp=fields(data).get(32)
    return datetime.fromtimestamp(timestamp,timezone.utc).isoformat() if timestamp else None


def checksum(path, algorithm='md5'):
    value=hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''): value.update(block)
    return value.hexdigest()


def parse_poly(text):
    lines=iter(text.splitlines()); next(lines)
    outers=[]; holes=[]
    for name in lines:
        name=name.strip()
        if not name: continue
        if name=='END': break
        points=[]
        for line in lines:
            if line.strip()=='END': break
            points.append(tuple(map(float,line.split())))
        ring=Polygon(points)
        (holes if name.startswith('!') else outers).append(ring)
    result=unary_union(outers).difference(unary_union(holes))
    if result.is_empty or not result.is_valid: raise ValueError('Invalid extract coverage polygon')
    return result


def download_extract(url,path,expected_md5,log,session=None,chunk_bytes=8*1024*1024):
    """Bounded ranged transfer; resume only under the pinned provider digest."""
    if not re.fullmatch('[a-f0-9]{32}',expected_md5): raise ValueError('Invalid provider checksum')
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and checksum(path)==expected_md5: return path
    partial=path.with_suffix('.'+expected_md5+'.part')
    if partial.exists() and checksum(partial)==expected_md5:
        partial.replace(path)
        return path
    if shutil.disk_usage(path.parent).free<MAX_BYTES*2: raise ValueError('Insufficient disk for OSM snapshot')
    session=session or requests.Session(); offset=partial.stat().st_size if partial.exists() else 0
    total=None; last_log=0
    while total is None or offset<total:
        for attempt in range(3):
            response=None
            try:
                response=session.get(url,headers={'Range':f'bytes={offset}-{offset+chunk_bytes-1}',
                                                  'Accept-Encoding':'identity','Connection':'close'},timeout=(15,30),stream=True)
                response.raise_for_status()
                match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                if response.status_code!=206 or not match: raise ValueError('OSM server did not honor bounded Range')
                start,end,size=map(int,match.groups())
                if start!=offset or end<start or end-start+1>chunk_bytes or size>MAX_BYTES or (total and total!=size):
                    raise ValueError('OSM snapshot range/size changed')
                total=size; received=0
                with partial.open('ab') as output:
                    for block in response.iter_content(chunk_size=256*1024):
                        received+=len(block)
                        if received>end-start+1: raise ValueError('OSM response exceeded requested range')
                        output.write(block)
                if received!=end-start+1: raise IOError('Truncated OSM range')
                offset+=received
                if time.monotonic()-last_log>20 or offset==total:
                    log(f'OSM extract download: {offset/1e6:.1f} / {total/1e6:.1f} MB'); last_log=time.monotonic()
                break
            except (requests.RequestException,IOError):
                if partial.exists():
                    with partial.open('r+b') as output: output.truncate(offset)
                if attempt==2: raise
                log(f'OSM extract transfer paused at {offset/1e6:.1f} MB; retrying this range ({attempt+1}/2)')
            finally:
                if response is not None: response.close()
    if checksum(partial)!=expected_md5:
        partial.unlink(missing_ok=True)
        raise ValueError('OSM snapshot checksum mismatch; source changed or download is corrupt')
    partial.replace(path)
    return path


def choose_coverage(query_geometry,session):
    failures=[]
    for zone in ZONES:
        base=BASE.rsplit('/',1)[0]+'/'+zone
        try:
            response=session.get(base+'.poly',timeout=(15,20));response.raise_for_status()
            if parse_poly(response.text).covers(query_geometry):return base,response.text
        except (requests.RequestException,ValueError) as exc:failures.append(type(exc).__name__)
    raise ValueError('No available regional OSM extract covers the entire boundary plus halo; choose a smaller region or retry unavailable coverage files. '+','.join(failures))


def obtain_snapshot(root,query_geometry,log):
    session=requests.Session()
    base,coverage=choose_coverage(query_geometry,session)
    # Resolve latest once, then pin both bytes and checksum to that dated URL.
    # CDN caches can otherwise serve a latest sidecar from a different edition.
    response=session.get(base+'-latest.osm.pbf',headers={'Range':'bytes=0-0'},
                         allow_redirects=False,timeout=(15,30),stream=True)
    response.raise_for_status()
    url=response.headers.get('Location','');response.close()
    if not re.fullmatch(re.escape(base)+r'-\d{6}\.osm\.pbf',url):
        raise ValueError('OSM provider did not resolve to a trusted dated extract')
    for attempt in range(3):
        try:
            response=session.get(url+'.md5',timeout=(15,30));response.raise_for_status();break
        except requests.RequestException:
            if attempt==2:raise
    expected=response.text.split()[0]
    if not re.fullmatch('[a-f0-9]{32}',expected): raise ValueError('Invalid OSM provider checksum')
    folder=Path(root)/'data/raw/osm-extracts'/base.rsplit('/',1)[1]/expected
    folder.mkdir(parents=True,exist_ok=True)
    if not (folder/'coverage.poly').exists():(folder/'coverage.poly').write_text(coverage,encoding='utf-8')
    path=download_extract(url,folder/'source.osm.pbf',expected,log,session=session)
    metadata={'provider':'Geofabrik / OpenStreetMap contributors','url':url,
              'provider_md5':expected,'sha256':checksum(path,'sha256'),'size_bytes':path.stat().st_size,
              'coverage':'source .poly covers AOI plus obstacle halo','license':'ODbL 1.0',
              'raw_path':str(path),'raw_sha256':checksum(path,'sha256')}
    metadata['source_timestamp']=snapshot_timestamp(path)
    if not (folder/'snapshot.json').exists():(folder/'snapshot.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return path,metadata


def extract_groups(source,query_geometry,groups,log,workdir,audit=None):
    """Reconstruct whole geometries before spatial selection, with bounded batches.

    A source-level bbox filter is deliberately forbidden: it can discard nodes
    referenced by ways crossing the region. GDAL keeps its node index on disk.
    """
    import geopandas as gpd
    import pyogrio
    import shapely
    import warnings
    config=Path(workdir)/'osmconf.ini'
    default=Path(pyogrio.__file__).parent/'gdal_data/osmconf.ini'
    text=default.read_text(encoding='utf-8').replace('#all_tags=yes','all_tags=yes')
    area_rules=('man_made=water_works,man_made=wastewater_plant,man_made=works,'
                'man_made=storage_tank,man_made=reservoir_covered,man_made=water_tower,'
                'power=plant,power=substation,power=generator')
    text=re.sub(r'^(closed_ways_are_polygons=.*)$',lambda match:match.group(1)+','+area_rules,text,flags=re.MULTILINE)
    text=text.replace('#report_all_tags=yes','report_all_tags=yes').replace('#tags_format=json','tags_format=json')
    text=re.sub(r'^ignore=.*$', 'ignore=',text,flags=re.MULTILINE)
    config.write_text(text,encoding='utf-8')
    rows={key:[] for key in groups}; geometries={key:[] for key in groups}
    for layer in ('points','lines','multilinestrings','multipolygons','other_relations'):
        log(f'Reading regional OSM snapshot: {layer}')
        # No spatial filter or max_features: exhaust every source layer.
        with warnings.catch_warnings(record=True) as diagnostics:
            # Raising from GDAL's C warning callback is ignored by Cython.
            # Collect diagnostics instead; unexpected reader warnings fail below.
            warnings.simplefilter('always',RuntimeWarning)
            # SELECT declares the single layer of interest to GDAL. Without it,
            # unread layers can overflow its feature queues on regional PBFs.
            with pyogrio.open_arrow(source,sql=f'SELECT * FROM "{layer}"',sql_dialect='OGRSQL',CONFIG_FILE=str(config),
                                   TAGS_FORMAT='JSON',USE_CUSTOM_INDEXING='YES' if str(source).endswith('.pbf') else 'NO',
                                   INTERLEAVED_READING='NO',use_pyarrow=True,batch_size=32768) as (_,reader):
                for batch in reader:
                    geometry_column=next((f.name for f in batch.schema if f.metadata and
                        f.metadata.get(b'ARROW:extension:name')==b'geoarrow.wkb'),None)
                    geometry_column=geometry_column or next((n for n in batch.schema.names if n in ('wkb_geometry','geometry')),None)
                    if geometry_column is None: raise ValueError('OSM reader returned no geometry column')
                    geoms=shapely.from_wkb(batch.column(geometry_column).to_pylist())
                    selected=shapely.intersects(geoms,query_geometry)
                    for index in selected.nonzero()[0]:
                        values={name:batch.column(name)[int(index)].as_py() for name in batch.schema.names if name!=geometry_column}
                        tags=json.loads(values.get('all_tags') or '{}')
                        if not isinstance(tags,dict): raise ValueError('OSM reader returned malformed tags')
                        geom=geoms[index]
                        if geom is None or geom.is_empty or not geom.is_valid:
                            raise ValueError('OSM source contains invalid relevant geometry')
                        ident=values.get('osm_way_id') or values.get('osm_id')
                        element='way' if values.get('osm_way_id') or layer=='lines' else ('node' if layer=='points' else 'relation')
                        attrs=json.dumps({'element':element,'id':ident,'tags':tags},ensure_ascii=False)
                        for name,criteria in groups.items():
                            if any(key in tags and (rule is True or tags[key] in (rule if isinstance(rule,list) else [rule])) for key,rule in criteria.items()):
                                rows[name].append(attrs);geometries[name].append(geom)
        messages=sorted(set(str(item.message) for item in diagnostics))
        if audit is not None and messages:audit[layer]=messages
        unexpected=[message for message in messages if not message.startswith(('Non closed ring detected.','organizePolygons() received an unexpected geometry.'))]
        if unexpected:raise ValueError('OSM reader reported an unexpected diagnostic: '+'; '.join(unexpected))
        if messages:log(f'OSM {layer}: retained {len(messages)} source-wide geometry diagnostic types; selected regional geometries were validated')
    return {name:gpd.GeoDataFrame({'attributes':rows[name]},geometry=geometries[name],crs=4326) for name in groups}


def cached_snapshot(root,query_geometry):
    records=[]
    for record in (Path(root)/'data/raw/osm-extracts').glob('*/*/snapshot.json'):
        try:records.append((json.loads(record.read_text(encoding='utf-8')).get('source_timestamp') or '',record))
        except (OSError,ValueError):continue
    for _,record in sorted(records,reverse=True):
        try:
            metadata=json.loads(record.read_text(encoding='utf-8'))
            source=record.parent/'source.osm.pbf'
            if (parse_poly((record.parent/'coverage.poly').read_text(encoding='utf-8')).covers(query_geometry)
                    and source.stat().st_size==metadata['size_bytes']
                    and checksum(source,'sha256')==metadata['sha256']):
                return source,metadata
        except (OSError,ValueError,KeyError): continue
    return None


def acquire_from_extract(aoi,path,log,include_context=False):
    from .acquisition import ROOT,GROUPS,REQUIRED_OSM_GROUPS,hazard_query_aoi
    from datetime import datetime,timezone
    from .source_store import input_guard
    query=hazard_query_aoi(aoi).geometry.union_all()
    attempt=Path(path).parent/'attempt.json'
    refresh=json.loads(attempt.read_text(encoding='utf-8')).get('refresh',False) if attempt.exists() else False
    with input_guard(ROOT/'data/raw/osm-extracts/download'):
        source,metadata=(None if refresh else cached_snapshot(ROOT,query)) or obtain_snapshot(ROOT,query,log)
    path=Path(path); archive=path.parent/'archive';archive.mkdir(parents=True,exist_ok=True)
    wanted={k:v for k,v in GROUPS.items() if include_context or k in REQUIRED_OSM_GROUPS}
    reader_diagnostics={}
    frames=extract_groups(source,query,wanted,log,archive,audit=reader_diagnostics)
    temporary=path.with_name('osm-extract-staging.gpkg');temporary.unlink(missing_ok=True)
    counts={}
    try:
        for layer,frame in frames.items():
            frame.to_file(temporary,layer=layer,driver='GPKG');counts[layer]=len(frame)
        # Atomically replace only this isolated acquisition's intermediate file.
        temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)
    metadata={**metadata,'acquired_at':datetime.now(timezone.utc).isoformat(),
              'date_status':'provider extract snapshot; not the imagery observation date',
              'reader_diagnostics':reader_diagnostics,
              'layer_counts':counts,'external_evidence':[str(source),str(source.parent/'coverage.poly'),str(source.parent/'snapshot.json')],
              'raw_layout':'Checksum-verified original PBF in shared data/raw/osm-extracts; regional GeoPackage is an adapter derivative.'}
    (archive/'extract-provenance.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    log('OSM regional extraction complete: '+', '.join(f'{k}={v}' for k,v in counts.items()))
    return metadata
