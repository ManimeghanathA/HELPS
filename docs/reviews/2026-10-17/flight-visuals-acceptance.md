# Flight frontend changes — 2026-10-17

Implemented all five requests from the new changes.txt. Changes are limited to the unified frontend and frontend tests; recommendation inputs/scoring, pipeline and stored polygons are unchanged.

- Shared helicopter position SVG replaces the default map pin. Its hub marks the query coordinate. On recommendation selection it turns toward the landing reference; map framing includes both the helicopter origin and the selected polygon. The orange reference/footprint remains separate. Entered approach heading for weather is not changed by the visual marker bearing.
- Region outlines use darker green #168047 on every shared map. Planned outlines retain faded opacity.
- Overview sun/full moon follows a decorative local-clock arc, with corresponding warm/white light and helicopter orientation. Automatic local-clock theme uses 06:00–18:00 for day and the remaining hours for night; it does not claim astronomical sunrise, moon phase or actual flight heading. A manual theme choice lasts until the next day/night period. Scene updates each minute, on resize, visibility change and return to Overview; no geolocation is requested.
- Dark-theme accent is lime. Both themes preserve measured slope colour semantics.
- Rotor loader has a stationary aircraft body and a solid four-blade rotor turning about its actual hub, with reduced-motion support.
- Map includes all four considered regions as a list: Bhadra enabled, Wayanad/Ladakh/Himalayas faded and disabled until knowledge is available.

Verification: all75 Node tests passed;8 focused Flask page/API tests passed. Tests cover time boundaries/midnight, cardinal/unknown bearings, disabled region states, icon creation/update, retained query coordinate and target marker, and existing application/map/scoring evidence contracts. Browser verified both theme scenes, all region states, real recommendation results, retained coordinate13.8194/75.6659 and marker rotation150.9466 degrees toward the selected candidate. Full backend suite was not repeated for this frontend-only change.

Moonlight screenshot: flight-scene-moon.jpg. Before/after frontend patch: flight-visuals.diff. Server restarted on http://127.0.0.1:5000.
