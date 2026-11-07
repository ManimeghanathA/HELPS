# Region inputs: raw → processed → knowledge

## Bhadra date-only workflow (18 October update)

The main Build knowledge screen now asks only for a newer observation date for Bhadra. It does not offer new-region creation or source/refresh choices in the ordinary scan form. The date must remain strictly newer than the active observation and no later than today. Monthly date search and historical evidence remain available.

Date-only builds download only missing Sentinel imagery/SCL for that date. They reuse the hash-validated local boundary, DEM, OSM, Overture, land cover, saved restrictions and rejected-site corrections. Raw static evidence may be processed locally if needed. Missing/corrupt static evidence stops the build rather than triggering another download or substituting an empty exclusion. The complete feature, terrain, temporal and recommendation pipelines remain in use. Candidate review/accept/reject is unchanged.

Fresh UI builds now default to the recovered Neha `neha-236c34c` profile, including the original connected-component geometry sequence, not only its classifier thresholds. Pinned June replay reproduces 2,484 candidates. Historical WorldCover contributes feature evidence but does not veto this profile; reviewed rejected sites remain excluded in ordinary builds. The stricter conservative profile remains separate. See [exact baseline recovery](reviews/2026-10-18/neha-baseline-recovery.md); neither experiments nor later scans are selected automatically.

One-time OSM recovery uses a full Geofabrik PBF snapshot: dated edition URL, published MD5, local SHA-256, region-plus-30m coverage check, and all nine layer groups. Original bytes remain in `data/raw/osm-extracts/<zone>/<digest>/`; regional raw/processed manifests pin them. Full geometries are reconstructed before regional filtering. Routine date-only scans reuse the resulting regional file and do not contact Overpass. Mapped snapshot time is independent of Sentinel observation time; neither source proves every real-world obstacle is mapped.

The Data Engineer selects a registered region and observation date, then uses **Check local inputs** in Build knowledge. This is read-only. It shows which sources can be reused, which need processing from raw, which need downloading and where files will be stored. Expand **Storage & source details** for full locations, **Copy location** and registered **Download file** actions. Builds revalidate evidence before using it.

## Storage and reuse

New automatic sources are saved under `data/raw/<region>/<source>/<snapshot>/`; Sentinel includes its observation-date directory. Original Sentinel response tiles, OSM JSON/XML, Overture exports and native DEM windows are retained where acquired. Adapters also retain explicitly labelled intermediate mosaics/vectors in raw bundles for recoverability.

Analysis-ready sources are published under `data/processed/<region>/<source>/<snapshot>/`. Completion manifests pin region geometry, date where relevant, preparation version, provenance and hashes. A processed source is reusable only while its files and recorded raw parents remain intact. Missing/corrupt processed output can be recreated from valid raw evidence. Partial attempts have no completion manifest and are never reused as complete inputs. Downloads for the same region are serialized independently from knowledge publication.

Sentinel is date-specific. Elevation and OSM/Overture snapshots are reused across imagery dates for the same boundary. The compatibility API still supports explicit obstacle refresh for maintenance; the ordinary date-only screen does not refresh or download these sources. A maintenance refresh preserves previous snapshots and fails if the provider cannot supply a valid replacement. DEM requires compatible units, CRS and region-plus-halo coverage. Copernicus fallback is a DSM, not surveyed ground. WorldCover remains the 2021 product and is aligned to the selected Sentinel grid where compatible local evidence exists.

New region uploads preserve the original boundary under `raw/<region>/boundary` and prepare a normalized boundary under `processed/<region>/boundary`. Current regional evidence uploads likewise preserve originals in raw and registered validated copies in processed; asset identity records remain under `knowledge/sources`. Manual uploads are not automatically advertised as complete multi-file Sentinel/OSM bundles. Legacy unscoped upload API calls remain compatible.

## Existing Bhadra

Known existing Bhadra files were registered **in place** rather than moved. Their full original locations appear in input details. Six Sentinel dates, the Overture footprint source and covering FABDEM are registered; original raw Sentinel bundles are also registered for fallback. This avoids duplicated bulk data and protects published provenance. Migration record: `docs/reviews/2026-10-18/region-input-adoption.json`.

The legacy OSM cache is incomplete under the required layer contract. The October 18 recovery downloads and converts a verified regional extract to establish a complete nine-layer local input. File existence alone is not treated as complete coverage. Source reuse does not establish completeness of real-world tree/building mapping.

## Knowledge and review

The knowledge builder consumes resolved sources and writes immutable `data/knowledge/<dataset-id>` packages, measured raster derivatives and stage checkpoints. Engineer jobs persist under `knowledge/jobs`. The active map and version-bound recommendations use `knowledge/registry.json`. A completed build remains pending until its polygon map is inspected and explicitly accepted or rejected. Previous packages and historical dates remain preserved. Hard compatibility features, soft scores and measured per-polygon features are unchanged by this storage refactor.

Both the main automatic UI build and the single-date polygon CLI use `scripts.pipeline.region_inputs`. The older acquisition API remains available for compatibility scripts; it retains its older date-cache layout. New single-date CLI results no longer auto-promote canonical processed polygons or auto-select themselves in the legacy engine. Use the main knowledge UI for reviewed publication. Old `runs`, `inputs` and archives remain retained reference/recovery material; they were not bulk moved or deleted.

## Validation

Latest delivery checks: 375 Python tests and 85 JavaScript tests. A real dated Geofabrik extract was downloaded and checksum-verified; all nine Bhadra layers were prepared locally. The recovered 28 OSM building IDs and footprints exactly match the earlier successful Overpass result. The date-only October 12 build completed with 9 candidates, 44 slope areas and 318 temporal observations over six historical dates; it remains pending review. Existing active and pending-enrichment package checksums are unchanged. No physical polygon-accuracy or operational landing-safety validation is claimed. Fresh June 1 detection remains a separate reproducibility exercise; the saved June 1 map is preserved exactly. Proofs are under `docs/reviews/2026-10-18/`.
