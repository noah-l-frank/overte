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
**37**. See [the native source contract](../../native/README.md).

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
shared feature contract is **version 3**, with a real client file-bundle picker
flow; these history/URL foundations still do not implement that full area. See
[the execution source](../../native/SCRIPT_EXECUTION_OBSERVATION.md).

The Script source now also requires `effectSourceVersion:1` when the caller
passes `require_effects=True`. Actual native local-entity UUIDs, raw user data,
RGB and original edit timestamps are independent of the loaded engine/require
history. Observed UUIDs remain directly tracked outside the initial discovery
radius; native tombstones, rather than missing name rows, establish absence.
One new candidate-bound wrapper case preserves a stalled real source counter
and rejects changed PID/start before another request. These are source/control
checks; the full picker/engine/effect/journal/restart coordinator remains open.

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

This **does not complete** version 3 Scripts: the owning wrapper still needs
persistent picker/engine cleanup intent, verified restart handoff and
the actual advancing-effect/independent observer join. A failed input may leave
the real dialog open; the future owner must retain intent and cancel it through
the normal picker path, or fail cleanup. The component neither invents an app
sandbox path nor treats accepted files as executed scripts. Native C++/Qt event
delivery remains uncompiled/unqualified. Pico/iOS picker wiring is separate.
See [the common file protocol](../../native/NORMAL_SCRIPT_FILES.md).

`_script_files(selector)` now stages the four exact shared fixture resources
through the same original candidate/PID/start/session-bound private channel.
The E2E-only native source reserves an exclusive private directory, persists its
opaque file owner, and provides a separate original-byte read. The host persists
intent before Stage, verifies every returned original and only retires it after
Release plus a separate fresh absence query. It obtains the actual native file
URI rather than guessing the application sandbox. General cleanup still reaches
process/session teardown, then rejects unresolved file intent. It never deletes
files instead of stopping an active script. Four added wrapper counterexamples
cover original roundtrip, ACK-only Stage, lost installed candidate and unresolved
files after teardown; all **37** focused cases pass. Native filesystem C++ is
uncompiled; these are transport/control simulations only. See
[the storage contract](../../native/SCRIPT_FIXTURE_STORAGE.md).

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

The current common contract is version 3. Its Audio workflow now follows normal
automatic memory capture/play/drain/completion, with real mute/cancel/background
states and independent original input/acoustic bytes. The old manual Save or
Preview commands are rejected. Phone's internal preview sources remain narrower;
normal Audio controls, native cycle/frame projection, acoustic actor and verified
restart/cleanup handoff are not yet a full area adapter. The updated shared
suite has 351 no-build cases; the Phone wrapper now passes 37 cases after the
parent merge. No device qualification is inferred.

The atomic Audio history extension is now connected through the existing native
source reader: `read(...,require_recorded_history=True)` checks real per-cycle
event/format/live-buffer metadata and refuses an older producer. The added Phone
wrapper case preserves terminal recording frames after empty live buffers and
rejects source downgrade. All 37 wrapper cases pass. Native C++ is uncompiled;
normal Audio UI inputs and independent acoustic/journal/restart joins remain
required. See [the history contract](../../native/RECORDED_PREVIEW_HISTORY.md).

The [normal Audio input component](NORMAL_AUDIO_PROTOCOL.md) now connects the
shared token/cycle recipe to the original Phone Qt/probe channel. Seven added
wrapper/probe cases bring the focused group to 44 passing cases. This remains
an internal prerequisite: full-area Audio and acoustic/cleanup coordination are
not advertised or qualified; native source is uncompiled.
