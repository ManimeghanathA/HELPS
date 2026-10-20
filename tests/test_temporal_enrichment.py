import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from scripts.knowledge.repository import write_package, KnowledgeRepository
from scripts.knowledge.sources import file_sha256
from tests.test_knowledge_repository import package_data


def fixture_package(tmp_path):
    source = tmp_path / 'original.gpkg'
    data = package_data()
    data['metadata']['build_spec'] = {'dataset_id': 'd', 'date': '2026-10-13', 'output_dir': 'old'}
    write_package(data, source)
    # Exercise the legacy retained package without temporal tables.
    with sqlite3.connect(source) as db:
        db.execute('DROP TABLE temporal_observations')
        db.execute('DROP TABLE temporal_aggregates')
    raster = tmp_path / 'history.tif'
    with rasterio.open(raster, 'w', driver='GTiff', width=12, height=12,
                       count=1, dtype='uint8', crs='EPSG:32643', nodata=255,
                       transform=from_origin(500000, 1500120, 10, 10)) as ds:
        states = np.ones((12, 12), dtype='uint8'); states[:, :6] = 0
        ds.write(states, 1)
    history = {'source_id': 'historic', 'path': str(raster), 'date': '2026-09-01',
               'status': 'available', 'sha256': file_sha256(raster),
               'provenance_state': 'manifest_date_verified', 'classification_policy': {'profile': 'conservative'}}
    return source, history


def test_enrichment_preserves_sql_geometry_features_and_source_bytes(tmp_path):
    from scripts.knowledge.enrichment import enrich_package
    source, history = fixture_package(tmp_path)
    digest = file_sha256(source)
    result = enrich_package(source, tmp_path / 'enriched', 'd-enriched', [history], log=lambda _: None)
    assert file_sha256(source) == digest
    assert result['date'] == '2026-10-13'
    assert result['enrichment_of'] == 'd'
    assert result['source_package_sha256'] == digest
    assert result['validation']['valid']
    target = Path(result['package_path'])
    with sqlite3.connect(source) as original, sqlite3.connect(target) as enriched:
        assert enriched.execute('PRAGMA foreign_key_check').fetchall() == []
        for table in ('terrain', 'zones', 'terrain_characteristics', 'zone_environment', 'lineage'):
            before = original.execute(f'SELECT * FROM {table}').fetchall()
            after = enriched.execute(f'SELECT * FROM {table}').fetchall()
            columns = [r[1] for r in original.execute(f'PRAGMA table_info({table})')]
            for left, right in zip(before, after, strict=True):
                for column, a, b in zip(columns, left, right, strict=True):
                    if column == 'dataset_id': assert b == 'd-enriched'
                    elif column == 'record_json':
                        expected = json.loads(a)
                        if expected.get('dataset_id') == 'd': expected['dataset_id'] = 'd-enriched'
                        assert json.loads(b) == expected
                    else: assert a == b
        assert enriched.execute('SELECT count(*) FROM temporal_observations').fetchone()[0] == 2
        assert enriched.execute('SELECT sha256 FROM sources WHERE source_id="historic"').fetchone()[0] == history['sha256']
    repo = KnowledgeRepository(target)
    row = repo.get_zone('z')
    assert row['temporal_open_confidence'] == pytest.approx(.5)
    assert row['temporal_support'] == 1
    assert repo.metadata['build_spec']['dataset_id'] == 'd-enriched'
    assert repo.temporal_observations('zones', 'z')[0]['provenance_state'] == 'manifest_date_verified'
    assert not (tmp_path / 'registry.json').exists()


@pytest.mark.parametrize('mutation,match', [
    ({'date': '2026-10-13'}, 'precede'),
    ({'date': 'bad'}, 'date'),
    ({'sha256': 'changed'}, 'hash'),
    ({'status': 'failed'}, 'available'),
])
def test_invalid_history_never_publishes(tmp_path, mutation, match):
    from scripts.knowledge.enrichment import enrich_package
    source, history = fixture_package(tmp_path)
    with pytest.raises(ValueError, match=match):
        enrich_package(source, tmp_path / 'enriched', 'new', [{**history, **mutation}])
    assert not (tmp_path / 'enriched' / 'knowledge.gpkg').exists()


def test_existing_output_and_reused_identity_are_rejected(tmp_path):
    from scripts.knowledge.enrichment import enrich_package
    source, history = fixture_package(tmp_path)
    output = tmp_path / 'enriched'; output.mkdir(); sentinel = output / 'manifest.json'; sentinel.write_text('retained')
    with pytest.raises(FileExistsError): enrich_package(source, output, 'new', [history])
    assert sentinel.read_text() == 'retained'
    with pytest.raises(ValueError, match='identity'): enrich_package(source, tmp_path / 'other', 'd', [history])


def test_duplicate_history_day_rejected(tmp_path):
    from scripts.knowledge.enrichment import enrich_package
    source, history = fixture_package(tmp_path)
    with pytest.raises(ValueError, match='duplicate'):
        enrich_package(source, tmp_path / 'out', 'new', [history, {**history, 'source_id': 'other'}])


@pytest.mark.parametrize('changed', ['source', 'history'])
def test_mid_build_source_changes_prevent_publication(tmp_path, changed):
    from scripts.knowledge.enrichment import enrich_package
    source, history = fixture_package(tmp_path)
    modified = False
    def change_after_measurement(message):
        nonlocal modified
        if modified or not message.startswith('Enrichment history:'): return
        modified = True
        if changed == 'source':
            with sqlite3.connect(source) as db:
                db.execute("INSERT INTO package_metadata VALUES ('external_change','changed')")
        else:
            with rasterio.open(history['path'], 'r+') as ds:
                ds.write(np.zeros((12, 12), dtype='uint8'), 1)
    with pytest.raises(ValueError, match='hash changed'):
        enrich_package(source, tmp_path / 'out', 'new', [history], log=change_after_measurement)
    assert not (tmp_path / 'out' / 'knowledge.gpkg').exists()
    assert not list((tmp_path / 'out').glob('*.staging'))
