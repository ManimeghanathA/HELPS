# Rejection accounting and surviving-obstacle report

The user reports promising terrain rejected by the 191-candidate experiment and visible buildings still inside some remaining polygons. Both remain unresolved physical-accuracy issues. No thresholds were changed in response to this report.

The preserved Neha baseline has 2,484 polygons containing 375,530 sampled Sentinel pixel centres. Within those polygons:

- Conservative spectral screening retains 39,662 centres (10.56%). This stage combines the class-5-only gate, NDVI ≤ 0.20, water rejection and UNKNOWN/cloud handling. Counts do not isolate NDVI alone.
- Land-cover screening retains 21,179 centres (5.64% of the original sampled centres).
- 1,693 baseline polygons have zero accepted centres after spectral screening.
- Another 279 have zero accepted centres after supplementary land-cover screening.
- 108 baseline polygons overlap at least one final experimental polygon by more than numerical tolerance. New polygons may split baseline regions or occupy source-mask areas outside the baseline polygons, so 108 is not the new candidate count.

This measures rejection, not false negatives or precision. The user's promising areas still need independent evidence before being labelled usable. A fixed low NDVI ceiling and class-5-only rule can reject short vegetation, and 2021 land-cover evidence can reject terrain whose cover subsequently changed. Fixed uncertainty margins and geometry/clearance gates can remove additional regions. A lower candidate count does not establish better physical accuracy.

The completed experiment audited against the supplied building footprints buffered by 10 m, with total residual intersection 1.37e-10 m². This demonstrates no meaningful overlap with those particular geometries. It cannot establish that all visible buildings were mapped, that the imagery dates agree, or that independent imagery is registered. A remaining building-overlap report requires tracing the exact experimental ID; an asynchronous request for one `BhadraExp_ZONE_...` ID has been issued. The baseline map at port 8766 and experiment at port 8770 must also be distinguished.

Recommended next action: separate obstacle evidence from surface suitability. Investigate a surviving building case before altering building margins. Compare vegetation decisions against a small separate sample of promising rejected areas, and recover candidates only where supporting evidence distinguishes short vegetation from canopy/plantations. Preserve rejected geometry and reasons so potential terrain is not lost from analysis. Do not increase rejection globally or relax the NDVI ceiling globally without checking the known plantation failures and separate sites.

Reproducible diagnostic: `diagnose_candidate_rejection.py`. Detailed per-polygon measurements: `candidate-rejection-diagnosis.json`. The diagnostic leaves product code, thresholds, baseline and experimental outputs unchanged.
