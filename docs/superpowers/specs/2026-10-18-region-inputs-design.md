# Region input lifecycle

Approved scope: the user approved the architecture proposal and nine-task delivery list, then explicitly instructed implementation without breaking existing work. This document records those decisions rather than introducing an additional approval round.

## Contract

All new automatic builds resolve source evidence through one region-aware service. Valid processed inputs win, otherwise process validated raw evidence, otherwise download missing evidence into raw and prepare processed outputs. Each source has an immutable manifest, AOI identity, content hashes, provenance, preparation version and acquisition time. Sentinel additionally requires exact observation date. OSM/Overture/DEM reuse is independent of imagery date. Explicit refresh fetches new OSM/Overture snapshots; it never overwrites old snapshots.

Storage: data/raw/<region>/{boundary,sentinel,dem,osm,overture}/<snapshot>/ and data/processed/<region>/<kind>/<snapshot>/. Sentinel includes observation date. Raw contains provider responses/tiles/native windows and original uploaded source files; adapters can also retain intermediate mosaics for recoverability, explicitly labelled. Processed contains validated analysis-ready rasters/vectors and manifest references to raw. WorldCover keeps its 2021 reference-year limitation. No file existence alone implies readiness.

Knowledge packages remain under data/knowledge. Build logs/checkpoints remain associated with immutable package/job identities. Registry publication and existing preview/confirm/reject semantics are unchanged. Hard/soft ranking and terrain features are unchanged. Existing baseline/source paths remain read-only; adoption creates manifests/copies only and preserves hashes. Failed/partial preparations do not publish manifests. Concurrent input resolution is serialized across processes. Raw files referenced by processed evidence remain integrity checked.

## UI

An input readiness panel shows reuse processed / process raw / download required, current snapshot dates, raw/processed destinations and reasons. Inspection is read-only and never downloads. Engineer-only registered-file downloads and copyable absolute locations provide access without accepting arbitrary client paths. Details remain collapsible. Refresh mapped obstacles is explicit and applies only to OSM/Overture. Region changes invalidate stale requests. Manual evidence remains available and its choice is honoured.

## Verification and limits

Regression tests cover raw recovery, processed reuse, changed AOI/date, corrupt manifests/content, missing OSM layers, provider failure, refresh failure preserving old versions, safe registered downloads and region isolation. Existing June 1 knowledge and enrichment hashes must remain unchanged. Run the full Python/JS suites. A separate offline June 1 replay compares fresh detection using existing available source evidence against retained polygons; if complete inputs cannot be resolved without downloading, report that limitation rather than fabricate equivalence. No new region or provider availability is claimed without a live build.

## Rulings

- Work in the current codex/unified-helps branch: almost the entire current application is uncommitted here, so a new checkout would omit the approved working version. No worktree, broad commit or destructive migration.
- Existing raw/processed layouts remain readable compatibility inputs. New outputs use region folders. Adoption is copy/reference based; no deletion or overwrite of baseline evidence.
- Source observations are independently dated. OSM/Overture are acquisition-time snapshots; historical date selection never relabels them.
