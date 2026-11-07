import io
import json
from types import SimpleNamespace

from flask import Flask
import numpy as np
from pyproj import Transformer
import pytest
from rasterio.enums import ColorInterp
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import box, mapping
from shapely.ops import transform

from scripts.knowledge import rgb_ingestion, rgb_model
from scripts.knowledge.repository import write_package
from scripts.ui import rgb_jobs
from scripts.ui.api import register_api
from test_knowledge_repository import package_data


HEADERS = {'X-HELPS-Role': 'engineer'}
DAY = '2025-09-18'
WEST, SOUTH = 500000, 1500000
RGB_BUILD = '/api/knowledge/rgb/build'
RGB_JOBS = '/api/knowledge/rgb/jobs'


def make_client(root):
    app = Flask(__name__)
    app.config['TESTING'] = True
    register_api(app, root)
    return app.test_client()


def boundary(left=5, bottom=5, right=35, top=35):
    to_wgs84 = Transformer.from_crs(32643, 4326, always_xy=True)
    geometry = box(WEST + left, SOUTH + bottom, WEST + right, SOUTH + top)
    return json.dumps(mapping(transform(to_wgs84.transform, geometry))).encode()


def image(*, transparent=False, capture_date=None, metres=1):
    rgba = transparent
    with MemoryFile() as memory:
        with memory.open(driver='GTiff', width=48, height=48, count=4 if rgba else 3,
                         dtype='uint8', crs=32643, photometric='RGB',
                         transform=from_origin(WEST, SOUTH + 48, metres, metres)) as raster:
            pixels = np.full((raster.count, 48, 48), 64, dtype=np.uint8)
            if rgba:
                pixels[3] = 255
                pixels[3, 16:22, 16:22] = 0
                raster.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha)
            raster.write(pixels)
            if capture_date:
                raster.update_tags(acquisition_date=capture_date)
        return memory.read()


def upload(client, *, geometry=None, rgb=None, date=DAY, resolution=None):
    data = {
        'name': 'Test Field',
        'date': date,
        'boundary': (io.BytesIO(geometry if geometry is not None else boundary()), 'area.geojson'),
        'image': (io.BytesIO(rgb if rgb is not None else image()), 'capture.tif'),
    }
    if resolution is not None:
        data['resolution_m'] = resolution
    return client.post(RGB_BUILD, data=data, headers=HEADERS)


@pytest.fixture
def worker(tmp_path, monkeypatch):
    monkeypatch.setattr(rgb_model, 'runtime_config', lambda root: None)
    monkeypatch.setattr(rgb_jobs.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(pid=4242))
    monkeypatch.setattr(rgb_jobs, 'process_alive', lambda pid: pid == 4242)
    return rgb_jobs.RgbJobs(tmp_path)


@pytest.mark.parametrize(('input_kind', 'error_fragment'), [
    ('oversized-area', '4 km²'),
    ('outside-footprint', 'footprint must cover'),
    ('upsampled', 'without upsampling'),
    ('coarse-source', 'without upsampling'),
    ('invalid-date', 'date'),
    ('future-date', 'date'),
    ('date-metadata-conflict', 'differs from the date'),
])
def test_invalid_rgb_inputs_never_create_a_job(tmp_path, worker, input_kind, error_fragment):
    client = make_client(tmp_path)
    if input_kind == 'oversized-area':
        options = {'geometry': boundary(right=2500, top=2500)}
    elif input_kind == 'outside-footprint':
        options = {'geometry': boundary(right=60)}
    elif input_kind == 'upsampled':
        options = {'resolution': '0.5'}
    elif input_kind == 'coarse-source':
        options = {'rgb': image(metres=3)}
    elif input_kind == 'invalid-date':
        options = {'date': '2025-02-30'}
    elif input_kind == 'future-date':
        options = {'date': '2099-01-01'}
    else:
        options = {'rgb': image(capture_date='2025-09-19')}
    response = upload(client, **options)
    assert response.status_code == 400, response.json
    assert error_fragment in response.json['error']
    assert client.get(RGB_JOBS, headers=HEADERS).json == {'jobs': []}


def test_transparent_pixels_fail_before_elevation_or_segmentation(tmp_path, worker):
    response = upload(make_client(tmp_path), rgb=image(transparent=True))
    assert response.status_code == 202, response.json
    job = response.json
    assert worker.work(job['job_id'], job['attempt']) == 1
    reopened = make_client(tmp_path)
    failed = reopened.get(RGB_JOBS, headers=HEADERS).json['jobs'][0]
    assert failed['status'] == 'failed'
    assert 'uncovered or transparent' in failed['error']
    assert failed['progress']['percent'] == 4


def test_job_survives_reopening_and_only_explicit_review_publishes(tmp_path, worker, monkeypatch):
    response = upload(make_client(tmp_path))
    assert response.status_code == 202, response.json
    queued = response.json
    assert queued['status'] == 'queued'
    assert queued['resolution_m'] == pytest.approx(1.0)
    assert queued['tile_count'] == 1
    assert queued['region_id'] == 'rgb-test-field'

    reopened = make_client(tmp_path)
    assert reopened.get(RGB_JOBS, headers=HEADERS).json['jobs'][0]['job_id'] == queued['job_id']
    job_path = '/api/knowledge/jobs/' + queued['job_id']
    assert reopened.get(job_path).json['status'] == 'queued'

    def build_fixture(root, folder, job, progress):
        progress('Packaging candidates for review', 93)
        data = package_data()
        data['metadata'].update(dataset_id=job['dataset_id'], region_id=job['region_id'], date=job['date'])
        for frame in (data['terrain'], data['zones']):
            frame['dataset_id'] = job['dataset_id']
        package = folder / 'knowledge.gpkg'
        write_package(data, package)
        return {'package_path': str(package)}

    monkeypatch.setattr(rgb_ingestion, 'build_rgb', build_fixture)
    assert worker.work(queued['job_id'], queued['attempt']) == 0
    pending = reopened.get(RGB_JOBS, headers=HEADERS).json['jobs'][0]
    assert pending['review']['decision'] == 'pending'
    assert pending['progress']['percent'] == 100
    assert not (worker.managed / 'registry.json').exists()
    assert reopened.post(job_path + '/accept', json={}, headers=HEADERS).status_code == 400
    summary = reopened.get(job_path + '/preview', headers=HEADERS)
    assert summary.status_code == 200, summary.json
    assert summary.json['proposed']['candidate_count'] == 1
    preview = reopened.get(job_path + '/preview?format=geojson', headers=HEADERS)
    assert preview.status_code == 200, preview.json
    assert preview.json['features'][0]['geometry']['type'] == 'Polygon'
    approved = reopened.post(job_path + '/accept', headers=HEADERS,
                             json={'preview_token': preview.json['preview_token']})
    assert approved.status_code == 200, approved.json
    assert approved.json['selected'] == {'rgb-test-field': queued['dataset_id']}
    final = make_client(tmp_path).get(RGB_JOBS, headers=HEADERS).json['jobs'][0]
    assert final['review']['decision'] == 'accepted'
