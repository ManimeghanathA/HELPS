"""Add historical evidence to a separate copy of retained immutable geometry.

This operation does not run candidate classification or activate a dataset.
Historical classification policy/provenance is supplied by the caller and is
retained verbatim in normalized source records.
"""
from contextlib import closing
from pathlib import Path
import datetime
import json
import os
import sqlite3
import uuid

import geopandas as gpd

from .chronology import observation_date
from .repository import _atomic_json, decode_geometry, dumps, validate_package
from .sources import file_sha256
from .temporal import compute_temporal, validate_history_raster


def _identity(value, old, new):
    if isinstance(value, dict):
        return {key: new if key == 'dataset_id' and item == old else _identity(item, old, new)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_identity(item, old, new) for item in value]
    return value


def _check_history(history, current_date):
    dates = set(); identities = set()
    for source in history:
        day = observation_date(source.get('date'))
        if day >= observation_date(current_date):
            raise ValueError('historical date must strictly precede retained observation date')
        if source.get('status') != 'available':
            raise ValueError('enrichment requires available historical sources; failed evidence cannot be omitted')
        if source['date'] in dates or source['source_id'] in identities:
            raise ValueError('duplicate historical date or source identity')
        dates.add(source['date']); identities.add(source['source_id'])
        inspected = validate_history_raster(source['path'], source.get('encoding'))
        if inspected['sha256'] != source.get('sha256'):
            raise ValueError('historical classification hash changed')
        if not source.get('provenance_state'):
            raise ValueError('historical provenance state must be explicit')


def enrich_package(source_package, output_dir, dataset_id, history_sources, log=print):
    """Return an unselected immutable same-date package with exact retained rows.

    Only dataset identity fields and package/run metadata change. Measurement
    tables, geometry blobs, entity identifiers and spatial indexes are copied by
    SQLite backup. Outputs are never reused or overwritten.
    """
    source_package = Path(source_package).resolve()
    output_dir = Path(output_dir).resolve()
    package = output_dir / 'knowledge.gpkg'
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f'enrichment output already contains artifacts: {output_dir}')
    source_hash = file_sha256(source_package)
    report = validate_package(source_package)
    if not report['valid']:
        raise ValueError('enrichment source package invalid: ' + '; '.join(report['errors']))
    metadata = report['metadata']; old = metadata['dataset_id']
    if not isinstance(dataset_id, str) or not dataset_id.strip() or dataset_id == old:
        raise ValueError('enrichment requires a separate dataset identity')
    current_date = metadata['date']; observation_date(current_date)
    history = [dict(row) for row in history_sources]
    if not history:
        raise ValueError('enrichment requires available historical sources')
    _check_history(history, current_date)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation prevents two jobs from writing the same output.
    reservation = output_dir / '.enrichment.lock'
    with reservation.open('x', encoding='utf-8') as lock:
        lock.write(dataset_id)
    staged = output_dir / ('knowledge.' + uuid.uuid4().hex + '.staging')
    try:
        with closing(sqlite3.connect(source_package.as_uri() + '?mode=ro', uri=True)) as original:
            frames = {}
            for table, key in (('terrain', 'terrain_id'), ('zones', 'zone_id')):
                rows = original.execute(f'SELECT {key},geom FROM {table} ORDER BY fid').fetchall()
                frames[table] = gpd.GeoDataFrame({key: [row[0] for row in rows]},
                    geometry=[decode_geometry(row[1]) for row in rows], crs=metadata['crs'])
            with closing(sqlite3.connect(staged)) as target:
                original.backup(target)
        log(f'Enrichment: preserved {len(frames["terrain"])} terrain and {len(frames["zones"])} zones; measuring {len(history)} older dates')
        observations = []; aggregates = []
        # Bound progress intervals to groups of entities without changing overlap semantics.
        for table, frame in frames.items():
            empty_terrain = frames['terrain'].iloc[:0]
            empty_zones = frames['zones'].iloc[:0]
            for start in range(0, len(frame), 100):
                chunk = frame.iloc[start:start + 100]
                measured, combined = compute_temporal(chunk if table == 'terrain' else empty_terrain,
                    chunk if table == 'zones' else empty_zones, history, current_date, dataset_id)
                observations.extend(measured); aggregates.extend(combined)
                log(f'Enrichment history: {table} {min(start + 100, len(frame))}/{len(frame)}')
        with closing(sqlite3.connect(staged)) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE'); db.execute('PRAGMA defer_foreign_keys=ON')
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for table in tables:
                quoted = '"' + table.replace('"', '""') + '"'
                columns = {row[1] for row in db.execute(f'PRAGMA table_info({quoted})')}
                if 'dataset_id' in columns:
                    db.execute(f'UPDATE {quoted} SET dataset_id=? WHERE dataset_id=?', (dataset_id, old))
                if 'record_json' in columns:
                    for rowid, text in db.execute(f'SELECT rowid,record_json FROM {quoted}').fetchall():
                        before = json.loads(text); after = _identity(before, old, dataset_id)
                        if after != before:
                            db.execute(f'UPDATE {quoted} SET record_json=? WHERE rowid=?', (dumps(after), rowid))
            db.execute('UPDATE analysis_runs SET run_id=? WHERE run_id=?', (dataset_id, old))
            db.execute('CREATE TABLE IF NOT EXISTS temporal_observations(dataset_id TEXT NOT NULL REFERENCES dataset_versions(dataset_id),entity_type TEXT NOT NULL CHECK(entity_type IN (\'terrain\',\'zones\')),entity_id TEXT NOT NULL,date TEXT NOT NULL,source_id TEXT NOT NULL REFERENCES sources(source_id),record_json TEXT NOT NULL,PRIMARY KEY(dataset_id,entity_type,entity_id,date))')
            db.execute('CREATE TABLE IF NOT EXISTS temporal_aggregates(dataset_id TEXT NOT NULL REFERENCES dataset_versions(dataset_id),entity_type TEXT NOT NULL CHECK(entity_type IN (\'terrain\',\'zones\')),entity_id TEXT NOT NULL,record_json TEXT NOT NULL,PRIMARY KEY(dataset_id,entity_type,entity_id))')
            db.execute('DELETE FROM temporal_observations'); db.execute('DELETE FROM temporal_aggregates')
            for source in history:
                existing = db.execute('SELECT sha256,record_json FROM sources WHERE source_id=?', (source['source_id'],)).fetchone()
                record = {**source, 'kind': 'historical_classification'}
                if existing and (existing[0] != source['sha256'] or json.loads(existing[1]).get('date') != source['date']):
                    raise ValueError('historical source identity conflicts with retained source')
                if not existing:
                    db.execute('INSERT INTO sources VALUES (?,?,?,?)', (source['source_id'], dataset_id, source['sha256'], dumps(record)))
            db.executemany('INSERT INTO temporal_observations VALUES (?,?,?,?,?,?)',
                [(dataset_id, row['entity_type'], row['entity_id'], row['date'], row['source_id'], dumps(row)) for row in observations])
            db.executemany('INSERT INTO temporal_aggregates VALUES (?,?,?,?)',
                [(dataset_id, row['entity_type'], row['entity_id'], dumps(row)) for row in aggregates])
            enriched = _identity(metadata, old, dataset_id)
            enriched.update(enrichment_of=old, source_package_sha256=source_hash,
                operation='geometry_preserving_temporal_enrichment', source_package_path=str(source_package),
                temporal_summary={'history_dates': sorted(row['date'] for row in history),
                    'observation_count': len(observations),
                    'entities_with_valid_history': sum(row['valid_history_count'] > 0 for row in aggregates),
                    'mean_valid_support': sum(row['temporal_support'] for row in aggregates) / len(aggregates) if aggregates else 0,
                    'source_limitations': [{'date': row['date'], 'provenance_state': row['provenance_state'],
                        'classification_policy': row.get('classification_policy')} for row in history]})
            if 'build_spec' in enriched:
                enriched['build_spec']['output_dir'] = str(output_dir)
            db.execute("UPDATE package_metadata SET value=? WHERE key='metadata'", (dumps(enriched),))
            db.execute('UPDATE dataset_versions SET record_json=? WHERE dataset_id=?', (dumps(enriched), dataset_id))
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('enrichment foreign key integrity failure')
            db.commit()
        _check_history(history, current_date)
        if file_sha256(source_package) != source_hash:
            raise ValueError('retained source package hash changed during enrichment')
        validation = validate_package(staged)
        if not validation['valid']:
            raise ValueError('enrichment package invalid: ' + '; '.join(validation['errors']))
        if package.exists():
            raise FileExistsError('immutable enrichment package exists')
        # Windows rename refuses an existing target; no replace semantics.
        os.rename(staged, package)
        result = {'dataset_id': dataset_id, 'package_path': str(package), 'validation': validation,
            'counts': report['counts'], 'enrichment_of': old, 'source_package_sha256': source_hash,
            'date': current_date, 'region_id': metadata['region_id']}
        _atomic_json(output_dir / 'manifest.json', {**result, 'status': 'complete',
            'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'activation': 'not selected; explicit map review required', 'source_records': history})
        log(f'Complete immutable geometry-preserving enrichment {dataset_id}')
        return result
    finally:
        staged.unlink(missing_ok=True)
        reservation.unlink(missing_ok=True)
