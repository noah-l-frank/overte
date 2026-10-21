# iOS source coverage and executable adapter handoff, 2026-10-21

**Scripts and Authentication are source-complete and host-tested; twelve areas remain partial.**
All fourteen shared v16 journeys exist. These two areas have complete iOS
input/observation/cleanup coordinators. Native compilation is unverified and
devices are untested. Host results do not represent product acceptance,
installation, build or laboratory execution.

The canonical physical source binding and explicit lost-launch recovery have
host-tested implementations. The native byte observer and SDK plugin remain
uninstalled/uncompiled and unqualified here. See the [Script handoff](SCRIPT_FEATURE.md)
and [Authentication handoff](AUTHENTICATION_FEATURE_SOURCES.md).

## Source and integration boundaries

The new branch starts at iOS `f85409d3b4b9c0c1f292b2bb5bbd903c5ff88347`,
including the consistently captured relevant WIP recorded in
[the provenance report](LOCAL_IMPLEMENTATION_20261021.md). The original iOS
worktree is read-only. Shared foundations `7636452f2124029798948aafae70ecff5c5fa7d0`
and `0a52254c0580a1fd28626d23bead55015500c0a7` are ancestors.

Phone comparison is frozen at `fe4684bf46585088370b3a328a738f147e670b97`.
Only Scripts, Authentication and Graphics are complete source-level Phone areas
there. Phone Emote controls/source/Rig helpers do not constitute a fourth area.
The current moving Phone worktree/branch is not an integration source.
Pico's committed status was inspected separately at
`de7587093406a49573189e626bd350a12cb3d31f`; no Pico commits or WIP were imported.
Its component factories and full-area gaps were kept distinct. Neither status
qualifies iOS inputs, installed bytes or measurements.

The historical JSON coverage summary and frozen render/configuration worktree
are references only. Current adapter/native/product sources and the version-16
inventory determine this matrix. No reference source, branch, evidence or
progress record was changed.

## Common operation and evidence obligations

All rows retain `catalog -> OverteSession -> feature.<area> operation -> target`.
The authoritative closed inputs/fields are
[adapter-contract.v16.json](../feature_journeys/adapter-contract.v16.json), generated
by the existing [inventory](../feature_journeys/inventory.py) from
[scenarios](../feature_journeys/scenarios.py). Foundation modules are declared
by `FOUNDATIONS`; each selected suite includes its mandatory capability gate.
There is no alternate reducer or verdict path.

Each completed area must supply **all** `act`, `observe`, `cleanup` operations:
ordinary inputs under durable one-send ownership; newly acquired original
product observations; repeated cleanup followed by independent stable absence.
Inputs/ACKs and staged fixture bytes are never observations. The existing
20-second/81-read checkpoint deadline, 60-second operation ceiling, 250-ms poll,
1.5-second sample freshness, 0.5-second positive stability and three-second
negative/cleanup windows remain. Native original epochs stay native; host
acquisition metadata and public aligned sample envelopes must remain separate.

The independent actor must acquire its own originals and publish through its
own private credential. It cannot copy primary normalized results. The new
adapter-only reader sees input/provider/phase information and no actor facts;
its credential cannot activate, register, publish, revoke or retire runs.
Images are original native-screen or supported original world-target PNGs with
actual challenge and feature pixels. Audio is original instrumented input plus
an independent real output/peer capture where required. Files come from actual
native/server/OS/receiver endpoints, not fixture delivery or requested filenames.

## Fourteen-area matrix

Every row remains **compilation unverified; devices untested**. Scripts and
Authentication are source-complete with their unchanged full shared journeys
and independent actor regressions. The other twelve rows remain **logic present;
iOS adapter partial**; their complete triples are still missing. “Partial”
credits only the specifically listed components.

| Area | Existing iOS components and actual product sources | Concrete missing interface/evidence and next implementation packet |
| --- | --- | --- |
| Worlds/navigation | `adapters/normal_navigation.py` drives native Go To/Places history; `adapters/adapter.py::_navigation_replies` reads actual reply IDs. Product: `scripts/system/places/places.js`, `interface/resources/qml/hifi/tablet/TabletAddressDialog.qml`. | No original-token bookmark CRUD/search/modal reader or durable whole-journey owner. Add original Places model/bookmark/settings and modal identities to the gated native survey, then join the current HTTP response-ID reader to actual arrival and independent directory/arrival observations. |
| Authentication | **Source-complete, host-tested.** Canonical full-candidate runtime, original Login/Menu tokens, private AFC credentials, measured preference restoration, separate actor/server proof, delayed reply consumer retirement, three restarts and durable cleanup/finalization. | See [operation/evidence/integration handoff](AUTHENTICATION_FEATURE_SOURCES.md). The unchanged seventeen-step journey passes with a real local HTTPS provider and synthetic iOS SDK/native sources. Requires the explicit dedicated HTTPS origin and existing typed/empty account preferences. Compilation and device qualification remain unexecuted. |
| Avatar/contacts | Existing collaboration/replication foundation and original avatar-entity reads. Product: `scripts/system/avatarapp.js`, avatar model/Rig and account connections. | No normal avatar URL/bookmark/scale/wearable/contact-consent control survey or complete remote contact actor. Instrument actual loaded/requested model generations and failure events plus original controls; implement owned Hips attachment IDs, bookmark preservation and mutual peer consent/cancel/reject/removal. |
| Create | `create_controls.py`, `TokenCreateUI` and native original selection/property input; original avatar-entity observations. Product: `scripts/system/create/qml/NativeCreate.qml` and native entity/file services. | No complete Model/texture/JSON-picker/PolyVox/export coordinator, source-owned export bytes or rez-permission actor. Bind existing native file browser for entity JSON and actual export completion, add actual settled voxel/model/texture observations and an independently controlled permission/remote entity actor. |
| Emotes | `FeatureObservation.native_observer()` can read original evaluated Rig/clip/pose/history. Product: `scripts/system/emote.js`, chooser QML and Rig. | No iOS ordinary chooser/reset survey, submitted-code/caller/root join or independent pose/image actor. Inspect and version the iOS Emote source profile first, add normal source-token input, then join actual native override/completion/early restoration and all real Sit variants. Phone's new root/caller/Rig packet requires its full dependency closure; it is not imported as an iOS adapter. |
| Web in the world | Existing world video input/screenshot foundation, `_web_dom`, native `ios/web/IOSWebView.mm`, `IOSWebChannel.cpp` and document epochs. | No source-bound world-surface focus/key recipe or complete native response/document/bridge lifetime ledger. Bind original WK response ID/status, DOM source and actual input focus to independent message receipts; implement normal navigation/Back/404 restoration/resume, foreign attempt and deferred callback retirement. A host GET cannot fill status or document loads. |
| Web in the tablet | Existing tablet/native Web/video components and the same original DOM reader. | In addition to the Web ledger above, the actual tablet browser/inline route, native inline grant/carrier and reconstructed blank resume need input/lifetime ownership. Bind the actual inline source and original revoked callbacks. An HTTP page named inline is not that source. |
| Graphics | Original settings with independent native clocks, iOS native subject v3 with actual orbit/boom, scene-load ledger, ordinary scene/camera and durable preference restoration, generic Graphics/View-menu tokens, completed-frame and Vulkan PNG/chunk/file owners, durable role samples/crossed-phase retirement, background/activation recovery, restart with old-PID death and original ownership transfer, independent role observation/publication, original world/native-screen joins and actual effect-pixel comparators. | The [whole-run coordinator](GRAPHICS_COORDINATION.md) passes all fifteen unchanged shared steps and double cleanup. The [paired finalizer](GRAPHICS_FINALIZATION.md) now has source/host-verified primary and actor world/image/lifetime restoration, one-send final Stop, independent four-clock OS windows and exact archive/CAS metadata retirement, including strict old/new PID histories. Cached pre-exit native holders remain nonzero originals; no native query or fictional zero packet occurs after death. The independent worker now stays through paired finalization, retains hard failure across restart and passes coupled lost-Stop/receipt tests. Version-2 primary configuration, canonical dispatch and durable SDK-only teardown are now present with lost/ignored DELETE, exact candidate/target scope and historical-repeat host tests. The full fifteen-step journey using the actual worker followed by the SDK transaction still requires verification before a complete capability. See [Graphics sources](GRAPHICS_FEATURE.md), [original samples](GRAPHICS_SAMPLES.md), [publication](GRAPHICS_PUBLICATION.md), [restart](GRAPHICS_RESTART.md), [calibration](GRAPHICS_CALIBRATION.md), [resource lifetimes](GRAPHICS_RESOURCE_LIFETIME.md) and [native callback closures](WEB_CLOSURES.md). Native compilation is unverified and devices are untested. |
| Audio | `normal_audio.py`, original recorded-preview history/input/sink PCM and existing microphone-permission/voice components. Product: automatic native recorded-preview cycle. | No full owner joining microphone authorization, ordinary cycle/mute/background cancellation, independent acoustic output/peer and verified idle restoration. Add an iOS OS-authorization observer/normal prompt recipe to this owner and retain actual pre-normalization input separately from acoustic output. Accepted sink-write bytes are not audible-output evidence. |
| Chat | `chat_controls.py`, `_chat_view`, `_chat_capture`, original local/network distinction and shared independent receiver/mixer-control components. Product: armored-chat QML and MessagesClient. | No complete original rendered and persisted Local/Domain history projection, actual UIKit keyboard measurement, remote stimulus/publisher or whole-run mixer/receiver ownership. Join the actual remote source pair to owned original rows and OS focus/keyboard; exercise distant Local rejection and observed no-mixer local echo, then prove no deferred replay for three seconds before explicit retype/resend. |
| Snapshots | `normal_snapshot.py`, `snapshot_files.py`, original SNAP capture/file foundation; `ios/snapshot/IOSSnapshotAdapter.mm` implements real Photos Save and system Share. | No full pending/cancel history acquisition, ordinary 350-ms cancel recipe, Photos saved-original read/remove, actual system-share receiver or authenticated upload/body sink. Add passive owned callbacks/Photos local identifiers and separate receiver originals; bind normal authorization/sheets to exact capture bytes and original completion. Private file presence cannot prove Save or delivery. |
| Scripts | **Source-complete, host-tested.** Canonical full candidate runtime; ordinary picker/cancel/stop/restart/reimport/missing-URL input; five original sources; role-separated durable history and actor publisher; host/native clock join; three-second cleanup and finalization. | See [Script operation/evidence/integration handoff](SCRIPT_FEATURE.md). The unchanged nineteen-step shared journey passes on synthetic iOS SDK boundaries with real temporary files and loopback HTTP. Native compilation and Proxmox device qualification remain unexecuted. |
| Assets | Existing `asset.load`/asset foundation; actual native asset browser/file importer and AssetServer/oven product sources. | No iOS normal Assets/picker token recipe, durable complete bundle staging-retirement or actual mapping/worker/output/permission actor. Add those gated original row/control/selection identities, then join independent server source hashes, companion paths, actual FBX worker and oven outputs, world model and vanished-file picker error. No server/oven is started in this local phase. |
| Lifecycle/input | Existing native lifecycle/normal UIKit-Qt input, `_pending_owner`, original pending Qt callback owner and OS PID continuity. | No complete Create/Chat/Script-filter context generations, normal semantic Back, actual UIKit keyboard and world-input/displacement observer join. Bind actual distinct editor QObject/loader/focus/window and OS keyboard notifications, then bracket the retained stale callback and held-input release with independent actor/position/image observations. Home is not a substitute for Back. |

## Source-specific completion, failure and cleanup

The following are required next packets, not new fictional product behavior:

- **Navigation:** current actual bookmark names/settings across real restart;
  actual empty/unmatched/owned search rows; current address/native modal and
  grounded arrivals. Cancel leaves original storage unchanged. Cleanup removes
  only captured owned bookmark IDs and observes original location/panels.
- **Authentication:** native pending/token/credential-generation and actual
  login/error dialog; independent protected access and provider outstanding
  delayed authority. Closing a dialog does not cancel a native request. Retire
  the old consumer by proven process death before releasing a delayed grant.
  Cleanup logs out normally, drains private input/probe/origin leases, disables
  grants and separately revokes fixture authority; callback/authority absence
  must precede deleting ownership.
- **Avatar:** distinguish advertised URL, actual loaded geometry/fallback and
  current-generation failed load. Scale and wearable effects need real peer
  observations; contact consent needs both actors. Cleanup restores measured
  avatar/scale/bookmarks and removes only the actual recorded wearable/contact.
- **Create:** ordinary URL creation transports all glTF/OBJ companions; texture
  uses actual `checker.png` slot. Export is an original DataVersion-0 tree,
  inspected independently. JSON input has no future texture assignment.
  Cancel/rez-denial/retry and actual no-owned entity/file/panel state are required.
- **Emotes:** original Script caller/range/rate/restore/evaluation events,
  independent current changed pose pixels and peer effects. Measure early
  restoration before nominal end; never assign a requested Sit variant.
  Cleanup restores the measured original override/pose and leaves native history.
- **Both Web areas:** retain actual view/document/source identities, incoming
  Send attempts, accepted bridge dispatch and matching original echoes. Ordinary
  404 is a showable document, not a load error. Restore the actual server resource
  before normal Reload. Cleanup requires destroyed/revoked owned contexts and
  drained deferred callbacks; original histories cannot be reset to hide a leak.
- **Graphics:** actual native initial settings and completed-frame/pass identity,
  current original challenge-bearing pixels and original scene/camera ownership.
  Close/background/restart must retain changed settings; restore-original and
  double cleanup must restore the measured initial preferences/scene/camera and
  prove actual image-buffer/receipt/callback lifetime drainage.
- **Audio:** retain capture/play/drain/completion/cancel history, original frame
  counts and both input/output PCM clocks. Check all twelve challenge symbols,
  duration/clipping and independent quiet negatives. Clean owned evidence,
  observe empty product buffers and use verified restart for initial idle
  history; never invent nonexistent Save/Discard preview controls.
- **Chat:** local/self echo is never remote delivery. Preserve actual message
  ordering/multiplicity and closed-page `channel:none`; independently acquire
  real focus/keyboard and persisted reconstruction. Retire original receiver
  caches/mixer leases only after observed no-owned nodes/messages/callbacks and
  quiet no-replay windows. Do not delete unowned history.
- **Snapshots:** pending cancellation must occur before render submission;
  idle Cancel is invalid. Photos denial retains a valid private capture.
  Independently read original private, Photos-saved, receiver and uploaded PNG
  bytes with their original capture ticket and exact equality. System chooser
  handoff is not delivery. Cancel/failure/retry/resume must preserve correct
  native lifecycle behavior. Cleanup removes only actual run-owned destinations
  after original native operations and callbacks drain; preserve authorization.
- **Scripts:** mobile default-only restart leaves owned execution/companions/
  effects absent; no implied autoload. Reopen/cancel/reimport is separate normal
  input. Actual load-result callback determines missing URL failure, even if a
  later loaded signal exists. Independently observe two advancing effect ticks,
  original consumed modules/code and actual engine/entity absence after Stop.
- **Assets:** preserve original server glTF/OBJ companions through folder rename;
  inspect original unbaked bytes rather than a derivative. FBX baking needs actual
  worker/completion/version/output. Disabled Delete has no invented error;
  vanished selected file requires the real browser error and no upload. Cleanup
  proves absence of owned mappings, original/baked blobs, workers, models,
  staging leases and retained native consumers, preserving shared resources.
- **Lifecycle/input:** Create initial text, Chat draft and Script filter are
  separate actual contexts. Background retains the Chat draft but releases
  actual keyboard/focus. Keep immutable original consumed/discarded input
  counters; stale callback rejection and stationary release must be observed.
  Cleanup cannot reset the counters or relabel old input as current.

## Reconciliation manifest

1. The captured `installed_code.py` WIP is preserved in local commit
   `b38bc9c037`; original patch/file SHA-256 values are in the provenance report.
2. Local `1846d179a4` ports the platform-neutral authorization portion of Phone
   `36534359c189f872c475dc85c177af0521c8e20b`. Exact shared paths: fixture reader,
   server, witness Client, registry/validator, existing quick-test inventory,
   two self-test files and the access handoff. All used dependencies are present
   here. The Script provider is now selected with its dependencies, as recorded
   in [the current Script handoff](SCRIPT_FEATURE.md); Graphics remains outside
   this port.
3. Local `011568ead3` changes iOS ownership writer to v3 with v1/v2 readers and
   connects read-only restart recovery. Shared changes are only the installed-
   code registry entry and validator minimum; preserve their union with Phone/
   Pico additions. Common feature journey stays v16; restart inputs/handoff,
   native byte/process packets and input scopes keep their own versions.
4. The current Script packet extends the installed writer to v4, preserves all
   legacy readers, and adds full candidate restart proof v2. It selects the
   shared Script provider and pure source joins with independent iOS input and
   clocks. The host regression covers all nineteen Script steps and both roles.
   Phone complete coordinators are in `overte_phone_script_*`,
   `overte_phone_authentication*` and `overte_phone_graphics*`. They depend on
   Phone candidate/process/ADB, normal UI/native scene sources, original history
   serialization, locks, source restart and independently credentialed workers.
   They are references for decomposition, not iOS drop-ins. Importing just the
   top-level class or copying Android process/storage/input bindings is invalid.
5. Authentication selects pure decomposition from the same frozen Phone commit,
   with separate iOS environment/UUID/input/AFC/process/clock semantics. Native
   preference observation v2 and secret-free normal clear/Remember controls
   preserve and restore original ordinary form side effects. The shared journey
   remains unchanged. The canonical adapter and independent worker are connected;
   host tests cover all seventeen steps, three restarts, both roles, authority
   retirement and uncertain input without resend.
6. Later Emote root/member/work/caller/Rig sources and original Graphics frame,
   file and callback-lifetime packets form dependency chains. Review their full
   native sampler/probe/parser/registry/self-test closure before selecting them.
   This branch makes no claim that importing a helper completes an area.
7. No Pico commit is selected. Resolve only reviewed pinned shared changes during
   later reconciliation; never read/copy its active WIP into this branch.

No main/protected/sibling integration, remote write or device execution is
performed. Remaining source gaps above are not hidden behind skipped features.
The added iOS admission regression checks every area's existing mandatory gate
against the actual iOS capability producer and requires infrastructure failure
for the missing triples, even when the runner's optional completeness flag is
absent.
