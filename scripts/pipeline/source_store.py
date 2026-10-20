"""Immutable per-region input snapshots; processed -> raw -> acquisition.

No scientific file is moved or replaced. A completion manifest is published last.
Callers supply source-specific validation and preparation, never client paths.
"""
import hashlib
import json
import re
import os
import time
from contextlib import contextmanager
from threading import Lock
from datetime import date as calendar_date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import shapely

from scripts.knowledge.repository import _atomic_json
from scripts.knowledge.sources import file_sha256

KINDS={'boundary','sentinel','dem','osm','overture','landcover'}
PREPARATION_VERSION='region-inputs-v1'
_locks={}
_locks_guard=Lock()


@contextmanager
def input_guard(path):
    """Source acquisition cannot hold the knowledge-publication mutex."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with _locks_guard:lock=_locks.setdefault(str(path.resolve()),Lock())
    with lock,open(str(path)+'.lock','a+b') as handle:
        handle.seek(0)
        if not handle.read(1):handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            deadline=time.monotonic()+120
            while True:
                try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError:
                    if time.monotonic()>deadline:raise ValueError('Region inputs are processing; retry when the active input task completes')
                    time.sleep(.05)
            try:yield
            finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
            try:yield
            finally:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def safe_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',value):
        raise ValueError('Invalid region or snapshot identity')
    return value


class SourceStore:
    def __init__(self,root,region_id,aoi):
        self.root=Path(root).resolve();self.region_id=safe_id(region_id)
        self.aoi=aoi
        if aoi.empty or aoi.crs is None or any(g is None or g.is_empty or not g.is_valid for g in aoi.geometry):
            raise ValueError('Input store needs a valid region boundary')
        geometry=shapely.normalize(aoi.to_crs(4326).geometry.union_all())
        self.aoi_hash=hashlib.sha256(geometry.wkb).hexdigest()

    def base(self,phase,kind,day=None):
        if phase not in ('raw','processed') or kind not in KINDS:raise ValueError('Unknown input kind or phase')
        path=self.root/'data'/phase/self.region_id/kind
        if kind=='sentinel':
            if not day or calendar_date.fromisoformat(day).isoformat()!=day:raise ValueError('Sentinel observation date required')
            path=path/day
        return path

    def _path(self,text):
        p=(self.root/text).resolve()
        data=self.root/'data'
        if not p.is_relative_to(data) or not p.is_file():raise ValueError('Input file outside registered data or missing')
        return p

    def _record(self,path):
        p=self._path(str(Path(path).resolve()))
        return {'path':p.relative_to(self.root).as_posix(),'sha256':file_sha256(p)}

    def _paths(self,records):
        if not isinstance(records,dict) or not records:raise ValueError('Input manifest has no files')
        paths={}
        for key,record in records.items():
            p=self._path(record['path'])
            if file_sha256(p)!=record['sha256']:raise ValueError('Input checksum changed')
            paths[key]=p
        return paths

    def _load(self,path,kind,day):
        record=json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(record,dict) or record.get('phase')!=path.relative_to(self.root/'data').parts[0] or
            not isinstance(record.get('metadata'),dict) or record.get('snapshot_id')!=path.parent.name or
            record.get('schema')!=1 or record.get('region_id')!=self.region_id or
            record.get('aoi_hash')!=self.aoi_hash or record.get('kind')!=kind or
            record.get('date')!=(day if kind=='sentinel' else None) or record.get('status')!='complete'):
            raise ValueError('Input identity mismatch')
        self._paths(record['files'])
        if record.get('evidence'):self._paths(record['evidence'])
        if record.get('phase')=='processed':
            if record.get('preparation_version')!=PREPARATION_VERSION:raise ValueError('Input processing changed')
            if record.get('raw_manifest'):
                parent=self._path(record['raw_manifest']['path'])
                if file_sha256(parent)!=record['raw_manifest']['sha256']:raise ValueError('Raw manifest changed')
                self._load(parent,kind,day)
        return record

    def _find(self,phase,kind,day,validator=None):
        for p in sorted(self.base(phase,kind,day).glob('*/manifest.json'),reverse=True):
            try:
                record=self._load(p,kind,day)
                if validator:validator(self._paths(record['files']),record['metadata'])
                return record,p
            except (OSError,ValueError,KeyError,TypeError,AttributeError):continue
        return None,None

    def inspect(self,kind,day=None,refresh=False):
        self.base('raw',kind,day)
        phase='processed';record,path=self._find(phase,kind,day)
        action='reuse_processed'
        if not record:
            phase='raw';record,path=self._find(phase,kind,day);action='process_raw' if record else 'download'
        if refresh:action='download'
        return {'kind':kind,'action':action,'snapshot_id':record['snapshot_id'] if record else None,
                'metadata':record.get('metadata',{}) if record else {},
                'files':record['files'] if record else {},'phase':phase if record else None,
                'raw_directory':str(self.base('raw',kind,day)),
                'processed_directory':str(self.base('processed',kind,day)),
                'refresh_requested':bool(refresh)}

    def _manifest(self,phase,kind,day,folder,files,metadata,raw_manifest=None):
        paths={key:(folder/value).resolve() for key,value in files.items()}
        # Downloads/preparations may only publish outputs in their staging folder.
        if any(not p.is_relative_to(folder.resolve()) for p in paths.values()):raise ValueError('Adapter output outside snapshot')
        record={'schema':1,'status':'complete','phase':phase,'region_id':self.region_id,
                'kind':kind,'date':day if kind=='sentinel' else None,'aoi_hash':self.aoi_hash,
                'snapshot_id':folder.name,'created_at':datetime.now(timezone.utc).isoformat(),
                'preparation_version':PREPARATION_VERSION,'files':{k:self._record(p) for k,p in paths.items()},
                'metadata':metadata}
        # Pin every raw response/tile too, not just an adapter's convenient mosaic.
        if phase=='raw':record['evidence']={str(i):self._record(p) for i,p in enumerate(sorted(folder.rglob('*'))) if p.is_file() and p.name!='manifest.json'}
        if phase=='raw' and metadata.get('external_evidence'):
            for i,p in enumerate(metadata['external_evidence']):record['evidence']['external_'+str(i)]=self._record(p)
        if raw_manifest:record['raw_manifest']=self._record(raw_manifest)
        _atomic_json(folder/'manifest.json',record)
        return record,folder/'manifest.json'

    def _folder(self,phase,kind,day):
        folder=self.base(phase,kind,day)/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'_'+uuid4().hex[:8])
        folder.mkdir(parents=True,exist_ok=False)
        return folder

    def _download_folder(self,kind,day,refresh):
        identity={'aoi_hash':self.aoi_hash,'region_id':self.region_id,'kind':kind,
                  'date':day if kind=='sentinel' else None,'refresh':bool(refresh),'version':PREPARATION_VERSION}
        for path in sorted(self.base('raw',kind,day).glob('*/attempt.json'),reverse=True):
            if (path.parent/'manifest.json').exists():continue
            try:
                if json.loads(path.read_text(encoding='utf-8'))==identity:return path.parent
            except (OSError,ValueError):continue
        folder=self._folder('raw',kind,day);_atomic_json(folder/'attempt.json',identity)
        return folder

    def _result(self,record,manifest):
        raw_paths={}
        if record.get('raw_manifest'):
            raw=self._load(self._path(record['raw_manifest']['path']),record['kind'],record['date'])
            raw_paths=self._paths(raw['files'])
        return {**record,'paths':self._paths(record['files']),'raw_paths':raw_paths,'manifest_path':manifest}

    def resolve(self,kind,day,download,prepare,validate,refresh=False,log=print):
        guard=self.root/'data/raw'/self.region_id/'.inputs'
        guard.parent.mkdir(parents=True,exist_ok=True)
        with input_guard(guard):
            if not refresh:
                record,path=self._find('processed',kind,day,validate)
                if record:
                    log(f'{kind}: reusing processed input · {path.parent}')
                    return self._result(record,path)
            raw,raw_manifest=(None,None) if refresh else self._find('raw',kind,day)
            if raw is None:
                folder=self._download_folder(kind,day,refresh)
                log(f'{kind}: downloading missing raw input · {folder}')
                files,metadata=download(folder)
                raw,raw_manifest=self._manifest('raw',kind,day,folder,files,metadata)
            folder=self._folder('processed',kind,day)
            log(f'{kind}: preparing raw input · {folder}')
            files,metadata=prepare(self._paths(raw['files']),folder,raw['metadata'])
            validate({k:folder/v for k,v in files.items()},metadata)
            record,path=self._manifest('processed',kind,day,folder,files,metadata,raw_manifest)
            return self._result(record,path)

    def adopt(self,kind,day,paths,metadata,validate,phase='processed'):
        """Register verified existing processed evidence in place, without moving it.

        Legacy analysis-ready files are not mislabelled as direct raw downloads.
        Their original paths/hashes remain pinned in the new processed manifest.
        """
        validate(paths,metadata)
        guard=self.root/'data/raw'/self.region_id/'.inputs';guard.parent.mkdir(parents=True,exist_ok=True)
        with input_guard(guard):
            existing,p=self._find(phase,kind,day,validate)
            if existing and {k:v['sha256'] for k,v in existing['files'].items()}=={k:file_sha256(v) for k,v in paths.items()}:
                return self._result(existing,p)
            folder=self._folder(phase,kind,day)
            record={'schema':1,'status':'complete','phase':phase,'region_id':self.region_id,
                    'kind':kind,'date':day if kind=='sentinel' else None,'aoi_hash':self.aoi_hash,
                    'snapshot_id':folder.name,'created_at':datetime.now(timezone.utc).isoformat(),
                    'preparation_version':PREPARATION_VERSION,'files':{k:self._record(p) for k,p in paths.items()},
                    'metadata':{**metadata,'adopted_in_place':True}}
            if metadata.get('raw_path'):
                original=self._record(metadata['raw_path'])
                if original['sha256']!=metadata.get('raw_sha256'):raise ValueError('Uploaded raw evidence changed')
                record['evidence']={'original_upload':original}
            _atomic_json(folder/'manifest.json',record)
            return self._result(record,folder/'manifest.json')

    def file(self,kind,snapshot_id,phase,key,day=None):
        path=self.base(phase,kind,day)/safe_id(snapshot_id)/'manifest.json'
        try:
            record=self._load(path,kind,day)
            return self._paths(record['files'])[key]
        except (OSError,KeyError,ValueError,TypeError):raise ValueError('Registered source file unavailable') from None
