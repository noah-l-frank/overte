# Independent original stereo Graphics evidence

`stereo-graphics-evidence` v1 is an explicit common-journey image policy:
`{"source":"world-render-target","profile":"pico-stereo-graphics-v1"}`.
The existing v16 artifact envelope carries a whole original two-eye PNG and a
separate original native JSON artifact. Legacy mono policies/readers remain
unchanged. No adapter subprocess receives the external policy or reader token.

For each acquisition the names are
`graphics-<run>-<role>-<stage>-<capture-request>.png` and the same stem followed by
`.native.json`. Both artifacts retain the original capture epoch, ticket and
private file ownership. The metadata is bounded to 2 MiB, rejects duplicate JSON
keys/nonfinite numbers, and contains only original native packets: before/after
native settings/lifecycle, before/after subject v3, actual Pico Graphics UI,
world capture v4 and provider status, plus their run/process/role/stage binding.
The exact schema and original names are enforced by
[`stereo_graphics_evidence.py`](../feature_journeys/stereo_graphics_evidence.py).
There are no adapter-supplied pixel statistics or requested-state fields.

The common engine additionally requires the actual authored seven-entity scene,
its native tracked head at the authored view and an original successful HTTP
delivery completed before the first subject acquisition. A decodable marker
cannot substitute for the delivered scene or unchanged authored colors/haze.
The common engine independently validates original source order, a 1500 ms
source interval, current public state/lifecycle and oldest source epoch. The
existing journey applies its independent current clock/action barrier. Original
GPU uniforms project the fixture challenge and effect interiors separately for
both eyes. The PNG is never cropped, resized or re-encoded by this verifier.
One eye cannot borrow another eye's challenge. Decode/photometry takes at most
five monotonic seconds; original source epochs are never changed.

Every process/role/stage pins GPU, native, UI and provider births. Each new public
sample must advance capture, acquisition, actual execution/submission, camera,
native, subject and UI cursors. Source request nonces cannot be reused under a
new sample. The histories stop at 4096 frames/contexts and 28672 source queries;
they never evict a floor. Cache keys bind the complete public sample and original
metadata digest, so altered state, lifecycle or artifact ownership is rechecked.

Effect comparison requires unchanged original scene/entity facts, source/target
extents, physical Forward camera pose within explicit matrix tolerances and
exactly one actual haze/mirror setting transition. Executed pass direction must
match the actual setting. Each eye independently requires normalized color
histogram total variation >= 0.05 and blue-dominance delta > 10 for haze or
orange-fraction delta > 0.005 for mirrors, in the actual transition direction.
The statistic is a histogram change lower bound, not a claim of registered
pixel-to-pixel correspondence. There is no fixed Phone eye or desktop ROI.

`stereo-graphics-archive` v1 adds `reduce_original` for pure historical
recomputation at the original recorded interval. It accepts no current-clock or
guard substitution and cannot qualify freshness on its own. Live `measure`
retains its real final clock/guard and original 1500 ms age bound. An owning
adapter still needs durable planned/opened/saved file identity for both original
artifacts, scene/preferences/restoration, separate actor publication, actual
callback/resource retirement and quiet cleanup. This packet adds no full Pico
Graphics capability. Native source remains uncompiled; all devices are untested.


## Legacy open-tablet limit

The v1 photometry profile now refuses a physically shown tablet. Actual
`WebTablet.js` creates local Model/Web/Gizmo entities in the world layer, and
`RenderForwardTask.cpp` draws world/front items before ToneMapping. Therefore
`before-hud` is not a claim that the 3D tablet was excluded. A near-marker,
projected board ROI and whole-frame pass count cannot attribute colors under
an open VR UI. A red-then-green host counterexample enforces this refusal.

This closed-tablet prerequisite does not complete the common v16 Graphics
journey, which explicitly requires original images/effect changes while its
Graphics page is open. That flow needs a separately versioned original
per-surface identity/visibility proof (including Haze and reflected content)
before the complete Pico capability can be registered. Native compilation and
devices remain unverified; old photometry is not silently promoted.

## Exact historical analysis cache

Repeated archive validation may reuse only a successful pure analysis of the
exact same original PNG bytes, metadata bytes, run, ticket, fixture URL and role.
The process-local LRU holds at most 64 entries and 16 MiB of charged original
input, serialized result and context bytes. Results are deserialized into new
objects; callers cannot mutate previously accepted facts. Custom diagnostic
clocks bypass the cache and the existing five-second analysis budget remains.

No current observation, age, guard, file identity, provider status, acquisition
ownership, cursor or replay verdict is cached. Callers still read and verify
actual private originals, including SHA256/inode/mode, and run all current source
and query/frame continuity checks. Missing or changed files cannot be replaced
from this cache. Source packets and the v1/v2 evidence schemas are unchanged.
