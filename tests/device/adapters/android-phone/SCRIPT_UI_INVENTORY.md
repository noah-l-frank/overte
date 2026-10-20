# Phone Script UI inventory, version 1

This E2E-only passive source covers manager display during a file dialog and
actual UI absence. It is an internal prerequisite, not a full `feature.scripts`
implementation. It requires `OVERTE_E2E_FEATURE_TESTS`,
`ANDROID_APP_PHONE_INTERFACE`, `--testScript` and the existing private result
directory/lifecycle guards. No script, picker or tablet input is added.

The original `phone-script-file-ui` observation may additionally contain
`scriptInventory`, with exactly:

* `inventoryVersion:1`, `complete`: an actual boolean;
* `tabletPresent`, `tabletShown`: actual booleans from a non-creating lookup of
  the existing system tablet proxy and its original `tabletShown` property;
* `managers`: at most 16 original manager-status v1 objects;
* `pickers`: at most 16 objects with exactly `componentSource`, `visible`,
  `closing`, `requestId`, `errorText`.

The tablet lookup is a plain guarded C++ method, outside the scripting API.
It never calls `getTablet()`, creates a proxy, loads a component or changes
visibility. An absent proxy is measured from the existing proxy map. Missing
service, wrong thread or malformed property yields unavailable, not hidden.

`ScriptUiInventory` observes the original bounded `NormalControlUi` tree walk,
including hidden items and its existing Qt overlay coverage. This Phone recipe
uses the normal Android screen-space tablet in the original OffscreenUi tree;
it does not qualify an alternative external/VR tablet surface. Input visibility,
enabled state and removal of the From File input row under a modal do not remove
passive observations. The existing limits remain 4096 nodes, depth 128 and 384
input rows; duplicate visits, ambiguity, overflow or unready roots invalidate
completeness. Incomplete inventories contain empty arrays and cannot establish
absence. Capture has the existing five-second/51-read limit, nonce, PID,
native clocks, advancing cursors and installed-candidate/source guards.

Every matching `RunningScripts` object must resolve to the canonical
`PathUtils::qmlUrl("hifi/dialogs/TabletRunningScripts.qml")` context and original
root id. The original manager layout and status Label have local `scriptLayout`
and `scriptStatus` ids only; their behavior/bindings are unchanged. Bounded
direct-child reads preserve actual status and independently bound Label text.
Unknown matching roots cannot silently become absent. This deliberately refuses
a desktop wrapper or foreign matching component outside the Phone source recipe.

A Script picker must have the ordinary exact caption/bundle/primary-filter
properties and the original root id in the canonical
`dialogs/NativeFileBrowser.qml` context. Its closing flag, system request id
and error are read from original typed properties. Visibility uses the original
window and finite geometry/ancestor clipping, without inferring success from
the last input. Raw context/text/request values remain private.

`_script_ui_state(selector)` acquires fresh original bytes, then uses
`script_ui_inventory.ui_state`. It refuses missing extensions, incomplete scans,
multiple visible managers/pickers, an orphan visible picker and impossible
proxy/visibility combinations. Hidden retained roots cannot reopen a page or
carry its old error. Original `tabletShown:false` takes precedence over retained
offscreen geometry. The result preserves `open`, `picker`, the actual current
`manager` and `pickerSource` objects (or measured absence), and `systemPending`.
An outstanding request remains pending even in a hidden dialog. A closing ACK
does not hide a still-visible picker. Separate root/Label texts remain separate;
this component does not classify a load as `NotFound`.

Old producers without this optional extension retain existing picker-input
compatibility. They cannot qualify this new complete UI source. Unsupported
versions and unknown fields are rejected; migration must be explicit. Cleanup
must additionally prove no active manager/picker, no system request and separate
engine/effect/native-file absence. These observations do not release ownership,
replay Cancel, stop a script or delete fixtures by themselves.

Fifteen device-free inventory cases plus four Phone factory counterexamples
cover carrier suppression, actual open/close, hidden retained roots, incomplete
or foreign sources, ambiguity, orphan dialogs, outstanding requests, ignored
close, old nonces/clocks/PIDs and candidate replacement. All 130 Phone
feature-adapter host cases pass. These exercise Python readers and synthetic
boundaries only. Native C++ remains uncompiled and devices untested. A full
nineteen-step coordinator and independently acquired actor facts are still
required before any complete feature capability can be advertised.
