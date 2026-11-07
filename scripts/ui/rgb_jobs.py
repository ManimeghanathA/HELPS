"""Persistent RGB build status and detached worker entry point."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
from uuid import uuid4

from scripts.knowledge.repository import _atomic_json, registry_guard
from scripts.knowledge.sources import file_sha256


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None


def process_alive(pid):
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    api.OpenProcess.restype = wintypes.HANDLE
    api.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = api.OpenProcess(0x1000, False, pid)
    if not handle:
        return ctypes.get_last_error() == 5
    try:
        status = wintypes.DWORD()
        return bool(api.GetExitCodeProcess(handle, ctypes.byref(status)) and status.value == 259)
    finally:
        api.CloseHandle(handle)


class RgbJobs:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.managed = self.root / 'data/knowledge'
        self.storage = self.managed / 'rgb-jobs'

    def path(self, job_id):
        if not re.fullmatch(r'[a-f0-9]{32}', job_id):
            raise ValueError('Invalid RGB job ID.')
        return self.storage / (job_id + '.json')

    def get(self, job_id):
        if not re.fullmatch(r'[a-f0-9]{32}', job_id):
            return None
        job = read_json(self.path(job_id))
        if job and job['status'] in ('queued', 'running'):
            process = read_json(self.folder(job) / 'worker-process.json')
            if process and process['attempt'] == job['attempt'] and not process_alive(process['pid']):
                job.update(status='failed', stage='Worker stopped', error='Resume to reuse completed tiles.')
            elif not process or process['attempt'] != job['attempt']:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(job['updated_at'])).total_seconds()
                if age > 60:
                    job.update(status='failed', stage='Worker did not start', error='Resume to retry the build.')
        return job

    def list(self):
        rows = (self.get(p.stem) for p in self.storage.glob('*.json'))
        return sorted((job for job in rows if job), key=lambda j: j['created_at'], reverse=True)

    def folder(self, job):
        return self.managed / 'datasets' / job['dataset_id']

    def update_review(self, job_id, review):
        job = read_json(self.path(job_id))
        if job is None or job['status'] != 'completed':
            raise ValueError('Only completed RGB jobs can be reviewed.')
        _atomic_json(self.path(job_id), {**job, 'review': review})

    def launch(self, job):
        folder = self.folder(job)
        job.update(status='queued', stage='Starting the background worker', updated_at=now(), attempt=uuid4().hex,
                   progress={'percent': 0, 'indeterminate': False})
        job.pop('error', None)
        _atomic_json(self.path(job['job_id']), job)
        command = [sys.executable, '-m', 'scripts.ui.rgb_jobs', job['job_id'], job['attempt']]
        options = {'cwd': self.root, 'stdin': subprocess.DEVNULL, 'stderr': subprocess.STDOUT}
        if os.name == 'nt':
            detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            options['creationflags'] = detached | 0x01000000
        else:
            options['start_new_session'] = True
        try:
            with (folder / 'worker.log').open('ab') as stream:
                options['stdout'] = stream
                try:
                    process = subprocess.Popen(command, **options)
                except OSError as exc:
                    if os.name != 'nt' or getattr(exc, 'winerror', None) != 5:
                        raise
                    options['creationflags'] = detached
                    process = subprocess.Popen(command, **options)
            _atomic_json(folder / 'worker-process.json', {'pid': process.pid, 'attempt': job['attempt']})
        except OSError:
            job.update(status='failed', stage='Could not start worker', error='Check the worker log and resume.')
            _atomic_json(self.path(job['job_id']), job)
        return job

    def assert_available(self):
        if any(j['status'] in ('queued', 'running') for j in self.list()):
            raise ValueError('An RGB build is already running. Wait for it to finish.')

    def submit(self, name, day, boundary, image, resolution):
        from scripts.knowledge.rgb_ingestion import (
            MAX_BOUNDARY_BYTES, MAX_IMAGE_BYTES, inspect_inputs, valid_date)
        from scripts.knowledge.rgb_model import runtime_config

        name = ' '.join((name or '').split())
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        if not slug or len(name) > 80 or len(slug) > 60:
            raise ValueError('Enter a region name containing letters or digits (up to 60 for its identifier).')
        region_id = 'rgb-' + slug
        with registry_guard(self.storage / 'submission'):
            self.assert_available()
            registry = read_json(self.managed / 'registry.json') or {}
            current = registry.get('selected', {}).get(region_id)
            day = valid_date(day, registry.get('datasets', {}).get(current, {}).get('date'))
            runtime_config(self.root)
            job_id = uuid4().hex
            dataset_id = f'{region_id}-{day.replace("-", "")}-{job_id[:8]}'
            job = dict(job_id=job_id, dataset_id=dataset_id, region_id=region_id,
                       region_name=name, date=day, created_at=now(), history=[], producer='rgb')
            folder = self.folder(job)
            folder.mkdir(parents=True, exist_ok=False)
            try:
                paths = ((boundary, folder / 'boundary.geojson', MAX_BOUNDARY_BYTES),
                         (image, folder / 'rgb.tif', MAX_IMAGE_BYTES))
                for upload, path, limit in paths:
                    remaining = limit
                    with path.open('wb') as out:
                        while chunk := upload.stream.read(min(remaining+1, 1024*1024)):
                            remaining -= len(chunk)
                            if remaining < 0:
                                raise ValueError('The GeoJSON must be at most 2 MiB and RGB GeoTIFF at most 256 MiB.')
                            out.write(chunk)
                    if remaining == limit:
                        raise ValueError('Upload nonempty GeoJSON and RGB GeoTIFF files.')
                aoi, metres, _, _, _, tiles = inspect_inputs(paths[0][1], paths[1][1], day, resolution)
                digest = file_sha256(paths[1][1])
                for old in self.list():
                    plan = read_json(self.folder(old) / 'rgb-plan.json')
                    if plan and plan['image_sha256'] == digest and old['date'] != day:
                        raise ValueError('These image bytes were already submitted with a different capture date.')
                job.update(resolution_m=metres, tile_count=len(tiles), area_km2=aoi.area.iloc[0]/1e6)
                _atomic_json(folder / 'rgb-plan.json', {
                    'resolution_m': metres, 'image_sha256': digest, 'boundary_sha256': file_sha256(paths[0][1])})
            except Exception:
                for filename in ('boundary.geojson', 'rgb.tif', 'rgb-plan.json'):
                    (folder / filename).unlink(missing_ok=True)
                folder.rmdir()
                raise
            return self.launch(job)

    def resume(self, job_id):
        with registry_guard(self.storage / 'submission'):
            job = self.get(job_id)
            if job is None or job['status'] != 'failed':
                raise ValueError('Only a failed or interrupted RGB job can be resumed.')
            self.assert_available()
            return self.launch(job)

    def work(self, job_id, attempt):
        from scripts.knowledge.rgb_ingestion import build_rgb

        path = self.path(job_id)
        job = read_json(path)
        if not job or job['attempt'] != attempt:
            return 1
        folder = self.folder(job)
        with registry_guard(folder / 'worker'):
            job = read_json(path)
            if job['attempt'] != attempt or job['status'] != 'queued':
                return 1
            def update(status, stage, percent):
                job.update(status=status, stage=stage, updated_at=now(),
                           progress={'percent': percent, 'indeterminate': False})
                job['history'] = [*job['history'], {'time': now(), 'stage': stage}][-150:]
                _atomic_json(path, job)
                print(stage, flush=True)

            try:
                result = build_rgb(self.root, folder, job, lambda stage, pct: update('running', stage, pct))
                job.update(result=result, review={'decision': 'pending'})
                update('completed', 'Ready for review', 100)
            except Exception as exc:
                traceback.print_exc()
                job['error'] = str(exc)
                update('failed', 'RGB build failed', job['progress']['percent'])
                return 1
        return 0


if __name__ == '__main__':
    sys.exit(RgbJobs(Path.cwd()).work(*sys.argv[1:]))
