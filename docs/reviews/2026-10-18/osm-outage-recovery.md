# OSM outage recovery attempt

Live diagnostics confirmed the main Overpass server returned HTTP 502 with a message that all workers and its queue were full. GET timed out. A tiny Private.coffee query returned 200. A documented third global provider, VK Maps, also returned 200 on the tiny query and was added to the provider pool. Global coverage was checked against the OpenStreetMap public-instance documentation; region-only mirrors were not used.

The real Bhadra acquisition was then attempted, retaining raw checkpoints and using all three providers. Some smaller responses were saved, but the complete building layer still could not be acquired. It failed after 158.19 seconds and did not publish a raw completion manifest or processed OSM package. See `osm-recovery-proof.json`, `overpass-connectivity.json`, `overpass-alternative.json` and `data/archive/runtime/osm-recovery-20261018.log`.

The fallback addition is not a claim that full-region OSM acquisition is now working. The active and pending knowledge hashes remain unchanged. The already acquired Sentinel observation is reusable.

361 Python regression tests passed in 53.35 seconds. Provider/subdivision tests use controlled endpoints; live evidence above records their limits. A durable alternative is a validated static regional OSM extract with local filtering and a cache. Geofabrik lists Southern Zone at about 532 MB, but the local static-file HEAD probe also timed out. No PBF was downloaded and no PBF-processing fallback was implemented in this attempt. Such an adapter needs coverage, snapshot, geometry and cache validation before it can substitute for the current query workflow.

Sources: https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances and https://download.geofabrik.de/asia/india.html.
