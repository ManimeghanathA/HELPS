from types import SimpleNamespace
from time import monotonic,sleep
from scripts.ui.jobs import JobManager

def wait(manager,job_id):
    deadline=monotonic()+3
    while monotonic()<deadline:
        result=manager.get(job_id)
        if result['status'] in ('completed','failed'):return result
        sleep(.01)
    raise AssertionError('job did not finish')

def test_job_runs_actual_builder_and_retains_failure():
    manager=JobManager();spec=SimpleNamespace(dataset_id='test')
    def fail(spec,log):
        log('Checking DEM units')
        raise ValueError('DEM missing')
    job=manager.submit(spec,fail);result=wait(manager,job['job_id'])
    assert result['status']=='failed' and result['error']=='DEM missing'
    assert any('DEM units' in x['stage'] for x in result['history'])

def test_result_serializes_with_validation_without_activation():
    manager=JobManager();spec=SimpleNamespace(dataset_id='test')
    job=manager.submit(spec,lambda spec:{'validation':{'valid':True},'counts':{'terrain':3}})
    result=wait(manager,job['job_id'])
    assert result['status']=='completed' and result['result']['counts']['terrain']==3
    assert 'activated' not in result

def test_new_strategy_remains_unpublished_and_does_not_activate():
    manager=JobManager();spec=SimpleNamespace(dataset_id='new',source_mode='new')
    seen=[]
    def builder(spec):
        seen.append(spec.source_mode)
        return {'validation':{'valid':True},'counts':{'terrain':2}}
    result=wait(manager,manager.submit(spec,builder)['job_id'])
    assert seen==['new'] and result['status']=='completed'
    assert 'selected' not in result and 'published' not in result


def test_inflight_builds_are_inspectable_without_becoming_packages():
    from threading import Event
    from types import SimpleNamespace
    done=Event();manager=JobManager()
    def build(spec):
        done.wait(2);return {'package_path':'pending.gpkg'}
    job=manager.submit(SimpleNamespace(dataset_id='new',region_id='r'),build)
    try:
        assert manager.list('r')==[]
        assert manager.list('r',include_unfinished=True)[0]['job_id']==job['job_id']
    finally:done.set()
