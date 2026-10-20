"""Observation chronology shared by submission, publication and activation."""
from datetime import date, timedelta


def observation_date(value):
    try:
        parsed=date.fromisoformat(value)
        if parsed.isoformat()!=value:raise ValueError()
        return parsed
    except (ValueError,TypeError):raise ValueError('Observation date must use YYYY-MM-DD') from None


def validate_new_date(value,current_date=None,today=None):
    parsed=observation_date(value)
    upper=observation_date(today) if today else date.today()
    if parsed>upper:raise ValueError(f'Observation date cannot be later than today ({upper.isoformat()})')
    if current_date and parsed<=observation_date(current_date):
        raise ValueError(f'New observation date must be later than current {current_date}; earliest allowed {(observation_date(current_date)+timedelta(days=1)).isoformat()}')
    return parsed.isoformat()


def current_entry(registry,region_id):
    identity=registry.get('selected',{}).get(region_id)
    return identity,registry.get('datasets',{}).get(identity,{})


def validate_registry_date(registry,region_id,value):
    return validate_new_date(value,current_entry(registry,region_id)[1].get('date'))


def validate_imagery_dates(spec):
    """A declared day and independently retained provider/tag dates must agree."""
    from .sources import inspect_source
    for key in ('spectral','scl'):
        asset=spec.sources.get(key)
        if asset is None:continue
        if asset.date!=spec.date:raise ValueError(f'{key} observation date {asset.date or "unknown"} does not match selected {spec.date}; old imagery cannot be relabelled')
        record=inspect_source(asset)
        dates=[]
        for name in ('date','observation_date','acquisition_date','DATE_ACQUIRED'):
            if record.get('tags',{}).get(name):dates.append(record['tags'][name][:10])
            if asset.metadata.get(name):dates.append(str(asset.metadata[name])[:10])
        manifest=asset.metadata.get('acquisition_manifest',{})
        if manifest.get('date'):dates.append(manifest['date'])
        if any(day!=spec.date for day in dates):raise ValueError(f'{key} actual source date differs from selected observation date')
        for history in spec.parameters.get('_history_sources',[]):
            if history.get(key+'_sha256')==record['sha256'] and history['date']!=spec.date:raise ValueError(f'{key} bytes belong to historical {history["date"]}; old imagery cannot be relabelled')
