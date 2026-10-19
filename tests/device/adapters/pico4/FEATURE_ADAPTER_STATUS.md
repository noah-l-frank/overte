# Pico feature adapter implementation status

Branch: `test/android-pico/shared-feature-adapters-20261019`.
Product base: `c5bf8ac17b`, composed with Main's common tests/flows through local
parent-to-child merges. No Phone branch was merged into Pico. No build,
installation, real device access or protected integration was performed.

Continuation: E2E-only native instrumentation is now explicitly authorized.
The shared `OVERTE_E2E_FEATURE_TESTS` packet supplies original native lifecycle
and evaluated animation/pose observations plus labelled render/audio/account
reads. `_native_feature_observer(target)` preserves the original candidate,
installed-byte, foreground and OpenXR process guards around that separate
read-only file. This source backend still advertises no `feature.*` triple.
The existing registered observation group now runs **15** host boundary cases,
including changed candidates, foreign PIDs and unavailable native hooks.
Native compilation and device behavior remain untested. See the
[native observation contract](../../native/README.md).

The internal `_recorded_preview_evidence()` joins original normal-preview
capture/sink PCM to the same verified candidate and OpenXR process guards.
Fixed private binary run-as reads, native cycle/event metadata, hashes and
actual cleanup observations remain separate from any audio verdict. Original
files surviving a release or candidate/process changes fail. There is no
complete audio capability or acoustic qualification. See
[the preview source contract](../../native/RECORDED_PREVIEW_EVIDENCE.md).

`_script_execution_observer()` uses the same original private transport and
candidate/OpenXR process binding for actual native engine identities and
CommonJS completion/cache/error history. The current shared feature contract
is **version 2**, correcting the Script file-bundle picker flow. Full file
picker/effect/cleanup joins remain open; no area triple is advertised. See
[the execution source](../../native/SCRIPT_EXECUTION_OBSERVATION.md).

The next packet now implements the five existing `scripts.*` foundation
operations through the real VR Tablet/MENU > Edit > Running Scripts controls.
It requires `OVERTE_PICO_NORMAL_SCRIPTS=1`, the original debug/OpenXR isolation
and candidate checks, and a native `featureControlsVersion:1` before input.
The E2E-only native resolver exports the real dialog/editor, row labels and
full delegate source URLs; reused rows retire tokens when their source changes.
Focused native Qt key/IME events replace the source field; ordinary VR pointer
events activate controls. No script service mutation or QML-handler invocation
performs these inputs. Cleanup attempts Stop and observed native absence before
original process teardown; lost candidate/process or ignored Stop retains
source intent and fails cleanup. A cleanup-only invocation revalidates the
original candidate lazily for source input, while teardown still works if that
verification fails. Ten real-wrapper host counterexamples pass, registered as
`normal-scripts` in the existing 42-group Pico suite. See
[the native Script control contract](../../native/NORMAL_SCRIPTS.md).

The internal `_script_file_picker(target,directory)` now reuses that same
candidate/OpenXR/normal Script UI context for the common Script bundle recipe.
The actual VR Tablet observer exports the real From File/picker delegates,
source URLs, selected flags, reviewed manifest and primary selection under
`fileControlsVersion:1`. A source/model change retires its token. The existing
VR surface pointer route activates controls; focused native key/IME/Return
and guarded primary-selector Home/Down/Return events perform edits. No source
load, file helper, QML handler or selection setter is an input shortcut.
Normal Script UI captures now recheck installed bytes before and after reads.

The ten-case group includes actual native token/recipe transactions, ignored
row delivery despite a successful ACK, primary readback and missing-marker/
candidate failures. The existing **31** candidate/navigation/Snapshot boundary
cases and **15** original-observation cases also pass after the extension.
All are device-free; native C++ remains uncompiled and actual VR/keyboard
delivery remains unqualified. A complete version 2 Script adapter still needs
owned original-byte staging, persistent picker/file/engine cleanup intent and
the advancing-effect/independent observer join. No new `feature.*` triple is
advertised. See [the common picker contract](../../native/NORMAL_SCRIPT_FILES.md).

`feature_observation.py` implements the original-observation backend on the
existing SH-009/installed-APK-bound Pico adapter. `_feature_observer(target)`
requires the actual candidate's E2E layer, configured isolated OpenXR session,
unchanged debug PID/start identity and current foreground package. Each read
checks installed bytes before capture and again afterwards, sends one closed
read-only request through `android-control-command.json`, and reads the original
private `normal-feature-observation.json`.

The response must carry the actual current random request ID, a strictly
advancing native source sequence, fresh target capture time, complete service
rows and the unchanged observer instance. Optional entity reads require complete
actual avatar-owned native rows. Neither a command ACK, a foreign request,
stale/cached rows, a failed query, a changed probe/process or a replaced APK can
return an accepted observation. Read failures have closed diagnostics without
selectors or raw native exceptions. No product API writes, UI actions, owned
entities or saved scripts are introduced by this reader.

This backend remains **internal** and advertises no `feature.*` capability.
It is not a complete area observer: the actual native script rows/entity IDs do
not establish v1 animation, account, peer, lifecycle, image, PCM or file facts.
Existing normal `places.*` and `snapshot.*` implementations remain intact.

Remaining input work after the normal Scripts packet:

* `android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp::controlId`
  exports GOTO/history, Home/pagination, SNAP and the new closed Script controls.
  Create, asset and other complete area controls still need their own bindings.
  Its `apply` validates current generation/control/source tokens.
* `PicoE2eTabletBridge.cpp::CONTROL_IDS` separately exports only the existing
  settings controls. The shared native API does not admit Create, script rows,
  source dialogs, asset mappings or their completion/ownership tokens.
* `PicoAccessibilityBridge.cpp` snapshots `OffscreenUi::getRootItem()` while
  the real VR controls are read from `TabletProxy::getTabletRoot()` by the E2E
  navigation bridge. The new Script input uses that actual VR root. The Android accessibility provider's existence alone
  therefore does not establish export of those VR controls. Reusing Phone
  W3C IDs/coordinates would be an unsupported presentation substitution.

The next input packet needs a source-reviewed, test-only extension of that real
VR automation boundary: ordinary pointer/key/IME actions, unique current object
tokens, dialog/full-URL row observations, bounded scrolling, cancellation and
process/bridge/generation ownership. The approved read-only native instrumentation
does not yet add these input controls. This is a concrete
missing native seam, not a simulated successful Pico adapter.

The independent fixture actor and original render/audio/share/export evidence
for all complete area contracts also remain missing. All fourteen v1 areas are
therefore **common test logic present; full adapter missing; device untested**.

Host validation uses the actual native candidate verifier and Pico wrapper with
only synthetic APK/tool/ADB/OpenXR/time boundaries. The new seven-case group is
registered in the existing Pico suite as `feature-observation` and mapped to its
tooling risk coverage. It checks ignored/foreign/stale/incomplete samples,
candidate changes on both sides, process loss, source instance changes and
sequence regression. It also verifies that no new feature capability or normal
input is advertised or delivered.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 android/vr/pico/tests/pico4-test-suite.py --test feature-observation --test suite-runner --test coverage-matrix
PYTHONDONTWRITEBYTECODE=1 python3 android/vr/pico/tests/device/test_native_execution_binding.py
```

These are host protocol/control-logic checks, not Pico product or physical
acceptance. Future hardware qualification must use the Proxmox Jenkins lab.
