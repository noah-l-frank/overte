# Pico original Lifecycle editor source v1

Lifecycle/input remains partial, with no complete feature capability. This
passive source supplies actual Qt editor/context identities and the existing
original VR entity-keyboard inventory. Native field/world input, the full
sixteen-step coordinator, independent publisher and final resource join remain
separate requirements.

The actual normal Pico Back route is now identified in
[`tabletUI.js`](../../../../scripts/system/tablet-ui/tabletUI.js): the
`pico-tablet-x-back` mapping receives `Controller.Standard.LeftPrimaryThumb`.
The original callback leaves a shown app page for Home; X on Home closes the
tablet. The Pico default script sets `deferTabletCreationUntilOpen`, the mapping's
existing enable condition. Overte's OpenXR plugin binds `left_primary_click`
to the Pico controller's `/x/click` and the standard left-primary channel.
The existing E2E `controller.button` profile maps left/primary to that same
original action. This is a real normal Back route even though NativeCreate has
no QML Back button. Calling Home or `returnToPreviousApp` directly still cannot
qualify this Back checkpoint.

`LifecycleUiObservation.h` is dedicated `OVERTE_E2E_FEATURE_TESTS` plus
`--testScript` instrumentation. The actual Pico TabletBridge additionally
requires the existing private E2E launch/results path, actual HMD mode, GUI
thread and native Keyboard/Tablet services. Commands in
`files/overte-e2e/lifecycle-ui-command.json` are exactly
`{schemaVersion:1,commandId,action:"observe",runId}`. There is no requested
editor, generation, text, keyboard flag, expected result, locator or input.
A native query nonce is consumed once, including on a failed result write;
4096 original queries bound the source lifetime.

The native source walks the actual original tablet surface. Create's
`NativeCreateText/newText`, Chat's `chatMessageInput/textArea` and Scripts'
`scriptFilter/filter` must have the exact native-configured canonical QML
context and original root/loader ancestry. Identical object names in a foreign
component do not identify an editor. Canonical Create/Chat URLs come from the
actual `PathUtils::defaultScriptsLocation()` directory; Scripts uses the native
configured `PathUtils::qmlUrl()`.

Each actual field/page/context/window/loader gets a bounded weak-object token.
Tokens are reused only for the same still-live QObject; destroyed-object address
reuse cannot resurrect an old token. The complete append-only editor inventory
retains original kind, tokens and `firstObservedEpochMs`. That timestamp denotes
actual first observation, never a fabricated QObject creation time. Every read
independently measures actual liveness, ancestry, clipped field visibility,
focus, current page and closed owned fixture text. Only the current editor can
expose empty or the run's Unicode/reply/retry draft. There are at most 64 editor
records, 256 object identities, 4096 visited items and 128 ancestry levels.
Overflow or an ambiguous current editor is unavailable.

`keyboard` is the unchanged original `Keyboard::featureChatObservation()` v2
inventory, including every real key/layer/entity, actual visibility and pressed
state, target and tablet-screen ownership. The Python source reuses
`vr_keyboard` validation. A QML keyboard request or generic touch metric cannot
replace this actual VR source. Source acquisition is bounded to five seconds
and 51 reads; actual native/PID/installed-candidate/OpenXR guards wrap each I/O.

The private `lifecycle-ui-observation.json` packet has exactly
`lifecycleUiVersion,commandId,runId,instance,sequence,processId,capturedEpochMs,source`.
Its source has exactly `complete,tabletShown,onHomeScreen,current,editors,keyboard`.
Each editor has exactly `id,kind,fieldId,pageId,contextId,windowId,loaderId,
firstObservedEpochMs,alive,attached,visible,focused,current,text`.

The guarded internal factory `_lifecycle_ui_source(target)` supplies the existing
Pico transport. `capture(run)` retains the original JSON and its actual SHA-256,
with native/keyboard instance and advancing cursors. Private summary version 1
preserves the complete original editor identities and retirement history across
host process reconstruction. Missing old records, rewritten identities/times,
resurrection, foreign PID/run/source/keyboard, old cursors or stale replies fail.
The source never assigns public generations 1–4 from input requests: a future
coordinator must bind those aliases only to actual distinct observed contexts.

Focused verification uses an owned private `TMPDIR` and
`PYTHONDONTWRITEBYTECODE=1`:

```bash
python3 tests/device/self_tests/test_pico_lifecycle_source.py -v
OVERTE_NATIVE_QT_MAJOR=5 OVERTE_QT5_HOST_ROOT=/prepared/qt5/root \
  python3 tests/device/contracts/tablet/test_lifecycle_ui_observation.py
python3 tests/device/validate_contract_versions.py
python3 tests/check-documentation.py --all
git diff --check
```

The eight Python cases use explicit synthetic original native/keyboard
boundaries. The compiled Qt5 check loads the real NativeCreate.qml, sends a real
normal Qt pointer focus, destroys the actual page and reconstructs it. It proves
real context/page/field retirement and new identity, with the same actual window
and loader. Keyboard and TabletRoot hosting are explicit host boundaries; no
real VR keyboard, OpenXR input, headset, independent peer or device result is
claimed. The Pico TabletBridge binding itself remains uncompiled by this narrow
header/QML check. Full tracking/effective-held-input/original-displacement and
pending-event/ordinary-X/background/cleanup composition remain unfinished.
