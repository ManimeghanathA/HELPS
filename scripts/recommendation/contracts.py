from dataclasses import dataclass, field, asdict
from datetime import datetime
import math
from typing import Any

def json_safe(value):
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value, datetime): return value.isoformat()
    if hasattr(value, 'to_dict'): return value.to_dict()
    if isinstance(value, dict): return {k: json_safe(v) for k,v in value.items() if k != 'metric_geometry'}
    if isinstance(value, (list,tuple)): return [json_safe(v) for v in value]
    return value

@dataclass(frozen=True)
class GateDecision:
    state: str
    reason_codes: tuple = ()
    evidence: dict = field(default_factory=dict)
    def __post_init__(self):
        if self.state not in ('pass','fail','unknown'): raise ValueError('Invalid gate state')
    def to_dict(self): return json_safe(asdict(self))

@dataclass(frozen=True)
class RecommendationRequest:
    dataset_id: str
    region_id: str
    latitude: float
    longitude: float
    model_id: str
    overrides: dict
    mission: str
    requested_at: datetime
    radius_km: float
    top_k: int
    policy: dict
    profile: dict
    weather: dict | None = None
    def to_dict(self): return json_safe(asdict(self))

@dataclass
class RecommendationResult:
    dataset_id: str
    region_id: str
    request: dict
    profile: dict
    mission: dict
    candidate_count: int
    gate_counts: dict
    eligible_spots: list = field(default_factory=list)
    uncertain: list = field(default_factory=list)
    excluded: list = field(default_factory=list)
    source_limits: list = field(default_factory=list)
    dataset: dict = field(default_factory=dict)
    schema_version: str = 'helps-recommendation-v1'
    eligible_count: int = 0
    uncertain_count: int = 0
    excluded_count: int = 0
    opportunity_counts: dict = field(default_factory=dict)
    research_candidates: list = field(default_factory=list)
    research_count: int = 0
    distinct_opportunity_counts: dict = field(default_factory=dict)
    verification_state: str = 'requires_verification'
    def to_dict(self): return json_safe(asdict(self))
