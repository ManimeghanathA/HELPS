import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from scripts.pipeline.source_store import SourceStore


def store(root, region='area', offset=0):
    aoi=gpd.GeoDataFrame(geometry=[box(75+offset,13,75.01+offset,13.01)],crs=4326)
    return SourceStore(root,region,aoi)


def callbacks(calls, fail=False):
    def download(folder):
        calls.append('download')
        (folder/'provider.txt').write_text('original')
        if fail:raise RuntimeError('offline')
        return {'source':'provider.txt'},{'snapshot_date':'2026-10-18','provider':'test'}
    def prepare(raw,folder,metadata):
        calls.append('prepare')
        (folder/'ready.txt').write_text(raw['source'].read_text())
        return {'source':'ready.txt'},metadata
    def validate(paths,metadata):
        if paths['source'].read_text()!='original':raise ValueError('invalid source')
    return download,prepare,validate


def test_processed_then_raw_then_download_and_cross_date_context_reuse(tmp_path):
    s=store(tmp_path);calls=[];download,prepare,validate=callbacks(calls)
    first=s.resolve('osm',None,download,prepare,validate)
    assert calls==['download','prepare']
    assert '/processed/area/osm/' in first['paths']['source'].as_posix()
    assert s.inspect('osm')['action']=='reuse_processed'
    assert s.resolve('osm',None,download,prepare,validate)['snapshot_id']==first['snapshot_id']
    assert calls==['download','prepare']
    first['paths']['source'].write_text('corrupt')
    assert s.inspect('osm')['action']=='process_raw'
    second=s.resolve('osm',None,download,prepare,validate)
    assert calls==['download','prepare','prepare']
    assert second['snapshot_id']!=first['snapshot_id']


def test_date_aoi_region_refresh_and_failed_refresh_are_isolated(tmp_path):
    s=store(tmp_path);calls=[];args=callbacks(calls)
    first=s.resolve('sentinel','2026-06-01',*args)
    assert s.inspect('sentinel','2026-06-02')['action']=='download'
    assert store(tmp_path,offset=.1).inspect('sentinel','2026-06-01')['action']=='download'
    assert store(tmp_path,region='other').inspect('sentinel','2026-06-01')['action']=='download'
    with pytest.raises(RuntimeError,match='offline'):
        s.resolve('sentinel','2026-06-01',*callbacks(calls,fail=True),refresh=True)
    assert s.inspect('sentinel','2026-06-01')['snapshot_id']==first['snapshot_id']
    refreshed=s.resolve('sentinel','2026-06-01',*args,refresh=True)
    assert refreshed['snapshot_id']!=first['snapshot_id']


def test_corrupt_raw_invalidates_processed_and_paths_cannot_escape(tmp_path):
    s=store(tmp_path);calls=[];args=callbacks(calls)
    first=s.resolve('osm',None,*args)
    first['raw_paths']['source'].write_text('changed')
    assert s.inspect('osm')['action']=='download'
    with pytest.raises(ValueError):store(tmp_path,region='../escape')
    with pytest.raises(ValueError):s.inspect('../escape')


def test_shared_extract_raw_evidence_is_pinned(tmp_path):
    s=store(tmp_path);calls=[];download,prepare,validate=callbacks(calls)
    shared=tmp_path/'data/raw/osm-extracts/test/source.pbf';shared.parent.mkdir(parents=True);shared.write_bytes(b'original snapshot')
    def with_shared(folder):
        files,metadata=download(folder)
        return files,{**metadata,'external_evidence':[str(shared)]}
    first=s.resolve('osm',None,with_shared,prepare,validate)
    assert s.inspect('osm')['action']=='reuse_processed'
    shared.write_bytes(b'corrupt')
    assert s.inspect('osm')['action']=='download'
    manifests=list((tmp_path/'data/processed').rglob('manifest.json'))
    data=json.loads(manifests[0].read_text());data['files']['source']['path']='../../../../outside'
    manifests[0].write_text(json.dumps(data))
    assert s.inspect('osm')['action']=='download'


def test_interrupted_or_invalid_preparation_has_no_complete_snapshot(tmp_path):
    s=store(tmp_path);calls=[];download,prepare,validate=callbacks(calls)
    def broken(raw,folder,metadata):raise ValueError('processing failed')
    with pytest.raises(ValueError):s.resolve('osm',None,download,broken,validate)
    assert s.inspect('osm')['action']=='process_raw'
    result=s.resolve('osm',None,download,prepare,validate)
    assert calls.count('download')==1
    assert result['paths']['source'].read_text()=='original'


def test_failed_download_can_resume_adapter_checkpoints_without_publishing_partial_source(tmp_path):
    s=store(tmp_path);folders=[];_,prepare,validate=callbacks([])
    def download(folder):
        folders.append(folder)
        if len(folders)==1:
            (folder/'part.txt').write_text('checked by adapter')
            raise RuntimeError('provider interrupted')
        assert (folder/'part.txt').read_text()=='checked by adapter'
        (folder/'provider.txt').write_text('original')
        return {'source':'provider.txt'},{}
    with pytest.raises(RuntimeError):s.resolve('osm',None,download,prepare,validate)
    assert s.inspect('osm')['action']=='download'
    s.resolve('osm',None,download,prepare,validate)
    assert folders[0]==folders[1]


def test_registered_download_identity_is_bounded(tmp_path):
    s=store(tmp_path);calls=[];result=s.resolve('osm',None,*callbacks(calls))
    assert s.file('osm',result['snapshot_id'],'processed','source')==result['paths']['source']
    with pytest.raises(ValueError):s.file('osm','../escape','processed','source')
    with pytest.raises(ValueError):s.file('osm',result['snapshot_id'],'processed','unknown')


def test_concurrent_resolution_has_one_download_and_complete_snapshot(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    s=store(tmp_path);calls=[];args=callbacks(calls)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:s.resolve('osm',None,*args),range(2)))
    assert calls==['download','prepare']
    assert results[0]['snapshot_id']==results[1]['snapshot_id']


@pytest.mark.parametrize('field',['snapshot_id','metadata','phase'])
def test_malformed_complete_manifest_is_skipped(tmp_path,field):
    s=store(tmp_path);result=s.resolve('osm',None,*callbacks([]))
    data=json.loads(result['manifest_path'].read_text());data.pop(field)
    result['manifest_path'].write_text(json.dumps(data))
    assert s.inspect('osm')['action']=='process_raw'
