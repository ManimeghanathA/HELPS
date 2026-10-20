# Vision subtraction and new-site addition implementation plan

**Goal:** Execute the user's approved two-stage geometry workflow, with the explicitly selected 12° maximum slope for new sites, and produce fully characterized unpublished knowledge.

**Architecture:** A bounded offline refinement producer reads the pinned vision GeoPackage through its spatial indexes. It subtracts all `other_regions` from the selected June parents, then contracts individual open-region segmentations by 5 m and qualifies additional sites. The existing knowledge builder recalculates all features and temporal evidence. A source-pinned same-observation refinement gets explicit map review rather than automatic activation.

**Requirements:** User's two numbered instructions and follow-up “12 deg”. Existing geometry gates remain 900 m², 30 m rectangle dimensions, 15 m neck opening and 30 m inscribed clear diameter. Reject missing DEM support or any intersecting cell above 12° for additions. Preserve mapped exclusions, reviewed rejects, parent/source lineage, aircraft-specific limits, all score inputs and the current baseline. Vision acquisition date remains unknown; June Sentinel context is not relabelled.

## Tasks

- [x] Add regression tests for narrow fragments, obstacle holes, 5 m inward offset, exact 12°/above-limit/nodata/partial support and overlapping additions.
- [x] Implement indexed vision reading and strict geometry qualification in `scripts/knowledge/vision_refinement.py`; keep streaming memory bounded and deterministic geometry/source IDs.
- [x] Implement the offline orchestration in a separate small runner: pinned selected source, existing static input snapshots and native DEM slope; revision seed/exclusion proof; full existing knowledge build; durable pending job and source-provenance metadata.
- [x] Support only verified same-date CV revisions in map acceptance, with unchanged expected-current/source hashes, metadata validation and full recomputed features; ordinary scan chronology remains unchanged. Label revision provenance clearly in review.
- [x] Run targeted tests, execute the real Bhadra build, validate geometry/exclusion/slope/dedup invariants, and request a focused review.
- [x] Run applicable regression suites and verify the real pending preview while preserving the active June package byte-for-byte. Report counts and remaining limitations. Model brainstorming follows delivery.


