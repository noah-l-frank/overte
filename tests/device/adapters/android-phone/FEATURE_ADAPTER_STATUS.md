# Phone adapter implementation, local source only

Branch: `test/android-phone/shared-feature-adapters-20261019`.
Product base: `718d069add` (Phone typed-config parity repair), composed with the
Main common-journey branch through ordinary local parent-to-child merges.
No protected integration, build, install or device execution was performed.

Continuation: the user explicitly authorized E2E-only instrumentation in native
client sources. The opt-in `OVERTE_E2E_FEATURE_TESTS=ON` source packet now supplies
actual lifecycle notifications, evaluated animation/pose metadata, and labelled
native render/audio/account reads. `_native_feature_observer()` joins these
original private bytes to the existing installed-APK, PID/start, foreground and
Appium session guards. The actual loaded animation resource URL is distinct from
its requested URL. Stale poses and candidate/process changes fail. These sources
are not complete area adapters and advertise no `feature.*` capability. Native
compilation and devices remain untested; focused Phone boundary tests now number
**31**. See [the native source contract](../../native/README.md).

The internal `_recorded_preview_evidence()` now acquires the normal memory
preview's original pre-normalization capture and accepted sink-write PCM through
that same candidate/process guard. Binary run-as reads verify fixed private
regular files and completion frames; hashes, native cycles/events and source
times bind the separate bytes. Cleanup queries actual native file/memory state
and independently checks Android file absence. This is an observation source,
not a complete audio capability or acoustic proof. See
[the preview source contract](../../native/RECORDED_PREVIEW_EVIDENCE.md).

`_script_execution_observer()` joins actual native ScriptManager identities and
resolved CommonJS completion/cache/error history to the same installed-candidate
and PID/start/session guards. It never sends source names or code. The current
shared feature contract is **version 2**, with a real client file-bundle picker
flow; these history/URL foundations still do not implement that full area. See
[the execution source](../../native/SCRIPT_EXECUTION_OBSERVATION.md).

The internal `_script_file_picker(selector,directory)` now binds the shared
ordinary file-bundle recipe to a dedicated E2E-only Qt source/input core on
Phone. `Test.phoneScriptFileUi` exists only in feature-enabled Phone builds and
requires the explicit test launch/results boundary. It observes the actual
OffscreenUi root/window and real existing picker controls. Normal Qt mouse,
focused key/IME and ComboBox keyboard events deliver input; no file helper,
QML handler, Script service or selection setter substitutes for user input.
The existing private Android command/probe channel carries the closed
`phone-script-file-ui` action. Native core, probe and Python IO each validate
their boundary. Current installed APK/PID/start/session guards remain in force.

The native source pins actual root/window generation and source-sensitive
control tokens. Its input cursor is consumed before dispatch. The host checks
fresh original native rows and then verifies actual folder, chosen URLs, review,
primary and disappearance through the common recipe. A successful delivery
acknowledgement alone cannot prove selection or execution. Retired generation,
foreign acknowledgements, ignored row/primary selection, partial files,
missing native marker and candidate changes have host counterexamples.

This **does not complete** version 2 Scripts: the owning wrapper still needs
private original-byte staging, persistent file/picker/engine cleanup intent and
the actual advancing-effect/independent observer join. A failed input may leave
the real dialog open; the future owner must retain intent and cancel it through
the normal picker path, or fail cleanup. The component neither invents an app
sandbox path nor treats accepted files as executed scripts. Native C++/Qt event
delivery remains uncompiled/unqualified. Pico/iOS picker wiring is separate.
See [the common file protocol](../../native/NORMAL_SCRIPT_FILES.md).

New implementations in the existing candidate-bound Appium entrypoint:

| Operations | Source implementation | Product/device evidence |
| --- | --- | --- |
| `scripts.manager.open/close`, `scripts.load-url`, `scripts.restart/stop` | Normal Tablet/From URL/row input; actual native URL identity; persistent cleanup intent | Host boundary tests only |
| `create.reference.open/close`, `create.cube/update/undo/redo/delete/import` | Normal Create controls, original read-only observer, actual avatar entity IDs and cleanup | Host boundary tests only |
| Existing `places.*`, `snapshot.*` | Existing Phone native navigation and original SNAP-file implementation retained | No new device qualification |
| All `feature.<area>.act/observe/cleanup` | **Not implemented as complete version 2 area adapters** | Never advertised; required capability gates remain red |

For a later Proxmox laboratory candidate only, opt in separately with
`OVERTE_PHONE_NORMAL_SCRIPTS=1` and/or `OVERTE_PHONE_NORMAL_CREATE=1` in the
private execution environment. The original candidate arguments, installed-APK
hash binding, controlled app-private command/probe configuration and explicit
target remain mandatory. No private target files were changed. An invalid opt-in
or an unbound/wrong product is rejected. The new probe producer must be present
in the actual later APK; enabling flags against an old candidate fails before
feature input. The adapter never installs or builds a replacement implicitly.

The read-only command is correlated to a fresh random request ID. It returns
original service/entity reads once, with a source sequence and actual capture
time; no recurring entity-query overhead is added to unrelated test suites.
The adapter checks PID+start ticks, foreground, original Appium session and
generation, target fingerprint and actual installed bytes around operations.

Implementation details and exact bounds are in
[normal scripts](../NORMAL_SCRIPT_MANAGER.md) and [normal Create](../NORMAL_CREATE.md).
Phone-owned UI bindings are `overte_phone_script_ui.py` and
`overte_phone_create_ui.py`; Main owns only the reusable flow/observation code.
No primary action uses a direct entity/script service mutation. UI ACKs remain
input receipts; the existing shared journeys independently inspect real effects.
Create Name/Color/Dimensions edits use actual W3C keyboard actions (Select All,
ordinary ASCII keys, modifier release and native field readback), because
`NativeCreate.qml` accumulates changes on Qt `textEdited`. Accessibility set-value
alone would not establish those edit events. Actual UiAutomator2/Qt key delivery
and off-screen field reachability still require later physical qualification.

Cleanup first tries normal owned entity/source cleanup, then the original
adapter-wide app/session teardown. If candidate/process continuity is lost, an
ignored deletion/stop remains, or an import has unresolved native completion,
cleanup fails and retains ownership state. A stopped process alone does not
establish removal of persisted avatar entities or saved Running Scripts.

The full fourteen-area v1 adapter is concretely blocked by missing complete
product observers, native lifecycle counters, original world-render target
capture, external real peer/account/domain fixtures, and delivery of original
record/share/upload bytes. See the common fourteen-area audit. In particular,
the source-reviewed From URL action loads directly, without the consent
cancel/reject flow required by the full scripts feature scenario; this must not
be disguised by a synthetic dialog in the adapter.

Hardware-free checks (run from this worktree):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s android/phone/tests/device -p test_feature_adapters.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s android/phone/tests/device -p test_installed_identity.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/device/self_tests -p 'test_normal*py'
```

The first test is also registered in `phone-e2e-runtime-regressions.py`'s existing
mandatory `COMMON_HOST_CHECKS`; no new CI workflow was introduced. These tests
substitute only native W3C/ADB/time boundaries and synthetic candidate bytes.
They prove control logic and failure handling, never Overte feature success or
Phone acceptance. All physical qualification remains pending on Proxmox.
