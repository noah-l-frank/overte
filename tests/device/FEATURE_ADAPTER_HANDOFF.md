# Feature adapter handoff, contract v11

The original shared-test packet defined the seams below without iOS, Phone or
Pico product adapter implementations or device results. Subsequent local adapter
packets are tracked separately below. The [machine inventory](feature_journeys/adapter-contract.v11.json) and
[ordered checkpoint source](feature_journeys/scenarios.py) are normative. The
[coverage matrix](FEATURE_COVERAGE.md) identifies the existing module owners.
The separate [adapter implementation audit](FEATURE_ADAPTER_IMPLEMENTATION.md)
tracks subsequent local platform packets and prerequisites. These do not change
the complete v11 contract or grant device acceptance.

## Action and read boundary

For each closed area, advertise all three operations only after implementing
and qualifying their complete v11 contract:

- `feature.<area>.act` accepts exactly `{contractVersion: 11, runId, ticket,
  fixtureUrl, verb, inputs}`. `runId` and `ticket` are fresh 32-character lowercase
  hexadecimal strings. `fixtureUrl` is a credential-free HTTP(S) URL whose exact
  path is `/feature-fixture/v1/runs/<runId>/`. `verb` and `inputs` must match the
  closed inventory, including expanded owned text. Return exactly
  `{"performed": true}` after delivering ordinary input, never a result verdict.
- `feature.<area>.observe` accepts exactly `{contractVersion: 11, runId,
  afterSequence}`. It returns exactly `{schemaVersion: 1, contractVersion: 11,
  runId, sequence, capturedEpochMs, state, artifacts, resources, lifecycle}`.
  `state` has every field declared for that area, measured from current product
  state. Unknown, inaccessible or unsupported observations are errors. Empty
  lists and default values cannot substitute for a failed read.
- `feature.<area>.cleanup` accepts exactly `{contractVersion: 11, runId}` and
  returns exactly `{"performed": true}`. Restore only the captured owned test
  scope. The common test calls it twice and then independently observes the
  initial state, empty owned-resource inventory and three seconds of stable
  secondary observations. Acknowledgment alone cannot establish cleanup.

Use ordinary UI entrypoints, field editing, buttons, permission dialogs and
Back routing for primary-user actions. Never implement actions by directly
setting the observed native properties, animation state, account state or test
verdicts. Controlled secondary-user/server actions are delivered to the owned
fixture actor. The adapter may wait for that actual stimulus; it must not
manufacture the actor's outcome. Only the runner receives assertion policy.
Neither the runner's reader token nor image-policy path is forwarded through
adapter invocation, discovery, description or cleanup environments.

`sequence` identifies a newly collected source sample and must strictly advance
past `afterSequence`; changing a label on cached state is forbidden. Maintain a
per-run order across normal app restarts using the actual new process/source
generation. Capture timestamps use host-aligned epoch milliseconds. Samples
must follow the action barrier, be at most 1.5 seconds old and at most 250 ms
in the future. Source timestamps cannot regress. A successful phase needs at
least three advancing samples spanning 0.5 seconds. Cancellation, denial,
rejection, stopped execution, stale completions and cleanup need three seconds.
The common poll is 250 ms; each state wait has a 20-second deadline and 81-read
ceiling. Adapter subprocesses retain the existing 60-second maximum; return
promptly after input and let the common layer wait for product effects.

`lifecycle` has exactly integer counters `backgrounds`, `activations`, `launches`.
Count actual native application lifecycle notifications, never requested
operations. Background/resume must increment backgrounds and activations once;
restart must increment launches and activations once and replace the separately
observed process identity. Other inputs must not change these counts, except the explicitly declared v9
Snapshot system-UI rows. Those may produce real deactivation/background/activation
notifications: launches and bound PID must stay unchanged, counters must not
regress, and the final observed native counters must settle for the required
window before becoming the next checkpoint's baseline. No input-request counts
are substituted for original lifecycle events. Restart
must preserve only the feature's specified persisted data. No unrelated process
replacement may pass.

`resources` is the current owned-resource inventory, not the requested cleanup
list. Entries use `entity|script|file|panel|input|connection:<public-owned-alias>`.
Aliases contain 1–64 lowercase letters, digits or hyphens. Enumerate actual
owned entities, running scripts, transient files, panels, held inputs and peer
connections. Both baseline and cleanup require an empty inventory. Keep private
native identifiers and original settings in adapter-private storage. The
runner's final adapter-wide cleanup must also retire owned runs after timeout
or process-group termination; do not depend on the module's `finally` executing.

## Original evidence

Each artifact entry has exactly `{kind, name, sequence, capturedEpochMs, ticket}`.
Image entries additionally require `source: "native-screen"|"world-render-target"`,
matching the independently configured policy.
Kinds are `image`, `audio`, `file`; at most one of each may appear. Names are
unique direct filenames under the private module artifact directory, at most
128 characters. Copy original bytes without re-encoding, painting, cropping or
creating a replacement from expected values. Bind the artifact to the actual
sample's sequence and current ticket; its timestamp must be within 1.5 seconds
of that sample. Readers reject symlinks, hardlinks, nonregular files, concurrent
mutation and files larger than 32 MiB. Artifacts stay outside the source tree. The private observation report retains
the public run/ticket, host action barrier and original acquisition metadata
alongside the independently decoded checksum/measurements so provenance can be
reviewed after the run. Journal snapshots do not share mutable source/history
objects.

The runner-only JSON image policy is keyed by area. Include an empty object for
areas with no image requirement; do not omit their area key. An area using image evidence
has `screen: {source: "native-screen"|"world-render-target", marker: [left, top, right, bottom], subject: [...]}`. Snapshots also
has `file` with equivalent regions in the original capture's coordinate space.
Prepare these regions independently for the target's fixed orientation and
resolution. A marker ROI excludes the 4-pixel outer card border and contains all
32×4 cells at at least 128×32 pixels. Subject and marker regions cannot overlap.
The subject region must contain the real feature's rendered content, exclude
unrelated animations and include at least 5% changed pixels where `changed` is
required. Never select a policy region dynamically to make a failed step pass.

For fullscreen panels, use an original world render-target capture if the
controlled card/subject is occluded on the native screen. Record that actual
source; a PNG produced by recompositing the scene is forbidden. The render target
must belong to the same live app/process and current scene. A platform without
this capture seam cannot advertise a complete area contract.

Every image must be a complete original PNG with all 128 current challenge bits.
The feature subject must be nonuniform. Change checks compare actual subject
pixels with the preceding successful feature image (channel difference >25 on
at least 5% of normalized pixels). This supplements semantic and peer
observations; the card alone cannot prove an avatar, browser or render effect.
The controlled actor displays the current card in the owned world/scene. Web
pages independently refresh it from the fixture's public current-ticket route.
Do not paint the marker over a screenshot after capture.

Audio reuses the existing voice detector: all twelve fresh symbols, correct
order/timing, complete duration and low clipping must pass on original PCM.
Negative captures require absence of that challenge and RMS below −55 dBFS.
Use bounded 16-bit mono/stereo WAV captures at 8–48 kHz, including the full
challenge duration. The source fixture is 24 kHz. Record/test-preview output
uses the three-second `recorded-preview-v1` profile and must carry the challenge
from the actual recording-start ticket. The original instrumented input and
independent acoustic output remain distinct, with native cycle/event/byte
provenance retained; acquisition timestamps do not relabel old source samples. A current label on foreign, truncated or
silent PCM cannot pass. Declare exactly which physical input/output or peer
capture point is measured. Product/physical audibility still requires the later
real-path qualification; simulated PCM is test-logic evidence only.

Files are independently decoded. SNAP capture/share retains the original PNG
from the capture ticket, including its original rendered card; fresh screenshots
use the current ticket. Share and upload also require actual receiver counters.
Create exports are original `DataVersion: 0` documents with exactly one owned
Model entity, its exact owned name, model source, unit dimensions and texture
assignment. IDs and unrelated serialization fields may differ. The pinned glTF
image URI produces the actual texture slot `checker.png`; a different key is
rejected even if its value is the requested URL. Geometry and source values
cannot be replaced. Ordinary NEW Model uses the explicit pinned
`gltf-bundle/main.gltf` or `obj-bundle/main.obj` URL under its model-create ticket;
transport the complete relative bundle. Apply the distinct generated `checker.png` from the texture
input ticket. Ordinary creation/import must use the owned name and unit dimensions via
real property fields. The separate local JSON picker uses the controlled
`import_document` input, with explicit actual owned fixture origin and no future
texture assignment; no public expected export resource is served. If a platform's local importer exports a different source
representation, qualify a new explicit contract reader; never rewrite the
original export to satisfy v8. Original source bytes of the selected Assets server mapping, read independently
of any baked/rendered derivative, must match the pinned original glTF bytes exactly and the independent server mapping must bind them to this run.

## Independent fixture observer

The fixture service is a coordinator and resource server. It cannot prove
product behavior by itself. Provision an owned test account/provider, ephemeral
domain/asset server, independent Overte peer, private share/upload sink, synthetic
microphone stimulus and capture transport as applicable. No public account,
public directory, real contact, personal recording or existing mapping is used.
The account aliases `owned`, `invalid`, `delayed` resolve inside private provider
configuration; passwords/tokens never occur in commands, observations or logs.

Start the coordinator from `feature_journeys/server.py --private-config <path>`.
The file must contain `readerToken`, `actorToken`, `host`, `port`. Use separate
random tokens of at least 32 characters. The actor token belongs only to the
independent observer process; never pass it to the product adapter or runner.
The runner uses `OVERTE_E2E_FEATURE_FIXTURE_URL` (ending `/feature-fixture/v1`),
`OVERTE_E2E_FEATURE_READER_TOKEN`, `OVERTE_E2E_FEATURE_IMAGE_POLICY`. Existing
foundation suites retain their own fixture inputs. Avatar/People, Create, Emotes,
Audio, Chat and Assets require the controlled domain, including its identity and
assignment-owned markers. The shared session enters that domain rather than
loading a serverless world which would disconnect the peer/asset tests. Prepare endpoints using the
existing isolated fixture ownership procedures; this task starts no services
outside short-lived loopback self-tests.

Authenticated routes under `/feature-fixture/v1` are:

| Route | Role | Contract |
| --- | --- | --- |
| `POST /runs` | reader | `{area}` → `{runId}`; maximum 32 live runs |
| `POST /runs/<run>/active` | reader | `{ticket, verb, inputs}`; closed input stimulus only, no expected state; maximum 256 unique tickets |
| `GET /runs/<run>/active` | actor/reader | current run, area, ticket, input stimulus |
| `POST /runs/<run>/samples` | actor only | raw observed sample described below |
| `GET /runs/<run>` | reader/actor | fresh bounded journal snapshot, at most 512 observations |
| `DELETE /runs/<run>` | reader | idempotently retire coordinator state after product cleanup |

Public resources require an unpredictable live run and an issued ticket:
`GET /runs/<run>/tickets/<ticket>/<resource>`. Missing resources return 404.
`GET /runs/<run>/current` exposes only the active card ticket. There are no
adapter-accessible journal publication credentials. The coordinator never logs
request URLs or bodies. Reader failures use fixed diagnostic text.

The observer publishes exactly `{ticket, actor: "owned-observer", actorSequence,
capturedEpochMs, facts}`. It measures the projection listed in `independentFields`
in the inventory, from the independent sources below. Each source sample must
advance its real sequence and remain fresh after the active ticket. The service
adds receive time and journal order. Old tickets, duplicate sequences, stale
samples, unknown actors and unknown/private strings are rejected. The common
layer checks this channel independently of product reads. There is no `passed`,
`expected`, `success` or assertion-policy input. A source download, control
receipt, requested value or UI text alone cannot substitute for an effect.

| Area | Required actual measurement source and semantics |
| --- | --- |
| world-navigation | Actual address/grounded position (A/B from `navigation_observation.POSITIONS`) plus independently read bookmark storage and directory response; A/B identify the controlled viewpoints. A failed navigation retains B and shows `not-found`. Restart retains the renamed bookmark. |
| authentication | Provider session/profile and protected-resource access identify `anonymous` or `owned`. Invalid credentials create no session. Keep the actual request pending through close/reopen; restart its consumer before releasing a real valid old grant. Observe anonymous new-process protected access and actual retained delayed server authority. Restart retains valid login; native logout clears current local authority and survives restart. Separate fixture cleanup revokes remote issued tokens. |
| avatar-people | Independent peer observes actual model source, replicated scale, attached owned wearable and connection consent. Bookmark storage is independently enumerated. `original` refers to the captured initial avatar; A refers to the pinned avatar fixture. Scale/attachments must visibly change. Consent cancellation/rejection must leave no connection; acceptance is mutual. |
| create | Real entity/server query identifies exact owned objects, selection, texture source, voxel value and effective rez permission. Cancel imports create nothing. Use the owned domain host. Create PolyVox with an 8×8×8 volume and the normal central-cube initial shape; use ordinary properties to place a unit-size volume two metres in front of the controlled avatar. `voxel-edit` selects cube/remove, a 0.5 m brush and one click at the visible front-face centre. `voxelValue` is 0 for unchanged saved voxel data and 1 only after the actual saved bytes differ from the creation baseline with native `isVoxelDataReady` true; it is never the requested brush setting. Model/texture/voxel changes require real geometry pixels; denied rez leaves zero objects and explicit permission feedback. |
| emotes | Ordinary plays/Sit must have a real native override, loaded selected resource and changed evaluated joints. `poseProgress` is the fraction of a nonempty original joint set that changed, never chooser progress. The nine non-Sit `wait-complete` actions send no product input or restoration call; actual automatic restoration and later evaluated idle pose must be observed. Choosers may hide/retain according to the selected submitted-source profile; reopen through ordinary input when necessary. Sit variant discovery resets through normal controls, gathers all actual Sit1/2/3 with at most 24 attempts per new variant and accepts either actual reset timing; no requested variant is sent. The final Waving cancellation additionally requires independently measured `restoredBeforeNominalEnd:true`, using the original native range/rate, restore event and later inactive evaluation with the 250ms margin in the version 5 migration. Delayed natural completion is false. Native timing does not identify button/timer cause: correlate original input/source and independent current peer/image effects. Unknown history is unavailable, never a guessed flag. Cleanup restores actual state and clears only the owned run association, not native history. |
| world-web/tablet-web | [Version 11 source contract](feature_journeys/WEB_SOURCE.md): actual native documents/status/origins, independently witnessed trusted Send attempts, native/script acceptance and matching page echoes, actual 404/restoration/Reload, reconstructed blank resume and native inline carrier/retired callback. All fifteen fields require independent sources. No HTTP-inline, assumed form retention or host-GET substitution. |
| graphics | Freeze actual original resolution/haze/mirror preferences and completed-frame/pass state through fresh agreeing baseline observations before any input. Change the ordinary immediate viewport-resolution control (0.5/0.6), Haze and Mirrors both ways; close/background/restart must retain changes. `renderScale` measures the actual completed render target; `hazePass`/`mirrorPass` require actual pass execution and original changed world pixels, independently of settings. `restore-original` and double cleanup restore the independently measured original state; no expected values are sent to adapters. See the version 4 migration for native fixture/persistence obligations. |
| audio | Actual automatic three-second preview cycle: original native phase/history and capture/played/live-buffer frames, original pre-normalization input PCM plus independent acoustic PCM with the recorded-preview-v1 challenge. Completion requires capture/play/drain/completed history, equal captured/played frames and empty product buffers. The normal Record button cancels only an observed active cycle. Muted Start and mute/background cancellation are measured from real events/bytes. There are no Save/Preview Start/Stop/Discard controls. OS denial/recovery remains in the composed permission foundation. Cleanup releases E2E evidence separately and requires a verified restart to restore initial native idle history. |
| chat | Acquire original rendered channel rows, persisted Local/Domain histories and actual active MessagesMixer presence separately from the independently received peer ledger. `select-channel` uses Local/Domain tabs; it does not block a peer. A Domain payload arriving while Local is selected remains in Domain history and becomes visible on switching back. A Local sender more than 20 metres away is rejected. Close destroys the owned page and cancels an unsent draft; reopening starts on Local and reconstructs original persisted history. Sane mixer removal must be observed before offline Send: native MessagesClient then emits local-only echo, QML clears the draft, and the actual remote peer receives nothing. Restoring the mixer never queues/replays that message; require a full three-second quiet window. Explicitly retype before resending: local Domain history contains the two actual copies while the remote peer contains exactly one retry. No offline banner, preserved draft or delivery ACK is invented. |
| snapshots | Independently witness original pending/cancel/complete history, actual review/system sheets, supported Save backend and OS authorization, app-private captures, OS-saved originals, share-receiver files and authenticated upload bodies. Denied Photos Save retains a valid private capture; Android Save needs no storage permission. A chooser callback is handoff only. Read original bytes from each destination and require equality with the pinned private PNG. Cleanup removes only owned originals and restores measured authorization. See SNAPSHOT_SOURCE.md for exact profiles and cancellation timing. |
| scripts | `picker-open` activates the existing Running Scripts **From File** control and observes the real **Open Script and Companion Files** picker. `picker-cancel` dismisses it and leaves zero running engines/effects. `picker-accept` chooses the owned `script.js` plus companion or `script-bundle/main.js` with its relative `companion.js`, using the platform's real file/bundle picker. The accepted source loads directly; no client-script consent dialog is invented. `companions` lists actual relative modules resolved by the current owned engine, not requested filenames or retained staged-file presence. Read actual running engines and the ticking owned entity independently. Restart starts actual execution from the retained owned source again. `effects` must advance at least two actual ticks in a successful observation window; Stop leaves zero active effects/engines/entities/companions. The separate `load-url` uses From URL with the owned missing.js URL; actual load failure leaves no running engine. Entity-script consent remains in the reused `scripted-entity` suite. |
| assets | Independently enumerate owned server mappings, selected resolved resource, finished bake output, actual rezzed model and effective write permissions. `import-selected` uses the real Add to World button and model dialog; `remove-owned-model` deletes only that owned entity through normal Create controls. Only this run's unpredictable mapping names may change. `mappings` lists owned bundle roots; `companions` lists every mapped relative dependency (glTF mesh/texture or OBJ material/texture), so partial uploads and leaked companions fail. glTF and OBJ companions must remain resolvable. Bake `ready` means usable derived output, not queued work. Denied delete preserves mapping; permitted delete removes it; missing upload cannot create one. |
| lifecycle-input | Observe actual editor/focus/keyboard ownership, held-input routes, world displacement from independent native positions and context generations. World input while editing produces no displacement. Back first releases keyboard, then closes editor. Replace context before delayed input; the new context remains empty. World input works once focus is released and remains bounded; cleanup releases every held route and restores position. |

Normalize only documented public aliases. The actor may retain private IDs in
its private state; it must never expose email addresses, passwords, filesystem
paths, device selectors or peer session IDs in `facts`. The common layer rejects
strings outside the fixed vocabulary before recording them.

## Cleanup and qualification sequence

Capture the initial owned test profile before input. Never clean up a pre-existing
object or source merely because it resembles a fixture. Register unpredictable
names, require the clean baseline, track every partial operation and clean up
only those owned IDs. Restore original permissions, settings, avatar, mappings,
bookmarks, accounts, capture format, panels, focus and input routes. Stop only
owned scripts; never Stop All. Remove only owned exported/recorded/share files.
Keep diagnostic originals in the private runner artifact directory until the
normal artifact retention/audit step. Secondary actors must observe restoration
before journal retirement. Preserve the first failure while still attempting
cleanup; cleanup failure prevents an otherwise successful result.

Qualify each adapter against the common counterexamples before advertising it.
Then run all hardware suites exclusively through the Jenkins laboratory on
Proxmox using the official `overte-jenkins` CLI. The workstation device laboratory
is retired; do not start local Appium/device-connect services or use a direct
local device run as fallback. Inspect live agents through the CLI before changing
configuration. Run the existing and new area suites with exact installed-code identity,
`--require-complete`, and the normal privacy/acceptance pipeline. Register real
physical evidence only after those steps. A successful simulation, native
input acknowledgment or host-only check cannot promote a production cell.

The optional [account provider v2](feature_journeys/ACCOUNT_PROVIDER.md) defines
the existing fixture server's actual HTTPS OAuth/profile paths, private account
inputs, original protected-request proof, delayed delivery and separate handler/
authority cleanup. It is a reusable backend prerequisite, not native login or a
complete Authentication producer. Native trust/origin, current credential probe,
ordinary controls and independent pending/error observations remain required.

The [native account observation v1](native/ACCOUNT_OBSERVATION.md) supplies
passive actual flags and immutable current reply/signal records through the
existing sampler. Require it explicitly for account-dependent consumers. An HTTP
receipt, cached token or login signal still cannot replace protected-access, UI
and independent actor observations.

The [protected-account probe v1](native/ACCOUNT_PROTECTED_PROBE.md) defines
closed read/release/inspect operations, original HTTPS response provenance,
current credential/origin fences, native deadlines, persisted intent and actual
reply/body/authority cleanup. Independent account/server joins exist as typed
components. Native origin provisioning and full normal-input/UI/actor/restart
composition remain required; no full area capability is enabled.

The [account-origin fixture ownership v1](native/ACCOUNT_ORIGIN_OWNERSHIP.md)
now defines exclusive native configuration files, original inode/write evidence,
source-instance fencing and retirement before actual cleanup. Its common reader
and persistent owner reject ACK-only staging and late recreation. Platform
transport/cleanup factories, ordinary account UI and full actor/restart joins
remain open; native source is uncompiled.

Authentication version 6 closes/reopens the view while the actual native request
remains pending, then retires its consumer through a real app restart before
releasing the delayed valid response. Startup prompt dismissal is an ordinary
idempotent UI action. `delayedGrantOutstanding` must be measured from the provider
v2's sanitized original delayed-request/current-authority endpoint, separately
from native identity/pending/authorization. The independent witness includes
actual dialog and error too. Native logout does not imply remote revocation;
reader-side cleanup separately blocks grants, cancels held handlers and revokes
issued fixture authority. See the current migration for complete obligations.

The [normal login control v2 source and recipe](native/NORMAL_LOGIN_CONTROLS.md)
now supplies narrower Phone/generic-QML UI prerequisites: original error/pending/domain
facts and ordinary field/pointer/key input, with credential-context tokens and
mandatory caller-owned intent. It is not a full Authentication producer. Concrete generic-surface transports, full durable ownership, logout/restart and independent witnesses
still require concrete platform composition. Native source remains uncompiled.

The [private login input lease v2](native/PRIVATE_LOGIN_INPUT.md) reserves an
exclusive native original and retires its nonce, pathname and descriptor after
actual private transfer/GUI delivery. Public commands/receipts and durable
journals contain no credentials. Copied originals, false cleanup ACKs and missing
source stay unavailable. It is a carrier prerequisite; concrete private iOS
transport/callback integration and the full independent Authentication verdict
remain separate. Native source is uncompiled and devices untested.

## Chat version 7 adapter prerequisites

The [source-specific Chat contract](feature_journeys/CHAT_SOURCE.md) defines the
24 checkpoints and the actual no-mixer boundary. Primary and independent actors
must acquire their own fresh original UI/storage/node/peer observations; neither
may copy the other's normalized state or count outgoing native sends as peer
delivery. The existing domain peer animation/heartbeat proves no Chat delivery.
No complete Chat capability is enabled by host reducer/source-boundary checks.

The [Create v8 source contract](feature_journeys/CREATE_SOURCE.md) distinguishes
ordinary Model URL creation from local entity-JSON import, requires actual picker
open/cancel/accept, independently observes UI/rez errors and retries after real
permission recovery. Export references are assertions only, never product files.

## Original Create input components v1

The [native Create control contract](native/NORMAL_CREATE_CONTROLS.md) and
`TokenCreateUI` now implement shared ordinary field/choice/tab/entity selection
and scrollbar recipes for the existing Create foundation. The corresponding
local branch packets add Phone private probe/Qt input, Pico's bound VR-tablet
normal input, and iOS's explicitly unbound native UI component. Each requires
caller-owned persisted intent and retains the captured reference through fresh
backend admission. Consumed input counters and widget readback still require
independent actual entity/history/resource observations for a feature verdict.

| Local adapter packet | Input component | Remaining complete-area status |
| --- | --- | --- |
| Android Phone `e88825d4d0` (fixture namespace fix `46ae6d6461`) | `PhoneCreateIO`, private `phone-create-ui`, `Test.phoneCreateUi` | Full adapter missing; devices untested |
| Pico `cc6ea0224e` (fixture namespace fix `b70f01e528`) | `PicoCreateIO`, existing candidate/PID/OpenXR-bound `PicoNavigation` | Full adapter missing; devices untested |
| iOS `83e7756b2c` | `create_controls.IOSCreateIO`, sequenced native normal pointer/field input | Full adapter missing; installed-code binding unavailable; devices untested |

These local commits live on their separate platform branches and must later be
integrated with the matching product parity source. Native C++/ObjC++ remains
uncompiled. Fifteen initial shared recipe cases were included in the passing
645-case no-build common selection; a sixteenth closed iOS fixture-activation
case and the final namespace correction passed focused checks afterwards.
Phone's full component group passes 86 host cases; Pico Script/Login/Create
passes 56; iOS's permitted host selection passes 306 plus five canonical entry
checks. These are test-logic checks, never product or physical acceptance.

No complete `feature.create.act|observe|cleanup` triple has been enabled. Model/
texture, JSON picker/export, PolyVox, permission actors, durable full-run ownership
and original file/image/peer joins remain required. The existing Phone
`create.*` registration continues to use its earlier accessibility foundation;
these new original-token helpers do not silently replace that registration.

## Snapshot version 9 adapter prerequisites

The [Snapshot source contract](feature_journeys/SNAPSHOT_SOURCE.md) is normative
for its 18-row source-profile inventory. Measure/pin the actual Photos/MediaStore/
document-picker backend and authorization independently before input. Conditional
rows are source-specific obligations, never missing-capability skips. The adapter
must reject an action incompatible with its actual backend rather than ACK a
fictitious permission or chooser. All three
profiles require actual queued-capture cancellation history, a private PNG, normal
successful Save, observed system Share/open/cancel/delivery, failed/retried upload,
resume and complete independent cleanup.

Snapshot file artifacts now require `source` equal to
`snapshot-private-original`, `snapshot-saved-original`,
`snapshot-receiver-original` or `snapshot-upload-original` according to the
actual acquisition endpoint. Fresh action/sample metadata cannot relabel an old
file as a new delivery. Native/independent actors must obtain those bytes from
the real owned endpoint; the common reader pins the original PNG's SHA-256 and
checks destination equality and its original capture challenge. No full Snapshot
adapter is enabled by the common correction or synthetic counterexamples.

## Independent Chat receiver v1 component

The [receiver/source handoff](native/INDEPENDENT_CHAT_RECEIVER.md) now defines
separately acquired primary and peer native caches, actual process/source/mixer
pairing, original remote message order/multiplicity and durable receiver cleanup.
Nine new host counterexamples pass; the complete permitted no-build common
selection passes 663 cases without skips/failures/errors/compiler attempts.
The existing read-only MessagesClient source can be invoked from an explicitly
opted-in E2E Assignment Client script on its real owner thread. Default domain
peer motion/heartbeat still does not produce Chat receipts. The private actor
transport was subsequently implemented below; peer stimulus/mixer ownership,
normal primary UI/storage joins and complete adapter activation remain missing.
Native source is uncompiled.

## Native Chat actor file transport v1

[CHAT_ACTOR_FILES.md](native/CHAT_ACTOR_FILES.md) specifies the new default-off
Assignment Client native IPC source, original-file envelopes, actual process/
executable/start/environment qualification and actual kernel FD retention/release.
The existing domain fixture opt-in stages it only for its dedicated peer, with
private expected-source configuration and a fresh root on whole-stack restart.

Fifteen private-file and seven Linux kernel/synthetic-worker cases pass, including
copied output with rewritten inode claims, unheld source metadata, ignored
queries, foreign/stale sources, uncertain writes and incomplete FD cleanup. The
existing four domain-controller cases pass. The preceding common regression
selection passed 683 checks; the final two FD-provenance counterexamples and the
55-case focused Chat selection passed afterwards. No build/compiler/device
execution occurred. Full Chat composition/capabilities remain missing.

## Owned MessagesMixer actuator v1

The existing domain fixture now has a private authenticated mixer-only process
control path. It pins owned type 4, persists and independently reads intent,
signals the original process through a pidfd, verifies actual exit/live restart
and journal absence, and preserves peer/domain/other services. See
[MESSAGES_MIXER_CONTROL.md](native/MESSAGES_MIXER_CONTROL.md). Fourteen focused
synthetic-worker cases and four controller cases pass. The independent receiver
now rejects matching old mixer identities after both sources observed absence
(ten receiver cases pass). Native node recovery, normal primary Chat UI/storage,
peer stimuli/publisher and complete-area activation remain required. These host
results do not qualify product behavior or devices.

The final permitted common regression selection passes 704 host checks with no
skips, failures, errors or compiler attempts (three explicitly excluded native
build checks). This selection includes both new Chat actor transport/FD checks
and all owned mixer/controller cases. It proves test logic only; native code
is still uncompiled and all physical client runs remain unperformed.

## Browser source audit prerequisite

The current v9 browser draft has unresolved source mismatches: HTTP404 is not a
native load error, reloading a permanently missing resource cannot recover it,
the generated stub has no real script echo, foreign-origin negatives lack a
proven attempt, and HTTP inline.html is not the actual native data-HTML route.
See [WEB_SOURCE_AUDIT.md](feature_journeys/WEB_SOURCE_AUDIT.md) for confirmed source
paths and the concrete correction/instrumentation packet. Browser capabilities
remain unavailable; do not implement desired-state receipts around this draft.

## Original Chat control component v1

The shared [normal Chat control contract](native/NORMAL_CHAT_CONTROLS.md) now has
original QML/model identification, native pointer/IME/Return input and a shared
run-bound recipe. It retains captured draft/channel/focus references, requires
durable intent and actual consumed counters, then reads actual widget effects.
Its 14 host cases pass; the complete permitted common selection passes 718
checks without skips, failures, errors or compiler attempts. Native code remains
uncompiled. Platform wrappers, private original model/settings endpoints, actual
keyboard/route measurements and full Chat composition remain outstanding. The
closed-page active-channel assumption also requires source-contract correction;
never copy local as a measured property of a destroyed QML page.

## Chat version 10 source correction

[CHAT_SOURCE.md](feature_journeys/CHAT_SOURCE.md) now defines closed `channel:none`,
actual Local re-entry, all ten independently witnessed UI/storage/peer fields,
mandatory independent open/type observations, actual tab focus outcomes and a
real background/resume checkpoint. Do not substitute QML keyboard requests, old
widget defaults, retained reducer state or lifecycle input counts for actual
observations. The complete flow has 25 checkpoints. Old v9 whole-area samples
cannot be promoted by inventing the missing independent fields. The original
normal-control components remain primitive v1; complete v10 adapters are missing.

The v10 common journey group passes 67 host cases; the complete permitted common
selection passes 721 with no skips, failures, errors or compiler attempts. The
three native compiler-dependent voice cases remain explicitly excluded. These
results validate host test logic only. Native instrumentation remains uncompiled,
complete area adapters remain missing and all three physical clients are untested.

Version 11 corrects browser source semantics and document transitions; see [the exact Web handoff](feature_journeys/WEB_SOURCE.md). It does not promote complete adapters or device acceptance.
