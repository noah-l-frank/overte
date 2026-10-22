# Original native background UI and VR-keyboard history

`native-lifecycle-background:1` is a passive source component, without normal
background/resume input or a complete feature verdict. It captures original
facts while the host's ordinary foreground-only readers are unavailable. The
foreground guard is unchanged. The same source supports a visible current Chat
that is already empty/unfocused or contains the Lifecycle Reply; arming does not
focus, type, hide a keyboard, change channels or mutate the product.

The actual test-gated Pico TabletBridge owns `LifecycleBackgroundHistory` for
its real process lifetime. The source requires the dedicated feature build,
`--testScript`, actual canonical private probe and private directory, GUI thread,
HMD and existing Tablet/Keyboard services. Its native callback reuses the same
unchanged `LifecycleUiObservation` and actual `Keyboard::featureChatObservation`
as normal Lifecycle reads. Source-qualified weak editor identities and native
UI/keyboard cursors therefore keep their original meaning. Autonomous samples
remain in this source's memory; they never overwrite another host query's fixed
UI result file.

The first arm requires an actually visible current Chat in native Qt Active.
Original field/page/context/window/loader identities and first-observed time
are bound. An actual `QGuiApplication::applicationStateChanged` notification
causes an immediate sample; its argument must equal the current native Qt state.
A fake signal argument cannot create a background fact. A native QTimer also
samples every 250 ms. The record preserves all original frames, with at most
96 frames over 20 seconds. Missing HMD/root/keyboard sources, backward clocks,
identity replacement, expiry or overflow become unavailable; they cannot look
like successful keyboard absence. Release stops the actual timer and preserves
its original history. The QObject/connection lifetime remains process-owned.

Only these private commands are accepted in
`files/overte-e2e/lifecycle-background-command.json`:

```text
{schemaVersion:1,commandId,action:"feature-lifecycle-background",operation,runId}
```

`operation` is `observe`, `arm` or `release`; mutations additionally require the
actual `ownerInstance` and next `intentSequence`. An original command ID is
consumed once, including unknown outcomes. A repeated exact ID returns its
original cached result and never resamples it. One run can arm this source only
once per process. All observations use native PID, UUID instance, query cursor,
clock and original arm/release command IDs. A release ACK alone cannot prove
client keyboard/focus quiet or retire the source QObject.

The original private result is `lifecycle-background-observation.json` with
`lifecycleBackgroundVersion,commandId,runId,instance,sequence,processId,
capturedEpochMs,lastIntentSequence,performed,available,active,timerActive,
released,expired,ownerRunId,originalId,armedEpochMs,armCommandId,releaseCommandId,
frames`. `timerActive` reads actual `QTimer::isActive()`.

Every immutable original frame has `frameId,sequence,capturedEpochMs,elapsedMs,
cause,applicationState,signalSequence,uiInstance,uiSequence,uiCapturedEpochMs,
tabletShown,onHomeScreen,currentId,focusedEditors,editor,keyboard`.
`applicationState` is the actual native `active/inactive/hidden/suspended` state;
`cause` names `arm/timer/query/application-state/release`. `editor` retains the
complete original Lifecycle row, including separate weak liveness, focus and
actual current closed draft. `keyboard` retains the actual native instance and
cursor plus `created,enabled,visible,raised,keyCount,pressedKeys`. Visibility is
the existing original native getter's entity-tree result, and pressed count is
reduced from all its original native key rows. This new narrow source exports
those original facts; it does not duplicate the complete key/entity inventory
for every history frame or substitute a QML keyboard request.

`adapters.pico4.lifecycle_background_source.NativeLifecycleBackground` provides
`read(run)`, `arm(run)` and `release_owned(run, original_arm_request)`.
`restore(original_raw)` validates an archived original packet and restores only
its history barrier; it sends no query and returns no current observation. The
next read must acquire fresh bytes with the same native instance and unchanged
original frame prefix. Original raw bytes/hash remain preserved.
`_lifecycle_background_source(target, source_lock=parent_lock, intent=...)` binds
the actual candidate/process and exact parent Script source-lock instance.
The intent callback must persist each original mutation request before send.
Uncertain arm/release only reads original native command IDs and immutable
frames. A changed source cursor or another arm cannot authorize release.
Unavailable history remains unavailable even after its timer is stopped.
The reader bounds raw UTF-8 before decode and checks immutable frame prefixes,
original identities, native counters and final native/monotonic freshness after
result construction and the last candidate guard. Existing Chat draft factories
also accept the exact parent lock/join for nested whole-flow composition.

The focused Qt5 check executes the actual Chat QML and normal native IME, actual
weak Qt source, history timer, native request admission and false-signal rejection.
It validates the real native JSON through the strict Python schema. It also
compiles the complete original new TabletBridge source methods and existing
private writer against declared service interfaces, catching source-wiring
errors without claiming a complete Pico application translation-unit build.
Physical VR visibility and OS Hidden transitions are explicit host boundaries;
the host run proves no actual device background acceptance. Reader tests cover
native-history boundaries, lost answers, unchanged prefixes, foreign cursors,
failed persistence, raw limits, busy shared publishers and final stale clocks.

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<private-directory> \
  OVERTE_NATIVE_QT_MAJOR=5 OVERTE_QT5_HOST_ROOT=<reviewed-qt5-root> \
  python3 tests/device/contracts/tablet/test_lifecycle_background.py
PYTHONDONTWRITEBYTECODE=1 TMPDIR=<private-directory> \
  python3 tests/device/self_tests/test_pico_lifecycle_background_source.py
```

A whole background owner must still join its durable arm to normal OS HOME,
actual original OS process/foreground proof, native lifecycle advancement,
original Hidden/Suspended frames with real keyboard/focus absence, normal return,
fresh same-context draft/model observations, quiet and original timer release.
VR absence requires that original enabled/created keyboard's actual visibility,
raised state and pressed-key count to be clear; a disabled or missing keyboard
cannot borrow a false visibility flag as whole-journey proof.
Neither a resumed-only keyboard read nor a historical frame without that actual
OS/lifecycle join establishes the journey. No journals or histories retire here.

`lifecycle_background.validate_return` now provides the pure original-evidence
join for the Lifecycle Reply checkpoint. It verifies the original PID/start and
candidate binding in both independent OS states, native background/activation
advancement without another launch, unchanged graphics/audio/account settings,
the exact native arm request and immutable prefix, and original Hidden/Suspended
then Active signal history after the last pre-HOME boundary. Actual enabled,
created keyboard absence and zero pressed keys are required during background
and after return. The fresh full normal UI must follow the last history cursor
with the same original field/page/context and Reply. Retained partial identities,
resumed-only false keyboard values and input acknowledgements cannot qualify it.
This pure historical verifier sends no input and establishes no current age,
three-second quiet, observer release or complete feature verdict. The durable
normal OS coordinator and final original-source acquisition remain separate.
It reports no editor generation: the earlier original Create/X/Chat history
must independently establish that ordering in the whole Lifecycle composition.
