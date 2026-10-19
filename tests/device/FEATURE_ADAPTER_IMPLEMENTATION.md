# Local adapter implementation and remaining native prerequisites

The fourteen-area **common test logic exists**. This adapter phase is **partially
implemented**: Phone has new ordinary Create/script foundation bindings; Pico
has a candidate-bound original-observation backend; iOS has an original-read
component behind its unchanged installed-code gate. **No complete new
`feature.<area>.act/observe/cleanup` triple is advertised by these three platform bindings.**
All fourteen complete version 2 adapters remain missing, and all device qualification
remains unperformed. An ignored input, an input ACK or a host simulation must
not be reported as feature success.

Continuation authorization: the user explicitly approved E2E-only native
instrumentation, with no functional product changes. The first native packet
adds a default-off build option, actual lifecycle notification counters and
original evaluated animation/pose observations, with labelled native
render/audio/account settings reads. Platform transports are being connected
in Phone, Pico, iOS order. See [the native source contract](native/README.md).
The initial source-only readers and full-area adapter status remain distinct;
these new sources do not by themselves complete any v1 triple.
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

The shared [version 2 migration](feature_journeys/CONTRACT_MIGRATION.md)
corrects client Script import to the existing file-bundle picker. URL Script
foundations remain narrower; the local picker/actual companion observer joins
are still open. The [original memory-preview PCM source](native/RECORDED_PREVIEW_EVIDENCE.md)
now has internal transports on all three platform branches. It retains actual
capture/sink bytes, native cycles/events and observed cleanup; it is not a full
audio adapter or independent acoustic proof.

## Fourteen-area source audit

All rows below mean: **test logic present; full v1 adapter missing; devices
untested**. Existing/new foundations are narrower implementation scopes.

| Area | Phone foundation / new source work | Pico foundation / new source work | iOS foundation / new source work | Additional full-area requirements not available through the current adapters |
| --- | --- | --- | --- | --- |
| Worlds/navigation | Existing normal Go To/history retained | Existing real VR Go To/history retained | Existing native component navigation retained; bound execution blocked | Actual bookmark CRUD/persistence, directory/search/failure state and independent arrival/directory actor |
| Authentication | No new login capability | No new login capability | No new login capability; installed-code gate applies | Controlled real account/protected endpoint, delayed-response release/revocation, actual principal/pending/error observations |
| Avatar/people | Existing replication foundations retained | Existing replication foundations retained | Existing component peer/replication code retained | Actual avatar chooser/bookmark/scale/wearable readers, mutual contact consent peer and original visible avatar effects |
| Create | **New** ordinary cube/edit/history/delete/JSON import + observer/source cleanup | **New** original avatar-owned native ID reader; VR input controls missing | **New** original avatar-owned native ID reader component; bound execution blocked | glTF/OBJ local picker + companions, voxel stroke/settled data, texture/render effect, original export bytes and real domain rez-denial actor |
| Emotes | No complete animation reader | No complete animation reader | No complete animation reader | Actual active animation/Sit identity and advancing pose, override/cancel/resume plus independently replicated pose/image evidence; button text cannot substitute |
| World web | Existing web-video foundations retained | Existing web-video foundations retained | Existing component web/video code retained | Real focused world-Web text/key route, actual page/bridge/origin/error state and independent message receipts/navigation/resume |
| Tablet web | Existing Tablet/video foundations retained | Existing VR Tablet/video foundations retained | Existing native Tablet component retained | Real browser/inline-app focus, bridge-origin isolation, page/history/error readers and independent effects |
| Graphics | Existing render-health foundation retained | Existing native renderer observer retained | Existing native renderer component retained | Ordinary preset/cancel/apply/mirror inputs and actual render-scale/shadow-pass/persistence readers; original current scene pixels under fullscreen panels |
| Audio | Existing voice/permission foundations retained | Existing voice/permission/native capture foundations retained | Existing native audio/permission components retained | Original microphone recording file and preview-output PCM, native permission failure/cancel counters, mute/resume silence and real independent audio peer |
| Chat | Existing text-input foundation retained | Existing native text-input foundation retained | Existing native text-input component retained | Actual draft/history/filter/offline state, meaningful Back/focus ownership and real receiving/sending peer with exactly-once retry receipts |
| Snapshots | Existing original normal SNAP capture/file contract retained | Existing original normal SNAP capture/file contract retained | Existing native SNAP component retained; bound execution blocked | Actual export/share permission path, original share/upload bytes/completion/cancel/failure receipts and controlled external sink; private capture-file presence alone is insufficient |
| Scripts | **New** ordinary From URL/load/restart/stop and independent execution/silence checks | **New** original actual running-source reader; VR script/dialog controls missing | **New** original running-source reader component; bound execution blocked | Local file/folder picker with real companions, source-bound consent cancel/reject/accept and application-restart durability. Current From URL source entry loads directly without that consent path |
| Assets | No new asset-browser capability | No new asset-browser capability | No new asset-browser capability | Native mapping/path row identity and import/rename/delete/bake inputs, actual complete ATP/companion/bake state, original resolved bytes and real domain write-permission actor |
| Lifecycle/input | Existing process/input foundations retained | Existing process/OpenXR foundations retained | Existing foreground PID/native input component retained | Actual native lifecycle notification counters, feature-editor context generations/focus, retired input rejection and independent ownership/displacement/resume observations |

Common blockers affecting the full triples:

* The witness HTTP journal accepts independently measured actor facts. It is not
  an account backend, domain administrator, external upload/share service or
  second Overte client. No such real measuring actor has been implemented by
  relabelling fixture simulation or by forwarding expectations to the adapter.
* The v1 `lifecycle` counters must come from actual native lifecycle events;
  request counts cannot fill them. The continuation's native packet implements
  that source, but the full-area observer/cleanup joins remain to be completed.
* Fullscreen panels can occlude the current in-world challenge/feature subject.
  The required original world-render-target capture with actual acquisition
  provenance is not available through these feature bindings. Compositing or
  painting a marker into a screenshot is forbidden.
* Original recording/export/share/upload bytes and independent peer effects
  cannot be inferred from a UI ACK, a selected filename, a prior file or input
  state. Existing narrow capture/file/voice contracts do not establish all of
  these additional results.
* Pico's E2E `PicoE2eNavigationUi::controlId/apply` and
  `PicoE2eTabletBridge::CONTROL_IDS` have closed native control sets for existing
  navigation/SNAP/settings. Create/scripts/assets and their current row/dialog
  tokens are missing. Its Android accessibility bridge's OffscreenUi root does
  not itself prove export of the real VR Tablet root. Phone input recipes cannot
  be substituted for that native VR route.
* iOS's canonical installed-code association is explicitly unavailable. Its
  native input component additionally exports only HUD/address/Places/SNAP
  control tokens, not the additional complete feature inputs. The prerequisite
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
