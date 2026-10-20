"""Temporal evidence changes relative priority, never hard eligibility."""
import pytest
from shapely.geometry import box

from helicopter_profiles import MISSION_CONTEXTS
from scripts.recommendation.contracts import GateDecision
from scripts.recommendation.ranking import rank_eligible, rank_research


def candidate(confidence=None, support=None, state='pass'):
    return dict(state=state, zone=dict(zone_id='z', terrain_id='t', latitude=13.5,
        longitude=75.5, area_m2=1600, max_clear_diameter_m=40, max_slope_deg=2,
        metric_geometry=box(-20, -20, 20, 20)), gates={}, terrain=dict(
        temporal_open_confidence=confidence, temporal_support=support,
        history_date_count=12, valid_history_count=8,
        history_dates=['2026-05-01', '2026-06-01'], temporal_source_ids=['history-source']))


def score(value, mission=None):
    return rank_eligible([value], mission or {'weights': {'distance': .9, 'temporal': .1}},
                         (13.5, 75.5), 5)[0]


def test_temporal_support_reduces_effective_weight_and_reports_reproducible_contribution():
    sparse = score(candidate(.5, .1))
    full = score(candidate(.5, 1))
    assert sparse['score_factors']['temporal'] == .5
    assert sparse['effective_weights']['temporal'] == pytest.approx(.01)
    assert sparse['normalized_weights']['temporal'] == pytest.approx(.01 / .91)
    assert sparse['score_contributions']['temporal'] == pytest.approx(.005 / .91)
    assert full['score_contributions']['temporal'] == pytest.approx(.05)
    assert sparse['supported_factor_weight_coverage'] == pytest.approx(.91)
    assert sparse['score_complete'] is False
    assert full['score_complete'] is True
    evidence = sparse['factor_evidence']['temporal']
    assert evidence['support'] == .1
    assert evidence['configured_weight'] == .1
    assert evidence['effective_weight'] == pytest.approx(.01)
    assert evidence['normalized_weight'] == sparse['normalized_weights']['temporal']
    assert evidence['contribution'] == sparse['score_contributions']['temporal']
    assert evidence['history_date_count'] == 12
    assert evidence['valid_history_count'] == 8
    assert evidence['history_dates'] == ['2026-05-01', '2026-06-01']
    assert evidence['source_ids'] == ['history-source']
    assert sum(sparse['score_contributions'].values()) * 100 == pytest.approx(sparse['score'])
    assert sum(sparse['normalized_weights'].values()) == pytest.approx(1)


@pytest.mark.parametrize('confidence', [0, 1])
def test_observed_temporal_extremes_affect_soft_score_only(confidence):
    result = score(candidate(confidence, 1))
    assert result['state'] == 'pass'
    assert result['score'] == pytest.approx(90 + confidence * 10)


@pytest.mark.parametrize('support', [None, 0, -.1, 1.1, float('nan'), float('inf'), True, 'invalid'])
def test_missing_or_invalid_support_is_unknown_without_fabricated_priority(support):
    result = score(candidate(1, support))
    assert result['score'] == 100
    assert result['state'] == 'pass'
    assert 'temporal' not in result['score_factors']
    assert 'temporal' in result['missing_optional_factors']
    assert result['available_factors']['temporal'] is None
    assert result['factor_evidence']['temporal']['supported'] is False
    assert result['factor_evidence']['temporal']['effective_weight'] == 0
    assert result['factor_evidence']['temporal']['contribution'] == 0


@pytest.mark.parametrize('confidence', [None, -.1, 1.1, float('nan'), float('inf'), True, 'invalid'])
def test_invalid_confidence_is_unknown(confidence):
    result = score(candidate(confidence, 1))
    assert 'temporal' not in result['score_factors']
    assert result['factor_evidence']['temporal']['supported'] is False


def test_child_temporal_evidence_takes_precedence_over_parent_evidence():
    value = candidate(1, 1)
    value['zone'].update(temporal_open_confidence=0, temporal_support=.5, history_date_count=3)
    result = score(value)
    assert result['score_factors']['temporal'] == 0
    assert result['factor_evidence']['temporal']['scope'] == 'zone'
    assert result['factor_evidence']['temporal']['history_date_count'] == 3
    assert score(candidate(1, 1))['factor_evidence']['temporal']['scope'] == 'parent_terrain'


@pytest.mark.parametrize('ranker', [rank_eligible, rank_research])
def test_temporal_evidence_cannot_override_hard_failure(ranker):
    failed = candidate(1, 1, state='fail')
    gate_failed = candidate(1, 1)
    gate_failed['gates']['slope'] = GateDecision('fail', ('slope_limit',))
    assert ranker([failed, gate_failed], {'weights': {'temporal': 1}}, (13.5, 75.5), 5) == []


@pytest.mark.parametrize('mission', list(MISSION_CONTEXTS.values()), ids=list(MISSION_CONTEXTS))
def test_every_mission_uses_modest_temporal_policy_and_missing_history_preserves_ranking(mission):
    observed_closed = score(candidate(0, 1), mission)
    observed_open = score(candidate(1, 1), mission)
    unknown = score(candidate(), mission)
    assert observed_closed['score'] < observed_open['score']
    assert observed_open['factor_evidence']['temporal']['configured_weight'] == pytest.approx(.1)
    assert sum(mission['weights'].values()) == pytest.approx(1)
    assert unknown['score_factors'] == {k: v for k, v in observed_open['score_factors'].items() if k != 'temporal'}
    assert unknown['score'] == pytest.approx(sum(unknown['score_contributions'].values()) * 100)
    assert all(v >= 0 for v in unknown['normalized_weights'].values())


def test_unknown_history_preserves_original_emergency_score():
    # Original supported weights: distance .45, clearance .30, area .10.
    # Factors are 1, 40/70, and 1600/2600 respectively.
    result = score(candidate(), MISSION_CONTEXTS['immediate_emergency'])
    assert result['score'] == pytest.approx(80.34906270100489)
