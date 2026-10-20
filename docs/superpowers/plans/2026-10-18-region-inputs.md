# Region Input Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Implement the user-approved processed → raw → download workflow and understandable source storage UI.

**Architecture:** A manifest-backed source store resolves independently versioned sources per region/AOI. Existing download adapters supply raw bundles; preparation validates and publishes processed snapshots atomically. The current knowledge/recommendation contracts remain intact.

**Tech Stack:** Python, Flask, Rasterio, GeoPandas, Leaflet, vanilla JavaScript.

**Spec:** ../specs/2026-10-18-region-inputs-design.md

## Global Constraints
- Preserve active and pending knowledge bytes and registry selection.
- Sentinel date must match; context/elevation date never becomes imagery date.
- No silent empty obstacles, nodata elevation or stale source substitution on refresh.
- No deletion or movement of existing scientific evidence.
- Preserve hard/soft recommendation rules and all measured features.

## Review Focus
- Processed evidence whose raw parents were changed is not reusable.
- Different AOI geometry under the same region cannot reuse uncovered data.
- A failed refresh leaves existing snapshots intact but fails the requested job.
- Filesystem access is limited to registered evidence; no arbitrary file download.
- Old interrupted snapshots and concurrent builders cannot become complete inputs.

## Tasks and ledger
- [x] Write failing source-store tests; implement `scripts/pipeline/source_store.py` with immutable manifests, validation, inspection and independent source resolution. Tests: `tests/test_source_store.py`.
- [x] Add adapter integration in `scripts/pipeline/region_inputs.py`; raw preservation/native DEM windows, Bhadra adoption and source lineage. Test processed reuse/raw processing/provider failures/refresh/region isolation.
- [x] Connect automatic UI builds and single-date CLI to resolver; add engineer readiness/registered-file API. Test chronology/manual overrides/guarded access/pending publication.
- [x] Add frontend readiness/refresh/storage UI; test escaped locations, stale request gates and accessible file links.
- [x] Register existing Bhadra data without moving sources, verify active/pending hashes, check offline replay eligibility, run full regressions and review.
- [x] Restart server with verified listener.

Execution rulings: user explicitly requested completion of the approved proposal/task list; proceed continuously. No new checkout because approved application is largely uncommitted in this branch. No automatic production selection. Record verification results below as work proceeds.

## Verification ledger

- Initial source-store failures observed before implementation; processed/raw recovery, changed AOI/date, corrupt sources, failed refresh and interrupted processing passed after implementation.
- Whole-change read-only reviewer identified land-cover grid reuse, malformed manifest handling, corrupt vector exception recovery, pre-migration readiness and explicit override/refresh ambiguity. Regression tests reproduced the code defects before fixes. Land cover now re-aligns raw crops; incomplete manifests are skipped; reader errors normalize to validation errors; actual offline adoption was completed; explicit obstacle overrides cannot be combined with refresh and unused Overture downloads are skipped.
- Ruling: old single-date CLI outputs must not overwrite canonical polygons or become auto-selected legacy runs. New CLI runs are explicitly pending; legacy compatibility helper remains callable separately. Existing historical runs and files are unchanged.
- Ruling: adoption is one-time per Bhadra boundary; corrupt/changed legacy evidence cannot be silently blessed again at each new scan. Original raw dated bundles are registered in place as raw evidence too. Explicit selected DEM identity remains honoured.
- User steering: exact product name added as a subheading at the top and bottom of the main frontend.
- Final full suite: **355 Python tests passed** (54.08s), **80 JavaScript tests passed**. Logs under `data/validation/region-lifecycle-*-final.log`.
- Actual Bhadra API proof: Sentinel, DEM and Overture reuse processed evidence; OSM lacks required layers and land cover has no registered prepared source. Registered-file streaming works. Active and pending package hashes/selection unchanged; pending decision preserved. Proof: `docs/reviews/2026-10-18/region-input-final-proof.json`.
- Offline fresh June 1 replay was not performed: existing OSM caches lack industrial/facilities layers and some other required layers. See `offline-replay-input-check.json`. This is not a claim that fresh detection reproduces retained polygons.
- Browser security previously denied local-page observation; no visual screenshot or browser verification is claimed and no bypass attempted. Automated frontend and backend evidence are recorded separately.
- Server restarted with final code; listener verified at `127.0.0.1:5000`, server PID 19648. Runtime logs: `data/archive/runtime/region-inputs-20261018.stderr.log` and matching stdout log.
