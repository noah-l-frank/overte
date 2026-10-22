# Original Pico Places and durable bookmark operations

This is a source/host-verified component of the unfinished Worlds/navigation
adapter. The full Navigation feature triple is unavailable. World arrival,
stereo originals, selected-origin/account/federation restoration, whole-area
composition of the [lookup-error owner](NAVIGATION_ERROR.md), actual restart,
independent peer and final resource retirement
still need whole-area composition. Native additions are uncompiled; no device
or product behavior is qualified.

## Existing normal input route

`native-places-controls` v1 extends the existing Pico `NavigationUi`, rather than
adding a second input bridge. It requires both `OVERTE_E2E_FEATURE_TESTS` and
`ANDROID_APP_PICO_INTERFACE`. The ordinary Android implementation of
`PlatformInfo.has3DHTML()` returns false, selecting the existing
`scripts/system/places/PicoPlaces.qml` through the original Places script.

The resolver verifies the actual file/qrc component context and semantic root.
It reads the original QML IDs, original `QAbstractItemModel` rows and Controls 2
popup/footer. The anonymous Cancel button is its actual attached RejectRole.
Text input, clicks and scrolling use the existing focused-field helpers and
controller pointer callbacks. No QML handler, model, selection, location,
bookmark API or setting is mutated by instrumentation.

The optional `placesControlsVersion: 1` family includes the Home PLACES entry,
tabs, actual search/model, refresh, maturity controls, original bookmark
add/name/save/cancel and per-row visit/rename/delete, and actual server/list
controls. Names, addresses and directory IDs are hashed before publication;
unowned text and URLs remain private. Models are bounded to 256 rows each.
The weak original Places root identity admits at most 16 live roots and 256
retired identities without extending QObject lifetime. It detects replacement;
it does not by itself establish complete resource retirement.

Tokens bind the current root, complete observed model/dialog/query state and
actual target geometry. Input requires the original five-second reference,
candidate/process/OpenXR binding, live focus, ordinary enabled/visible hit target
and an idle original 230 ms dispatch timer/queue. Controller acknowledgments
remain distinct from effects. The parser retains old snapshots without the new
family and rejects malformed/unknown new metadata.

`TokenPlacesUI` uses the existing `PicoNavigation` route through `PicoPlacesIO`.
Only this run's two bookmark names and owned directory name can be selected;
search text is restricted to its actual controlled challenges. Server writes
require a separately owned origin recipe and are currently refused. Every
mutation records intent before its one send. Original consumed input sequence,
field hashes/focus, dialog state and model rows are observed separately.

## Durable independent storage flow

`navigation-bookmark-operations` v1 connects these inputs to the independent
[native map/backing-file reader](../../native/LOCATION_BOOKMARK_OBSERVATION.md).
The internal `_bookmark_operations(target, path, run)` factory uses the actual
bound normal-Scripts runtime, its candidate/session identity and the existing
private native transport. The parent must already own an open, loaded Places
page, private state path and the source/input lock. This component creates no
new public operation or complete feature capability.

`NavigationBookmarks.act(ticket, verb)` implements add cancellation, add, rename
cancellation, rename and delete. Preparation refuses collisions with either
run-owned name. Baselines retain original native packets, backing-file/map
digests, unowned UI/storage digests, actual current-address digest and weak root
identity. No requested address becomes observed persistence or world arrival.

Each exact input stage has a durable pending record before delivery. If a
reply is lost, recreation reads the same stage and joins its original consumed
native input sequence with the independently observed effect. It never resends
that input or replaces an unresolved ticket. Source birth, candidate, current
root, complete unowned storage and original address must remain unchanged.
The native cursor and original timestamps survive adapter recreation.

Cancellation must leave the entire original native map and file revision
unchanged. Save/rename/delete require actual persisted owned entries and the
matching current bookmark model. A closed dialog or ACK is insufficient.
Every operation ends with three seconds of unchanged native storage and current
UI, using both original epoch and UI elapsed clocks. Source gaps above 1500 ms,
stalled UI snapshots, extra consumed inputs or retained writes fail. Native/UI
original clock headers and native quiet packets remain in the private journal;
archive validation preserves their timestamps. A complete operation has a
20-second budget; native reads retain their existing five-second/51-read bound.
The journal admits at most eight operations and retains the existing 64 KiB
private-state bound. The shared scenario needs five bookmark operations.

The journal remains owned for the future whole-area finalizer. This component
does not transfer ownership across an app restart or delete its metadata while
Places, callbacks or parent resources may remain. Unresolved ownership survives
failures so final cleanup cannot report success prematurely.

## Host verification and remaining composition

The complete five-operation flow executes actual Python UI projection,
`PicoNavigation` admission, private factory, durable state and native reader
against synthetic Qt/OS/input boundaries and a separate private host storage
file. Counterexamples cover ignored input/persistence, lost applied focus/save
replies, stale/changed references, foreign names, native cursor/root/candidate
replacement, changed unowned data, identical-byte rewrites, retained writes,
operation deadlines and stalled UI clocks. Node also executes original QML
dialog handlers, script bookmark handlers, search filtering and refresh logic
with synthetic native boundaries. These are adapter/source tests, not native
filesystem or physical VR qualification.

The inspected original READY_FOR_CONTENT path calls `transmitPortalList`, which
aborts the previous request, clears cached portals and starts a new generation
fetch. Every open must join its actual provider response and consumed current
model. No cached-list or completed network receipt alone establishes this.
The [normal directory owner](NAVIGATION_ORIGIN.md) provides original
endpoint/account/settings observation and guarded selection/restoration. Next
compose it with directory response consumption/model/arrival, original lookup
error and remaining Go To closure, restart and the independent final observer.
