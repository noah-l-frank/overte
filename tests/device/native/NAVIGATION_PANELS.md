# Original Pico Navigation panel lifetimes

`native-navigation-panels` v1 is a passive source, not an input or complete
Navigation capability. It is compiled only with `OVERTE_E2E_FEATURE_TESTS` and
`ANDROID_APP_PICO_INTERFACE`, requires `--testScript`, and observes on the actual
GUI thread. The Test scripting entry also requires the original active test
lifecycle and private test directory. Native sources remain uncompiled; every
Qt/QObject/OpenXR/device boundary in host verification is synthetic.

`NavigationUi::observe` supplies its actual complete root/window and frame.
`NavigationPanelsObservation` traverses all children, including hidden retained
items, without creating pages, changing properties, calling handlers or holding
strong QObject references. It recognizes original Pico Places and
`TabletAddressDialog.qml` using their lexical root, actual component URL and
original semantic/class identity. Original component URLs are hashed; no address,
settings, text, credentials or arbitrary source paths are published.

Places IDs use the same existing weak identity helper as the original UI and
directory observer. Go To uses its own original weak identity. Pointer reuse
cannot revive a dead record. Every observed root remains in the bounded history,
with immutable profile/source hash and **first observed** epoch, not an invented
creation epoch. `alive` comes from `QPointer`; `inCurrentTree` and `visible` are
separate facts. Hiding or detaching a still-live page never proves destruction.

The nonce-only command is exactly `schemaVersion: 1`, `commandId`,
`action: feature-navigation-panels` and `runId`. The original probe writes the
fixed private `feature-navigation-panels.json`; no expected root, selector,
cleanup instruction or preferred result is accepted. Missing instrumentation is
unavailable, never an empty successful inventory. The actual private Pico reader
retains candidate/process guards and the original native clock.

The closed reply contains `navigationPanelsVersion: 1`, original command/run,
source instance, sequence, PID, epoch, `complete: true`, roots and the original UI
bridge/generation/input counter/elapsed/epoch/open/ready fields. Each root has
`rootId`, `profile` (`pico-places-v1` or `pico-address-v1`), `sourceSha256`,
`firstObservedEpochMs`, `alive`, `inCurrentTree`, `visible`. Publication requires a
complete traversal and a frame no older than 1500 ms. Bounds are 4096 traversed
items, depth 128, 128 retained roots, 4096 unique source queries; overflows or
clock regressions fail closed. Query waits are under five seconds with one send.

The Python reader requires increasing original source/input/elapsed clocks,
unchanged process/bridge/birth, complete retained history and no resurrection.
A previously unknown older root cannot be silently adopted. `retired` succeeds
only for explicitly known root IDs whose actual weak pointers are dead.

Transit v2 persists original Home entity geometry before the normal OpenXR ray,
then joins actual Home state, unchanged Qt input count, measured destination,
original bookmark file/map, original directory root and this complete panel
inventory. Both the old Places root and any Go To root must be retired before
success. Three seconds of original quiet follow. This neither closes the whole
tablet nor implements the remaining Go To input/lookup owner, full Script/XHR/
Web/callback retirement, restart, actor or complete Navigation finalizer.

Do not add this source to Phone/iOS automatically. It changes no existing UI
wire shape and is a Pico-only additive reader/probe entry. A future platform
integration must supply that platform's actual root lifetime producer.
