# Android Phone World Navigation, contract v17

The complete `feature.world-navigation.act|observe|cleanup` triple is registered
in the existing Phone Appium adapter and common Journey. It is default off:
`OVERTE_PHONE_FEATURE_WORLD_NAVIGATION=1` requires a bound controlled Phone debug
candidate, the existing private fixture reader credential, an owned navigation
provider, and a private `OVERTE_PHONE_NAVIGATION_IMAGE_POLICY` file. Missing
abilities prevent advertisement or observation success.

The policy has exactly `imageExtent`, `markerRoi`, and `imagePolicy` keys. Example
for a controlled 640 by 480 render target:

```json
{"imageExtent":[640,480],"markerRoi":[20,20,180,60],"imagePolicy":{"source":"world-render-target","marker":[24,24,152,56],"subject":[200,100,600,420]}}
```

The marker interior must match the original marker geometry; the independently
chosen subject rectangle must not overlap it. `OVERTE_DEVICE_ARTIFACT_DIR` must
be a private artifact directory. No policy or expected image is learned from a
target. The normal AccountManager directory endpoint, protocol and source
revision must already match the controlled provider. The owner never changes
preferences to make admission pass.

## Original inputs and observations

Ordinary W3C tablet/Go To inputs and token-bound native Qt pointer/key/IME inputs
operate the original Places page. There are no direct QML handler, bookmark,
location or expected-state assignments. Native controls are bound to original
QML contexts, row roles, current addresses and bookmark-dialog identities. A
conservative transparent-decoration accommodation permits ordinary Quick event
delivery; enabled foreign pointer handlers, overlays and input controls still
block input. Input acknowledgment establishes delivery only.

Each observation independently reads fresh original Places query/full input
records/ListView models, live native preferences, actual bookmark memory and
backing-file bytes, OS keyboard metrics, current native lifecycle and grounded
world probe. Before/after native brackets must agree. Directory records and
not-found callbacks join immutable completed HTTP receipts from the separately
owned provider. A not-found modal must also have the exact weak original dialog
identity recorded by the actual AddressBarDialog callback; matching text alone
is insufficient.

A small E2E-only local Web marker is an input fixture. Its actual original
object/view identity, original Browser/GPU/runtime readiness and current
world-target PNG are independently acquired. Both directory arrival and return
by bookmark require their own marker and body pixels. Each role owns its own
capture receipt and PNG. Restart uses ordinary Stop/Launch once, actual old PID
absence, a new native process/lifecycle, and unchanged persisted bookmarks.

`script_observer.py` configuration version 3 accepts `area: world-navigation`.
It uses its own `actorToken`, candidate binding and source acquisitions. The
primary cannot publish peer samples or issue actor input. The fixture service
keeps its existing separate reader/publisher permissions. The observer must
remain available until it independently retires after fixture shutdown.

## Ownership and recovery

Versioned private candidate/session/run/role journals persist intent before
input. Uncertain input is never replayed after reconstruction. Fresh original
cursors, marker identities and GPU acquisition/frame identifiers advance;
historical records never satisfy a new observation. Immutable digest-bound frame
and owner files retain evidence within the existing journal size limits.

Cleanup cancels owned dialogs, dismisses only the original owned error, removes
only run-owned bookmarks, drains the same marker and Browser, releases capture
receipts, restores A through normal Go To, and verifies unchanged foreign
bookmarks/preferences, hidden keyboard, absent UI and empty original queues and
timers. Both roles independently prove a three-second quiet window. Failed
bootstrap also retains cleanup responsibility; after actual provider retirement
it may acquire new independent quiet evidence without publishing a baseline or
peer success. Global finalization waits outside the source lock for the actor,
restores the admitted original URL through ordinary inputs, archives evidence,
and CAS-removes and verifies absence of control journals. Repeated finalization
is idempotent. Interrupted PNG writes retire only their recorded inode after a
durable archive intent and verified absence; unrecorded or foreign files remain
unresolved and prevent success.

## Verification and limits

`android/phone/tests/device/test_navigation_feature.py` exercises the actual
registered public facade and complete 17-checkpoint common v17 Journey using
explicit synthetic target boundaries, real private journals, PNG decoding and
independent actor acquisitions. Counterexamples cover ignored inputs/cancel,
lost Save return without replay, foreign modal provenance, replayed native
cursors, changed preferences/candidate/keyboard, failed bootstrap, default-off
registration, observer/probe grammar, and partial/foreign host files. Existing
navigation resource tests additionally execute the actual controlled loopback
HTTP service and credential separation.

```sh
python3 -m unittest discover -s android/phone/tests/device -p test_navigation_feature.py -v
PYTHONPATH=tests/device python3 -m unittest self_tests.test_navigation_resources self_tests.test_native_navigation_replies self_tests.test_navigation_source_semantics self_tests.test_phone_navigation self_tests.test_places_navigation
python3 android/phone/tests/phone-navigation-native-test.py --build-dir build/phone-navigation-native-review
```

The feature tests are also registered in the existing mandatory Phone runtime
regression entrypoint. Its prepared-host mode includes the native check;
without `--build-dir` that check allocates a new unique checkout-local build
directory and never reuses a previous or frozen build.

The native host check compiles the original controls/reply/modal sources and
passive navigation-view header against installed Qt6, then runs unmodified
`PicoPlaces.qml` with real ordinary Qt inputs and foreign-overlay refusal. It
uses explicit resource-path and script-message host seams. This is a partial
native check: Android/Qt5 product translation units, marker Entity/Browser/GPU
integration and an APK are **not compiled here**, and all device behavior is
**untested**. No installation, device transport or lab execution is implied.
The shared Emote code-pin catalog must be refreshed centrally after integration
because the probe source changed; do not learn those pins from a target.
