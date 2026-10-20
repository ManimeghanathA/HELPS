import hashlib
import pytest
from scripts.pipeline.osm_extract import download_extract, parse_poly


class Response:
    def __init__(self, body, start, total):
        self.body=body; self.status_code=206
        self.headers={'Content-Range':f'bytes {start}-{start+len(body)-1}/{total}'}
    def raise_for_status(self): pass
    def iter_content(self, chunk_size): yield self.body
    def close(self): pass


class Session:
    def __init__(self, data): self.data=data; self.calls=[]
    def get(self, url, headers, **kwargs):
        start,end=map(int,headers['Range'][6:].split('-'))
        self.calls.append(start)
        return Response(self.data[start:end+1],start,len(self.data))


def test_download_verifies_and_reuses(tmp_path):
    body=b'OSM-test-data'; session=Session(body)
    expected=hashlib.md5(body).hexdigest()
    path=download_extract('https://example.test/map.pbf',tmp_path/'map.pbf',expected,print,session=session,chunk_bytes=4)
    assert path.read_bytes()==body
    calls=len(session.calls)
    download_extract('https://example.test/map.pbf',path,expected,print,session=session)
    assert len(session.calls)==calls


def test_bad_checksum_never_publishes(tmp_path):
    with pytest.raises(ValueError,match='checksum'):
        download_extract('https://example.test/map.pbf',tmp_path/'map.pbf','0'*32,print,session=Session(b'bad'))
    assert not (tmp_path/'map.pbf').exists()


def test_completed_partial_recovers_without_another_request(tmp_path):
    body=b'complete download';expected=hashlib.md5(body).hexdigest();session=Session(body)
    path=tmp_path/'source.pbf';path.with_suffix('.'+expected+'.part').write_bytes(body)
    assert download_extract('https://example.test/source.pbf',path,expected,print,session=session).read_bytes()==body
    assert session.calls==[]


def test_extract_replication_date_is_not_imagery_date(tmp_path):
    from scripts.pipeline.osm_extract import snapshot_timestamp
    import struct,zlib
    def varint(value):
        out=bytearray()
        while value>127:out.append((value&127)|128);value>>=7
        return bytes(out)+bytes([value])
    def binary(number,value):return varint((number<<3)|2)+varint(len(value))+value
    headerblock=varint(32<<3)+varint(1_760_000_000)
    blob=varint(2<<3)+varint(len(headerblock))+binary(3,zlib.compress(headerblock))
    header=binary(1,b'OSMHeader')+varint(3<<3)+varint(len(blob))
    source=tmp_path/'header.pbf';source.write_bytes(struct.pack('>I',len(header))+header+blob)
    assert snapshot_timestamp(source)=='2025-10-09T08:53:20+00:00'


def test_poly_holes():
    shape=parse_poly('test\n1\n0 0\n4 0\n4 4\n0 4\n0 0\nEND\n!2\n1 1\n2 1\n2 2\n1 2\n1 1\nEND\nEND\n')
    assert shape.area==15


def test_new_region_uses_extract_that_covers_entire_boundary():
    from scripts.pipeline.osm_extract import choose_coverage
    from shapely.geometry import box
    class Text:
        def __init__(self,text):self.text=text
        def raise_for_status(self):pass
    class CoverageSession:
        def get(self,url,**kwargs):
            low=30 if 'northern-zone' in url else 0
            return Text(f'region\n1\n{low} {low}\n{low+5} {low}\n{low+5} {low+5}\n{low} {low+5}\n{low} {low}\nEND\nEND\n')
    base,coverage=choose_coverage(box(31,31,32,32),CoverageSession())
    assert base.endswith('/northern-zone') and parse_poly(coverage).covers(box(31,31,32,32))


def test_local_extract_preserves_full_geometry_holes_and_tags(tmp_path):
    from scripts.pipeline.osm_extract import extract_groups
    from shapely.geometry import box
    from scripts.pipeline.acquisition import GROUPS
    from xml.etree.ElementTree import Element, SubElement, ElementTree
    root=Element('osm',version='0.6')
    coords=[(0,0),(4,0),(4,4),(0,4),(1,1),(2,1),(2,2),(1,2),(3,3)]
    for i,(x,y) in enumerate(coords,1):
        n=SubElement(root,'node',id=str(i),lat=str(y),lon=str(x),version='1')
        if i==9: SubElement(n,'tag',k='power',v='tower')
    for ident,refs,tags in [(10,[1,2,3,4,1],{}),(11,[5,6,7,8,5],{}),
                             (12,[1,3],{'waterway':'stream'}),
                             (13,[5,6,7,8,5],{'building':'yes','name':'Full tags'}),
                             (14,[1,2,3,4,1],{'power':'substation'}),
                             (15,[1,2,3,4,1],{'man_made':'storage_tank','area':'no'}),
                             (16,[1,2,3,4,1],{'power':'line','man_made':'pipeline'})]:
        w=SubElement(root,'way',id=str(ident),version='1')
        for ref in refs: SubElement(w,'nd',ref=str(ref))
        for k,v in tags.items(): SubElement(w,'tag',k=k,v=v)
    r=SubElement(root,'relation',id='20',version='1')
    for ref,role in [('10','outer'),('11','inner')]:SubElement(r,'member',type='way',ref=ref,role=role)
    for k,v in {'type':'multipolygon','natural':'water'}.items():SubElement(r,'tag',k=k,v=v)
    source=tmp_path/'fixture.osm';ElementTree(root).write(source,encoding='utf-8',xml_declaration=True)
    groups=extract_groups(source,box(-.1,-.1,3.5,3.5),GROUPS,print,tmp_path)
    assert max(g.area for g in groups['water'].geometry)==15
    assert len(groups['power'])==3
    assert sorted(groups['facilities'].geom_type)==['LineString','MultiPolygon']
    assert groups['power'].loc[groups['power']['attributes'].str.contains('pipeline')].geom_type.iloc[0]=='LineString'
    assert len(groups['buildings'])==1
    assert 'Full tags' in groups['buildings'].iloc[0]['attributes']
    assert groups['water'].geometry.total_bounds.tolist()==[0,0,4,4]
    assert len(groups)==9 and groups['industrial'].empty


def test_acquisition_recovers_with_snapshot_after_query_failure(tmp_path,monkeypatch):
    import geopandas as gpd
    import requests
    from shapely.geometry import box
    from scripts.pipeline import acquisition,osm_extract
    monkeypatch.setattr(acquisition,'fetch_osm_response',lambda *a,**kw: (_ for _ in ()).throw(requests.HTTPError('busy')))
    calls=[]
    def fallback(aoi,path,log,include_context=False):
        calls.append(include_context)
        for group in acquisition.GROUPS:gpd.GeoDataFrame(geometry=[],crs=4326).to_file(path,layer=group,driver='GPKG')
        return {'provider':'verified-test-snapshot'}
    monkeypatch.setattr(osm_extract,'acquire_from_extract',fallback)
    meta=acquisition.osm(gpd.GeoDataFrame(geometry=[box(75,13,75.01,13.01)],crs=4326),tmp_path/'osm.gpkg',print,include_context=True)
    assert calls==[True] and acquisition.osm_complete(tmp_path/'osm.gpkg',True)
    assert meta['provider']=='verified-test-snapshot'


def test_closed_facility_boundary_excludes_its_interior():
    import geopandas as gpd
    from shapely.geometry import LineString,Point
    from scripts.pipeline.processing import prepare_facility_exclusion
    ring=LineString([(0,0),(100,0),(100,100),(0,100),(0,0)])
    result=prepare_facility_exclusion(gpd.GeoDataFrame(geometry=[ring],crs=32643))
    assert result.geometry.iloc[0].contains(Point(50,50))
    explicit_line=prepare_facility_exclusion(gpd.GeoDataFrame({'area':['no']},geometry=[ring],crs=32643))
    assert not explicit_line.geometry.iloc[0].contains(Point(50,50))
