# iOS feature adapter implementation status

Branch: `test/ios/shared-feature-adapters-20261019`.
Product base: `864f8b79a4`, composed with Main's shared journeys/observation
helpers through local parent-to-child merges. Neither Phone nor Pico history
was merged into iOS. No application build, signing, installation, device access or protected
integration was performed.

Continuation: the user has explicitly authorized E2E-only native
instrumentation. The shared default-off native feature source now records real
lifecycle notifications and evaluated clips/poses, alongside labelled native
render/audio/account reads. The iOS component's `_native_feature_observer` uses
the original bounded HTTP/AFC transport and native foreground PID. The
canonical binding explicitly rejects this new method too; it cannot bypass
installed-code verification. The existing `--e2e-test-build` selector enables
the new source option, while normal builds pass it as OFF. No build was run.
The focused observation group now has **21** passing host cases. See the
[native observation contract](../../native/README.md).

The component `_recorded_preview_evidence()` now uses the same original HTTP/AFC
transport for separate native capture/sink PCM files. Hashes, native cycles,
event histories and source times bind the bytes. AFC errors never establish
empty audio or deleted files: release requires a separate fresh native query
of actual file/memory state. Candidate-bound access explicitly remains blocked
with `OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE`; no full audio capability or
hardware playback claim is introduced. See
[the preview source contract](../../native/RECORDED_PREVIEW_EVIDENCE.md).

The internal `_script_execution_observer()` now reads actual engine identities
and CommonJS completion/cache/error history through original HTTP/AFC bytes.
The canonical candidate binding explicitly rejects this method too. The
current shared feature contract is **version 3**, with the actual Script
file-bundle picker flow; no complete area adapter is claimed by these sources.
See [the execution source](../../native/SCRIPT_EXECUTION_OBSERVATION.md).

The Script source extension now additionally carries original local-entity
UUIDs, raw user data, RGB, edit times and persistent native absence tombstones.
`read(...,require_effects=True)` requires its typed version before qualification.
The original HTTP/AFC component preserves stalled counters and original event
times, and a changed native process prevents another request. All **21** source
cases pass, including the new effect extension; the broad no-build selection
passes **247** cases with the same explicit native omissions. The canonical
iOS installed-code gate continues refusing the enclosing reader entirely.
The native source is uncompiled, and full journal/restart/picker/engine cleanup
coordination remains open.

The normal Script component now implements the existing five `scripts.*`
foundation operations through native SCRIPTS/From URL/row controls. Opt in with
`normalScripts:{contractVersion:1,profile:"ios-native-qt-scripts-v1"}` in the
private physical E2E component configuration. The real producer must expose
`featureControlsVersion:1` before any input. Source entry uses focused native
Qt key/IME events; native UIKit widgets activate their original current Qt
controls. Full actual delegate URLs bind row tokens. The adapter validates the
observed token on the same resolved UIKit element before clicking, and reused
source rows retire their UIKit element. This prevents a same-basename foreign
source from inheriting an action during re-resolution.

Private Script ownership explicitly says `NATIVE_UI_COMPONENT_ONLY`, recording
the actual process, Appium generation, target fingerprint and native UI instance
without invented source/artifact hashes. It cannot be adopted as verified
candidate ownership. Cleanup observes Stop/absence before original teardown;
ignored Stop, lost process/session or failed source cleanup retains intent and
fails even if the app has stopped. The canonical installed-code gate still
blocks all invocations and cannot be bypassed through this component.

The Script component now also supplies internal `_script_file_picker()` through
normal UIKit clicks and the original native HTTP/AFC field transport. It uses
`fileControlsVersion:1`, the actual Script file-browser caption/mode/filter,
full delegate URLs, original selected/reviewed files and source-sensitive tokens.
The HUD and tablet walks partition file controls by actual visual/QObject
ownership; a visible file modal masks the covered tablet controls. Native
UIKit objects retire when their original token changes. Folder replacement and
Return target the actual focused editor; primary selection uses normal
Home/Down/Return events with actual model/focus checks, followed by readback.
The closed `select-index` extension carries only an integer 0..31, never a
preferred filename, model assignment or script load command.

**Nineteen** Script component boundary tests pass (eight foundations, six picker and five storage
cases), including ignored row/selector input, actual relative companion review,
foreign UIKit token, missing marker and changed process. The broad no-build
selection passes **247** tests, zero failures/errors/skips and zero compiler
attempts, with the same 20 compiler-dependent tests explicitly omitted. Five
canonical candidate binding tests pass, explicitly rejecting the new private
picker method even after candidate preflight. Native C++/Objective-C++ remains
**uncompiled and device unqualified**. These simulated boundaries prove control
logic only. See [the file control contract](../../native/NORMAL_SCRIPT_FILES.md).

The new internal `_script_files()` joins exclusive native fixture staging to
the same actual native input process/session/fingerprint continuity closure.
It persists explicitly component-only file ownership before Stage, verifies
separately returned original bytes and requires Release plus a separate fresh
absence query. HTTP/AFC transfer bounds remain closed; only this validated
fixture command admits its bounded 49152-byte echo. General cleanup reaches
original teardown and then fails if any persistent file intent remains. Lost
process, ACK-only staging and ignored release are counterexamples. The canonical
binding explicitly refuses this private method too. See
[the storage contract](../../native/SCRIPT_FIXTURE_STORAGE.md).

The full owner still needs persisted open-picker/engine cleanup intent, verified
restart handoff and an advancing actual entity-effect/journal join. A failed
picker input can leave that dialog unresolved for the future owner.
No new `feature.*` capability is advertised. Canonical installed-code association
remains blocked; the private method has an explicit refusal in that binding.

The existing iOS native component now has an internal `_feature_observer` and
`ios/adapters/feature_observation.py` (under `tests/device`). It uses the real
native process observer, the existing owned fixture command endpoint and AFC
Documents `mobile: pullFile` transport. It never sets product state. One closed
read-only request obtains actual `ScriptDiscoveryService` rows and optionally
actual avatar-owned entity IDs from the shared probe.

The reader validates the selected physical iOS component profile, safe bundle/
Documents paths, exact HTTP echo, original bounded base64/JSON bytes, current
request ID, actual advancing source sequence/capture timestamp, unchanged probe
instance and live foreground bundle/PID before and after capture. Redirects are
refused. Missing, partial, stale, foreign, incomplete or oversized documents
cannot become accepted state. Temporary AFC missing-file responses may be
polled within five seconds/51 reads; native errors stay private. Expected values
are never sent or substituted. No `feature.*` capability is advertised.

**Canonical execution remains blocked.**
`tests/device/adapters/ios/binding.py::create_adapter` deliberately omits
`executionIdentity` from descriptions, refuses sessions/invocations and now
explicitly refuses `_feature_observer` too. Its unchanged reason is
`OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE`. The offline candidate/IPA verifier,
bundle ID, PID, prior installation receipt and self-reported probe source cannot
establish the independently reviewed installed-code/signature association.
This new component must never be used to bypass that gate.

Concrete native input blocker after that prerequisite:
`tests/device/ios/adapters/normal_input.py::CONTROLS` and the actual E2E-only
`IOSNormalUiInput` producer currently cover HUD/address, Places/history and SNAP.
The new Script packet extends these with current source rows/dialogs. Create
fields/history/entity selection, assets and other complete feature controls
remain missing. General
UIKit accessibility existence is not proof of the same native controls. The
next packet needs source-reviewed ordinary Qt pointer/IME mappings and actual
control tokens on those live roots, with stale context and cleanup handling.
The new approved read-only instrumentation does not yet add these input controls.

The larger fourteen-area version 3 contracts additionally need native lifecycle event
counters, complete product state readers, an independent real account/domain/
peer actor and original render/PCM/recording/export/share/upload evidence.
All fourteen remain **common test logic present; full adapter missing; devices
untested**. Existing component navigation and Snapshot implementations remain
unchanged and are not installed-code/device acceptance.

Hardware-free checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/device/ios/self_tests -p test_ios_feature_observation.py
PYTHONDONTWRITEBYTECODE=1 python3 ios/tests/appium-native-binding-test.py
```

The nineteen-case Script file is discovered by the existing
`ios/tests/run-tests.sh` Python self-test group. No global workflow was changed.
Tests replace HTTP/AFC/process/time boundaries and use one owned loopback server
to verify redirect refusal. That server is a protocol fixture, not an Appium or
device laboratory. Original binding tests also prove that a successful candidate
preflight still cannot invoke this reader through the bound adapter. These are
adapter control-logic checks only. Future hardware qualification belongs
exclusively to the Proxmox Jenkins lab.

Validation correction: a later broad host selection accidentally compiled the
two pre-existing native Snapshot reader harnesses through their `setUpClass`
helpers. This violated the no-build instruction. Both temporary build roots
were cleaned by the original teardown. The corrected 215-case host-only
selection excludes both native Snapshot classes and the acoustic compiler case;
zero compiler attempts occurred. See `tests/device/FEATURE_ADAPTER_VALIDATION.md`
for the retained initial mixed-run record and exact limits.

The current common Audio contract is version 3: actual automatic memory
capture/play/drain/completion, native phase/history/frame consistency, normal
mute/cancel/background behavior and separate original input/acoustic evidence.
OS permission recovery stays in its existing foundation. Normal Audio input,
cycle projection, acoustic actor and verified restart/cleanup handoff remain
open; the component preview source does not supply them. The common suite
passes 351 no-build cases and the iOS observation group passes 21 cases after
the parent merge. The canonical installed-code gate remains unchanged.
