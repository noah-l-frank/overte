# Original Pico Navigation panel lifetimes

`native-navigation-panels` v2 (reads closed v1) is a passive source, not an input or complete
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

The closed reply contains `navigationPanelsVersion: 2`, original command/run,
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
tablet nor implements a whole-area finalizer. The separate [normal lookup owner](../adapters/pico4/NAVIGATION_LOOKUP.md) now supplies Go To input/404/presentation. Full Script/XHR/
Web/callback retirement, restart and actor composition remain unfinished.

Do not add this source to Phone/iOS automatically. The nonce-only command and existing control row shapes stay unchanged; v2
adds lookup metadata and the opt-in raw Pico UI flag described below. A future platform
integration must supply that platform's actual root lifetime producer.

## Original lookup metadata in v2

The additive `lookup` object contains `complete`, nullable `home` and nullable
`address`. Its completeness is separate from the full root traversal: missing
original lexical objects, duplicate roots or unavailable properties cannot
become a successful lookup input source. Closed v1 remains readable for older
lifetime-only archives; one live source cannot change its producer version.

Home identifies the original `TabletHome.qml` lexical `tablet` and `swipeView`.
It reports the weak `rootId`, hashed component URL, actual `pageIndex`,
`pageCount` and visibility. Unready count zero/index minus one is preserved.
Address joins the original lexical `root` and `addressLine`, actual SHA-256,
length, focus/input readiness and visibility to the exact live address root
already in the lifetime inventory. Home is separate from Go To/Places lifetimes.

`NavigationLookupControls.h` shares these weak identities with native control
tokens. Original GOTO text/icons/button UUID, actual page delegate index,
root/page/draft/focus and mapped scene geometry contribute to the input source
fingerprint. Changed sources retire the prior token. No new QML controls or
product setters are introduced. The raw Pico frame adds the opt-in
`navigationLookupControlsVersion: 1`; existing control row shapes remain intact.
