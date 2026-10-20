# Restore calibrated fresh scans

User requested the original calibrated thresholds and a new October 12 scan. The retained June map remains selected; no acceptance is automatic and no target candidate count is imposed.

The main knowledge build now selects the calibrated profile: SCL 5 / NDVI <=0.50 or SCL 4 / NDVI <=0.20, MNDWI <0 and explicit water rejection. The three-cell cloud margin, mapped building/water/industrial/facility exclusions, reviewed negatives, geometric area/dimension/clearance gates and final overlap audits remain in use. The calibrated profile uses its existing exact building-footprint subtraction and no additional AOI-edge strip; those conservative-only margins remain available in the separate conservative profile.

Historical WorldCover is retained as a source for per-polygon features rather than a hard mask for calibrated scans. This restores the broader working-map policy recorded in `2026-10-13/working-map-decision.md`. Conservative scans still apply the historical land-cover veto. Synthetic end-to-end tests exercise both policies, including water rejection and preservation of calibrated ground when an old reference labels it tree cover.

The initial threshold-only comparison (`bhadra-20261012-53b64c70`, job `649a0ca977714e8ab99ab318c95db64b`) completed with 313 polygons but retained the later land-cover veto. It is preserved as a comparison. The final restored-policy run is `bhadra-20261012-e0f12791`, job `924ea020c8e44264a0f5a3ab5021c2c3`; see the completed proof for its final results. The nine-polygon conservative result is also preserved separately.

All runs reuse local data. Temporal observations are harmonized under the selected classifier. No recommendation weighting, aircraft feature or hard/soft scoring rule changed. The review list now shows candidate counts and orders newest pending runs first.

Validation: `data/validation/calibrated-original-python.log`: 379 passed. `data/validation/calibrated-original-node.log`: 85 passed. Independent read-only review found no important regression in the scoped policy restoration.
