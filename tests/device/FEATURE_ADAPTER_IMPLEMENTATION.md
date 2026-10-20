# Local adapter implementation and remaining native prerequisites

The fourteen-area **common test logic exists**. This adapter phase is **partially
implemented**: Phone has new ordinary Create/script foundation bindings; Pico
has a candidate-bound original-observation backend; iOS has an original-read
component behind its unchanged installed-code gate. **No complete new
`feature.<area>.act/observe/cleanup` triple is advertised by these three platform bindings.**
All fourteen complete version 9 adapters remain missing, and all device qualification
remains unperformed. An ignored input, an input ACK or a host simulation must
not be reported as feature success.

Continuation authorization: the user explicitly approved E2E-only native
instrumentation, with no functional product changes. The first native packet
adds a default-off build option, actual lifecycle notification counters and
original evaluated animation/pose observations, with labelled native
render/audio/account settings reads. Platform transports are being connected
in Phone, Pico, iOS order. See [the native source contract](native/README.md).
The initial source-only readers and full-area adapter status remain distinct;
these new sources do not by themselves complete any version 8 triple.
The [source compatibility audit](FEATURE_SOURCE_COMPATIBILITY.md) also records
draft common workflow assumptions that must be corrected before area activation.

## Local branches and ownership

| Owner | Local branch | Worktree basename | Product/source base |
| --- | --- | --- | --- |
| Main/common | `test/main/shared-feature-journeys-20261019` | `overte-shared-feature-journeys-20261019` | `7636452f2124029798948aafae70ecff5c5fa7d0` |
| Android Phone | `test/android-phone/shared-feature-adapters-20261019` | `overte-phone-feature-adapters-20261019` | `718d069add` |
| Pico 4 | `test/android-pico/shared-feature-adapters-20261019` | `overte-pico-feature-adapters-20261019` | `c5bf8ac17b` |
| iOS | `test/ios/shared-feature-adapters-20261019` | `overte-ios-feature-adapters-20261019` | `864f8b79a4` |

Every branch name was checked with the reviewed branch-policy helper before
creation. Product branches contain local parent-to-child merges of common work,
not sibling product histories. Main owns reusable flows, private ownership and
read-only probe/fixture contracts. Concrete Phone/Pico/iOS bindings stay in their
own product branches. Existing reference/frozen worktrees were not changed.
These are local review branches for later composition with the parity changes;
no protected branch, upstream, push, PR, global CI workflow or device-lab service
was changed.

## Implemented source packets

Phone's existing candidate-bound Appium wrapper now implements all five
`scripts.*` foundation operations and all eight `create.*` foundation operations.
Inputs use ordinary native Tablet, source dialogs, exact script rows, Create
fields, history/import/delete controls and normal keyboard events for Qt
`textEdited` fields. Original installed-APK byte checks, PID/start ticks,
foreground, native session/generation and private target binding remain in
force. Persistent ownership precedes input. Actual service rows/native UUIDs
identify input targets; the existing independent common journeys still judge
the real effects. Cleanup retains unresolved work instead of claiming success.

The shared probe's new **read-only** command is
`normal-feature-observe`, with exactly `schemaVersion:1`, fresh `commandId` and
`includeAvatarEntities:boolean`. The Android private control channel takes a
32-hex command ID; the existing owned HTTP fixture takes `ios-<32hex>`. Both
reach the same source-owned sampler. It writes original complete service rows,
optional actual avatar-owned UUID/name/type rows, probe instance, source sequence,
request ID and capture time. Reads cannot load/stop a script or create/edit/delete
an entity. Queries run only for a new explicit request; unrelated suites acquire
no recurring full-entity-query overhead.

Pico's internal reader joins that original diagnostic to the original candidate
verifier, installed bytes and live OpenXR/debug process. iOS's internal native
component joins actual HTTP request/AFC bytes to its live foreground bundle/PID.
Neither reader is a complete feature observer or a peer. The canonical iOS
adapter explicitly continues rejecting this reader, sessions and all invocations
with `OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE`.

Detailed platform packets are documented in each owning branch under
`tests/device/adapters/<android-phone|pico4|ios>/FEATURE_ADAPTER_STATUS.md`.
Reusable protocol/bounds/cleanup details are in
[normal scripts](adapters/NORMAL_SCRIPT_MANAGER.md) and
[normal Create](adapters/NORMAL_CREATE.md).

The shared [current migration](feature_journeys/CONTRACT_MIGRATION.md)
retains the corrected client Script import to the existing file-bundle picker. URL Script
foundations remain narrower. All three source branches now connect the normal
local file-bundle picker with actual control/model tokens and add exclusive
private Script fixture staging, original-byte readback and persisted file
cleanup intent. Missing/changed files and unresolved cleanup fail. The actual
companion/advancing-effect/observer joins and verified restart handoff remain
open. See [file controls](native/NORMAL_SCRIPT_FILES.md) and
[fixture storage](native/SCRIPT_FIXTURE_STORAGE.md). The [original memory-preview PCM source](native/RECORDED_PREVIEW_EVIDENCE.md)
now has internal transports on all three platform branches. It retains actual
capture/sink bytes, native cycles/events and observed cleanup; it is not a full
audio adapter or independent acoustic proof. The new
[atomic Audio cycle/history source](native/RECORDED_PREVIEW_HISTORY.md) additionally
joins original events and live buffer counters on the audio thread. Its typed
read requirement refuses older narrow producers and preserves historical frame
formats/times; it has separate internal normal Audio inputs on all three platform branches, but no complete ownership/acoustic evidence coordinator.

The [controlled account protocol](feature_journeys/ACCOUNT_PROVIDER.md) now
implements actual HTTPS password/refresh grants, owned Bearer profile access,
delayed responses and authority/handler cleanup in the existing fixture server.
Authentication registration refuses missing/plaintext providers. It does not
implement native login controls, client pending/error measurements, native
trust/origin setup or a complete actor/coordinator; no capability is enabled.

## Fourteen-area source audit

All rows below mean: **test logic present; full version 9 adapter missing; devices
untested**. Existing/new foundations are narrower implementation scopes.

| Area | Phone foundation / new source work | Pico foundation / new source work | iOS foundation / new source work | Additional full-area requirements not available through the current adapters |
| --- | --- | --- | --- | --- |
| Worlds/navigation | Existing normal Go To/history retained | Existing real VR Go To/history retained | Existing native component navigation retained; bound execution blocked | Actual bookmark CRUD/persistence, directory/search/failure state and independent arrival/directory actor |
| Authentication | No new login capability | No new login capability | No new login capability; installed-code gate applies | Controlled HTTPS account/profile fixture now exists; passive native pending/token/reply history now exists; explicit-origin protected-probe and owned origin-file factories now exist; normal login input recipes/private credential carriers now exist internally; native trust/setup, logout/restart/whole-run ownership and independent actor joins remain missing |
| Avatar/people | Existing replication foundations retained | Existing replication foundations retained | Existing component peer/replication code retained | Actual avatar chooser/bookmark/scale/wearable readers, mutual contact consent peer and original visible avatar effects |
| Create | **New** ordinary cube/edit/history/delete/JSON import + observer/source cleanup | **New** original avatar-owned native ID reader; VR input controls missing | **New** original avatar-owned native ID reader component; bound execution blocked | Normal glTF/OBJ Model URL creation with companions, real entity-JSON file picker/staging, voxel stroke/settled data, exact-slot texture/render/export effects and real domain rez-denial/retry actor |
| Emotes | Evaluated Rig/clip/pose and immutable native call/frame history | Same candidate-bound history reader | Same original native history component; canonical binding blocked | Full source-profile/normal-input/history/peer/image coordinator, measured completion/early-restoration timing and actual Sit identities; the original tablet Sit end-frame concern remains unresolved |
| World web | Existing web-video foundations retained | Existing web-video foundations retained | Existing component web/video code retained | Real focused world-Web text/key route, actual page/bridge/origin/error state and independent message receipts/navigation/resume |
| Tablet web | Existing Tablet/video foundations retained | Existing VR Tablet/video foundations retained | Existing native Tablet component retained | Real browser/inline-app focus, bridge-origin isolation, page/history/error readers and independent effects |
| Graphics | Ordinary token-bound immediate controls plus original settings and internal owned mono-frame capture | Ordinary actual VR controls plus original settings; mono-only image source refuses Pico stereo | Ordinary native component controls/mono image transport; canonical binding blocked | Full preference/scene/camera/restart owner, actual Haze/Mirror pass observers and independent effects; stereo and unsupported backend sources remain unavailable |
| Audio | New bound original memory-preview capture/sink PCM source | New bound original memory-preview capture/sink PCM source | New original memory-preview HTTP/AFC component | Normal Audio token/cycle inputs now connected internally on all three; full ownership, permission/mute/resume joins, independent acoustic capture and real peer; native accepted-write bytes do not prove audible output |
| Chat | New candidate-bound native reception cache/owner and local/network distinction | Same new candidate/OpenXR-bound reception/cache owner | Same HTTP/AFC component; canonical installed-code binding blocked | Actual normal Local/Domain controls, draft/page/persisted histories, independently bound remote peer ledger, owned MessagesMixer remove/restore and whole-run cleanup. Native self/local echo never proves peer delivery. |
| Snapshots | Existing original normal SNAP capture/file contract retained | Existing original normal SNAP capture/file contract retained | Existing native SNAP component retained; bound execution blocked | Actual export/share permission path, original share/upload bytes/completion/cancel/failure receipts and controlled external sink; private capture-file presence alone is insufficient |
| Scripts | Ordinary From URL/row foundations; normal file-bundle picker; private staged originals and persisted file ownership | Same normal Script/VR file-bundle controls and staged-original ownership under candidate/OpenXR guards | Same native UIKit/Qt component and staged originals; bound execution blocked | Persist picker/engine ownership, join actual loaded companions and advancing entity effects to an independent observer, and implement verified restart ownership handoff. Script import itself has no consent modal; entity-script consent remains in its existing foundation |
| Assets | No new asset-browser capability | No new asset-browser capability | No new asset-browser capability | Native mapping/path row identity and import/rename/delete/bake inputs, actual complete ATP/companion/bake state, original resolved bytes and real domain write-permission actor |
| Lifecycle/input | Existing process/input foundations retained | Existing process/OpenXR foundations retained | Existing foreground PID/native input component retained | Actual native lifecycle notification counters, feature-editor context generations/focus, retired input rejection and independent ownership/displacement/resume observations |

Common blockers affecting the full triples:

* The witness HTTP journal accepts independently measured actor facts. It is not
  an account backend, domain administrator, external upload/share service or
  second Overte client. No such real measuring actor has been implemented by
  relabelling fixture simulation or by forwarding expectations to the adapter.
* The version 8 `lifecycle` counters must come from actual native lifecycle events;
  request counts cannot fill them. The continuation's native packet implements
  that source, but the full-area observer/cleanup joins remain to be completed.
* Fullscreen panels can occlude the current in-world challenge/feature subject.
  The native main-mono GL tone-map capture hook and original-memory/chunk reader
  now exist as uncompiled E2E instrumentation. Private platform transport/ownership/receipt cleanup are connected as
  internal components, but scene/view/pass and full feature coordinators remain
  open; no qualified original world image exists for these feature suites.
  Stereo/Vulkan fail closed. Compositing a marker into a screenshot is forbidden.
* Original recording/export/share/upload bytes and independent peer effects
  cannot be inferred from a UI ACK, a selected filename, a prior file or input
  state. Existing narrow capture/file/voice contracts do not establish all of
  these additional results.
* Pico's E2E `PicoE2eNavigationUi::controlId/apply` and
  `PicoE2eTabletBridge::CONTROL_IDS` have closed native control sets for existing
  navigation/SNAP/settings, normal Script URL/rows and the new source-bound
  file-bundle controls. Create/Assets and their current row/dialog tokens remain
  missing. Its Android accessibility bridge's OffscreenUi root does
  not itself prove export of the real VR Tablet root. Phone input recipes cannot
  be substituted for that native VR route.
* iOS's canonical installed-code association is explicitly unavailable. Its
  native component now also exports normal Script URL/row tokens alongside
  HUD/address/Places/SNAP, but the full additional feature inputs are missing. The prerequisite
  cannot be replaced by an archive hash or self-reported native diagnostic.

Resolving these needs additional reviewed native automation/observation seams
and real controlled actor/service implementations. Native E2E-only observation
seams are now being added under the explicit continuation authorization;
functional product changes remain outside scope.
Each blocked area was audited and the next area/platform processed; no missing
area has been silently marked complete.

## Verification and later handoff

The existing quick common Python selection includes the new flow/counterexample
tests. Phone's new tests are in the existing `COMMON_HOST_CHECKS` of
`phone-e2e-runtime-regressions.py`; Pico's new `feature-observation` group is in
its existing suite/coverage matrix; iOS's new test is discovered by its existing
Python self-test group. No alternate test system or global CI workflow was added.

Counterexamples include ignored text/stop/delete/create input, unlabelled partial
creation, duplicate/native foreign IDs, replaced candidates, process/probe/session
changes, old/foreign request IDs, nonadvancing or incomplete source observations,
original-file transfer errors, unresolved imports and retained cleanup intent.
The actual shared JavaScript producer and Android private-channel dispatch are
executed against explicit native boundaries; one owned loopback HTTP server
checks iOS redirect refusal. These prove adapter/test control logic only.

No devices, installs, application builds, Jenkins jobs or global lab services were
accessed. An initial expanded iOS host selection accidentally compiled two
pre-existing native Snapshot reader harnesses through transitive `setUpClass`
calls. This violated the requested no-build scope. Their temporary build
directories were cleaned by the original teardown; the initial receipt is
retained as a mixed host run, not a no-build result. The corrected selection
excludes both native Snapshot classes and the acoustic native compile case,
and rejects compiler launches before execution. See the
[validation record](FEATURE_ADAPTER_VALIDATION.md).
Qualification of actual keyboard delivery,
visible/scrollable controls, original pixels/PCM/files and product behavior is
still pending. Later hardware work must use the Proxmox Jenkins laboratory via
the official CLI; no workstation device-lab fallback is authorized.

The shared [normal Audio input component](native/NORMAL_AUDIO_CONTROLS.md) now
has a token/cycle guarded ordinary-input recipe and sixteen independent host
counterexample cases. It is an internal prerequisite, not a full Audio adapter;
native delivery and acoustic/cleanup coordination remain unqualified.

The [submitted-code source](native/SCRIPT_CODE_IDENTITY.md) identifies actual
ScriptEngine input, with immutable code-unit hashes and reviewed Emote profiles.
It selects source semantics only and does not complete Emote adapters. The
original generic Sit end-frame source concern remains explicitly unresolved.

The shared [immediate Graphics input component](native/NORMAL_GRAPHICS_CONTROLS.md)
now has native original-widget metadata/point calculations and a token guarded
recipe, with fourteen host counterexample cases. It observes actual above/below
viewport directions and original Qt/native setting coherence. Internal Graphics transports are now connected on the three platform branches.
Original render/pass evidence and full ownership remain open;
no complete Graphics capability is advertised and native source is uncompiled.

The [world-render acquisition packet](native/WORLD_RENDER_ACQUISITION.md) adds an
E2E-only GL readback plus actual pre-HUD main-mono callback, original chunk
transport, persistent ownership and separate native/file cleanup. The private
factories are connected in Phone, Pico and the unbound iOS component; 48 common
reader/ownership cases cover failure boundaries. The executing backend and
original GL creation context must match actual GPU objects. Native code remains
uncompiled. Pico stereo and Vulkan/unknown backends provide no image; no default
buffer, UI composite or guessed eye substitutes. Scene/camera/pass and complete
feature coordinators remain missing. No full capability is activated.

The [passive native account packet](native/ACCOUNT_OBSERVATION.md) replaces an
instrumentation read that could itself refresh credentials. Actual native
pending/context flags and bounded original current reply/signal history are now
available to the existing internal reader with a mandatory source option.
This does not establish remote protected access, native UI success or a full
Authentication coordinator. Native source remains uncompiled.

The [native protected-profile component](native/ACCOUNT_PROTECTED_PROBE.md) adds
one actual current-credential HTTPS GET, source/context-fenced original response
metadata and separate reply/body/authority cleanup. Private persisted intent and
actual provider-proof/passive-account joins have strict host readers. This remains
uncompiled source; native origin provisioning, normal login, complete actor
composition and Authentication activation remain open.

The common [account-origin file lease](native/ACCOUNT_ORIGIN_OWNERSHIP.md) now
adds exclusive native fixture configuration, original inode/write provenance and
retirement before independently observed file cleanup. It can clean its own
partial writes but refuses copied/modified originals. It does not set product
endpoints or trust; platform factory/cleanup integration is still the next step.
Native code remains uncompiled and no full Authentication triple is enabled.

The origin-file factories are now connected in Phone/Pico and the unbound iOS
component, including actual Test-instance acquisition and their existing process/
artifact/session guards. Adapter cleanup drains network probes then owned
configuration before base teardown and preserves unresolved ownership. Native
trust/ordinary endpoint setup, login/cancel/UI/error and verified restart/actor
composition still gate Authentication activation; all native code is uncompiled.

The [native Create control contract v1](native/NORMAL_CREATE_CONTROLS.md) and
`TokenCreateUI` now provide original-reference-bound normal field, ComboBox,
tab/entity selection and scrollbar input. Fifteen synthetic-boundary cases
compose the existing Create owner/observer and reject ignored effects, context
replacement and unresolved cleanup. The full local no-build common selection
passes 645 host cases (three native compiler checks explicitly excluded).
Native Qt source remains uncompiled; platform adoption and the complete v9
model/file/export/PolyVox/permission actor composition remain pending.

The separate platform branches now connect the shared Create input recipe:
Phone `e88825d4d0` / `46ae6d6461`, Pico `cc6ea0224e` / `b70f01e528`, iOS
`83e7756b2c`. The [handoff](FEATURE_ADAPTER_HANDOFF.md#original-create-input-components-v1)
records exact routes, host checks and remaining obligations. This closes a
normal-input prerequisite on all three branches, not a complete feature area.
All fourteen complete area triples still require adapters and physical checks.

Snapshot contract v9 now corrects private capture versus real OS Save, actual
pending/cancel history, Photos/MediaStore/document-picker source profiles,
system sheets, original saved/receiver/upload bytes and cleanup restoration.
The [source-specific handoff](feature_journeys/SNAPSHOT_SOURCE.md) documents the
short normal pre-render cancellation window and remaining actual OS/actor
qualification. All **65** common journey cases and the complete permitted
**654**-case no-build common selection pass, with no failures/skips/errors or
compiler attempts; three existing native compiler checks remain explicitly
excluded. The existing original Snapshot JS suite now has eleven passing cases.
No complete Snapshot adapter, OS storage/receiver actor or physical result is
claimed by these synthetic-boundary checks.

The [independent Chat receiver v1](native/INDEPENDENT_CHAT_RECEIVER.md) now pins
actual separately read primary/peer source identities and mixer history and
extracts remote reception order without accepting self/local/foreign echoes.
Its real private journals retain partial cleanup intent. Nine new host cases
and the existing 21 receive-source cases pass; the complete permitted common
selection passes 663 cases. An E2E-only script-callable native source/Assignment
Client opt-in is present, but uncompiled. An authenticated/private running actor
transport, peer/mixer stimuli, primary UI/storage and complete area joins are
still required; no complete Chat capability is enabled.
