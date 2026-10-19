# Normal native Script controls, version 1

This is a test-only extension of the existing Pico/iOS native UI boundary and
the existing `scripts.*` foundation flow. It is not a complete fourteen-area
feature adapter. `OVERTE_E2E_FEATURE_TESTS` remains default OFF. An instrumented
native UI observation additionally publishes `featureControlsVersion:1`;
script flows refuse an old/missing producer before opening a tablet.

`NormalScriptControls.h` identifies real Qt controls by their source names and
structure. The closed IDs are `scripts.entry`, `scripts.menu`,
`scripts.menu-edit`, `scripts.menu-running`, `scripts.from-url`, `scripts.list`,
`scripts.url.field/submit/cancel`, `scripts.restart.<0..127>` and
`scripts.stop.<0..127>`. The existing Home/pagination controls are reused. Pico
uses the real MENU > Edit > Running Scripts route when SCRIPTS is not a
first-party app in its startup profile. Neither adapter changes that profile.

The unnamed URL editor must belong to the actual `Open and Run Script` /
`Script URL` dialog and be a real QQuickTextInput. Only that dialog's actual
OK/Cancel buttons can submit/cancel it. An open source dialog masks underlying
controls. Inputs are ordinary pointer and focused field key/IME events; the
helper cannot call ScriptEngines, ScriptDiscoveryService mutations or QML slots.
URLs are restricted to the existing owned HTTP(S) script-management sources and
Create observer; credentials, query strings, fragments and arbitrary sources
are refused at the native boundary too.

Each row carries the actual adjacent native Label and the **full original URL
from that delegate's QML modelData**. The reviewed Label/Restart/Stop trio must
match the same ordinal. Native tokens must retire when either the object or
its actual source identity changes, including in a reused delegate. Before a
row action, the shared manager independently rereads actual native service
order, checks the full URL and current label/token, and never retries uncertain
input. A matching basename from another origin is insufficient.

`TokenScriptUI` implements normal app/menu entry, source entry, row actions,
cancellation and stable disappearance. The owning IO validates complete native
schemas, PID/instance/clock/control tokens and original installed candidate
identity. Open/navigation waits are bounded to ten seconds/101 reads; page
construction gets 0.6 seconds, with at most 32 observed pages. No page/input is
replayed after an uncertain mutation. Field readback verifies text delivery;
the independent common journey still verifies execution/companion effects.

The shared `NormalScriptManager` continues owning private intent and cleanup.
An ignored Stop or changed candidate/process retains unresolved source intent;
force-stopping the app does not establish removal from persisted running scripts.
Host boundary simulations verify these rules, not native compilation, Qt/VR
delivery, product execution, complete local-file/folder/consent workflows or
device acceptance. Bounded scrolling beyond currently visible script rows is
not implemented by this packet and must not be treated as successful input.
