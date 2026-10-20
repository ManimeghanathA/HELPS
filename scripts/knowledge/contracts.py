"""Public producer/consumer contracts. Distances are metres, slopes degrees."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import math

EVIDENCE_STATES = ('measured', 'derived', 'unknown', 'invalid')
THRESHOLDS = (0, 2, 4, 6, 8, 10, 12, 15)

@dataclass
class SourceAsset:
    source_id: str
    path: Path
    kind: str = 'vector'
    layer: Optional[str] = None
    date: Optional[str] = None
    sha256: Optional[str] = None
    units: Optional[str] = None
    coverage_state: str = 'unknown'
    coverage_path: Optional[Path] = None
    crs: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.path = Path(self.path)
        if self.coverage_path is not None:
            self.coverage_path = Path(self.coverage_path)
        if self.coverage_state not in ('unknown', 'supplied', 'verified'):
            raise ValueError('coverage_state must be unknown, supplied or verified')

    @classmethod
    def from_dict(cls, value):
        if isinstance(value, cls): return value
        return cls(**value)

@dataclass
class KnowledgeBuildSpec:
    dataset_id: str
    region_id: str
    date: str
    aoi: SourceAsset
    retained_seed: SourceAsset
    dem: SourceAsset
    output_dir: Path
    reviewed_exclusions: Optional[SourceAsset] = None
    sources: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)
    source_mode: str = 'retained'

    def __post_init__(self):
        for name in ('aoi', 'retained_seed', 'dem', 'reviewed_exclusions'):
            asset = getattr(self, name)
            if asset is not None: setattr(self, name, SourceAsset.from_dict(asset))
        self.sources = {key: SourceAsset.from_dict(value) for key, value in self.sources.items()}
        self.output_dir = Path(self.output_dir)
        if not self.dataset_id or not self.region_id:
            raise ValueError('dataset_id and region_id required')
        if Path(self.dataset_id).name != self.dataset_id or self.dataset_id in ('.', '..'):
            raise ValueError('dataset_id must be a single safe directory name')

    @classmethod
    def from_dict(cls, value):
        return cls(**value)

    def to_dict(self):
        return json_safe(asdict(self))

@dataclass
class TerrainRasterAssets:
    elevation_path: Path
    slope_path: Path
    roughness_path: Path
    valid_path: Path
    crs: str
    resolution_m: float
    manifest: dict = field(default_factory=dict)
    manifest_path: Optional[Path] = None

@dataclass
class KnowledgeBuildResult:
    dataset_id: str
    package_path: Path
    manifest_path: Path
    counts: dict
    validation: dict
    source_completeness: dict

    def to_dict(self): return json_safe(asdict(self))

def json_safe(value):
    if isinstance(value, Path): return str(value)
    if isinstance(value, dict): return {str(k): json_safe(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [json_safe(v) for v in value]
    if hasattr(value, 'item'): return json_safe(value.item())
    if isinstance(value,float) and not math.isfinite(value): return None
    return value
