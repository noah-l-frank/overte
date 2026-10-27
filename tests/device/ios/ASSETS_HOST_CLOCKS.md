# Assets factory host/native clock boundary

`IOSAssetsRuntime` now has an explicit host epoch callback, defaulting to actual
`time.time() * 1000`, alongside the existing host monotonic callback. Model
source factories use that host callback; parsed sources inherit it from their
actual Model source. Scene factories use it for their independent host bracket.
Native sample/guard callbacks and original native transport remain unchanged.

The prior Model and Scene factories passed `observer.epoch_ms`. The canonical
Script runtime intentionally binds that observer callback to a separately
acquired native clock. It is correct for native freshness, and incorrect as a
host timer. In the Model collector it can also issue additional native clock
queries outside the declared native BEFORE/AFTER endpoints, because the clock
transport is journaled during collection. The correction gives the host
bracket its own true host callback, without removing any typed native guard or
source reads. Parsed sources require no reconstructed timestamps or copied
native values.

No old original is retimed, rewritten, relabeled or repaired. Earlier direct
fixture collectors supplied explicit separate synthetic host clocks; those
component results do not retrospectively qualify the old factory's clock
origin. Old private ownership remains inspectable for responsibility, and no
full Assets/Actor/publication capability is enabled by this correction.

## Exact host evidence

- `assets-host-native-clock-factory-first-20261027.log`: two direct canonical
  cases passed in 0.719s. The Model/parsed host callback is the explicitly
  supplied host function and invoking it issues no native query. A complete
  Scene factory acquisition retains host epoch near `1.9e12` and independently
  produced native epoch near `20k`; its four typed source responses and six
  owned raw originals are retained under the existing callback/nonce/guard
  codecs. Extra native freshness reads remain native freshness reads.
- `assets-host-clock-runtime-scene-compat-20261027.log`: 26 relevant existing
  factory/failure/Scene/peer-counterexample cases passed in 6.160s. Candidate,
  process, current guard, prefix/inode and no-repeat ownership are preserved.
- `assets-host-clock-project5-20261027.log`: the five explicit documentation,
  documentation-contracts, iOS input-selection, policy-consistency and
  project-coverage suites passed in 6.88s; version and whitespace checks pass.

The 1.5-second acquisition window, 250 ms clock agreement, source completeness
and process/candidate bounds are unchanged. Native, Qt, SDK and network sources
in these tests are declared models; no device, compiler, real service, rendered
model pixels or complete Assets journey has been qualified.
