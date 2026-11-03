# Original second-client Pico remote Avatar observations

The private `feature-pico-remote-avatar-observe` command has only schema v1,
nonce, run ID and remote subject session UUID. It is read-only and test-gated
by `OVERTE_E2E_FEATURE_TESTS`, `ANDROID_APP_PICO_INTERFACE`, active
`--testScript` and the original lifecycle observer. It does not register a
complete Avatar, Emotes or Actor capability.

`TestScriptingInterface::featurePicoRemoteAvatarObservation` uses a dedicated
instance of the existing bounded `AudioSettingsQueue` dispatcher, with its
existing 1000 ms dispatch and 200 ms NodeList channels. An immutable original
request retains the same epoch and `QElapsedTimer` from
before first queue admission through every queued hop, capture and final
encoding/return. Neither a late functor nor post-publication delay can start a
new observation clock. NodeList and its DomainHandler are read only on their
actual owning thread, before and after
the subject observation. Both actual snapshots include the original session,
Domain UUID, connection state and existing `featureChatSession(run)` birth,
revision and run-bound Domain digest. Changed snapshots or dependencies refuse.
No URL is supplied to connect, no Domain is started and no client is selected
by an expected model or requested avatar URL.

The subject UUID is a lookup scope only. The actual AvatarManager must return
a non-self Avatar with that actual session UUID. Its original Avatar and Model
are held weakly between calls; expiration or replacement cannot be rebound.
The getter copies the existing Avatar-load instance, Model/Geometry identities,
immutable loaded HFM source digest and actual Rig ID. `picoRemoteAvatarVersion`
is now **2**: it preserves the old raw `e2eAnimationObservation` (normally empty
for OtherAvatar) and adds the distinct `remoteJointPoseVersion: 1` described
below. It never invents a local animation evaluator, override, caller or clip.
Actual feet pose, scale, visibility/scene flags
and current recording frustum are copied without setters. The local-only
`shouldRenderLocally` property is neither imported nor forced onto this remote
subject; Android's existing local-avatar rendering policy is unchanged.

The getter also records the actual current GPU `FeatureWorldRender::instance`
and rechecks the same GPUContext. This connects the remote subject's observed
client to its own original capture and model-draw stream. Equal process numbers
on different devices cannot borrow another client's PNG or renderer birth.

The probe forwards each of at most 512 original nonces once, preserving the
native result or explicit unavailability. It performs no local-avatar fallback,
getter retry, animation action or model capture. The new native header and
getter remain **uncompiled and unqualified** in this packet.

## Actual remote joint producer and committed-section provenance

The actual `SkeletonModel::updateRig` remote path skips local animation
evaluation. `OtherAvatar::interpolateJoints` instead calls
`Rig::copyJointsFromJointData` and `computeExternalPoses`. Consequently the v1
Host positive used a modeled local-Rig DTO that a real remote avatar need not
produce. The v1 real-empty-Rig path correctly refused; it is not a qualified
remote effect source and is never relabeled as v2.

E2E-only observation now records the actual copy attempt before either original
early return, completion after actual relative-joint assignments, and the actual
external-pose build. A rejected copy clears its previous completion; rebuilding
an already completed copy cannot renew its completion clock. Only the existing
OtherAvatar path snapshots the new copy under its original joint-data lock.
The snapshot binds the actual subject/Avatar/Model/Geometry/Rig, original copy
cursor and clocks, counts and complete bounded relative/absolute joint samples.
The getter reads the stored snapshot; it does not evaluate or retime a pose.

Copying old network data is not a new receive. The actual `AvatarData` parser
records only completed JOINT_DATA and default-pose-flag sections, after their
original assignments under `_jointDataLock`. Latest entries retain the actual
section bytes (at most 8192), byte count, SHA/base64, subject, section kind/count,
original parser-entry `usecTimestampNow` and epoch, actual commit epoch and
per-Avatar committed-section cursor. These are **decoder committed-section
provenance**, not socket-arrival time or whole-packet validation. Unrelated
account/wire payload is not copied. A valid joint section followed by an invalid
later packet tail is not called a valid whole packet.

Interpolation/simulation bookkeeping and `_hasNewJointData` are not receive
sources. Recopying, getters and rendering retain the same original section
identity and age. A rejected/truncated section cannot refresh it. Joint-data
age is checked separately from copy freshness. The Host rejects a fresh recopy
of stale committed data, foreign section identity even with identical raw bytes,
missing/rejected copy completion and mismatched geometry/counts. A measured
copied-pose difference requires a genuinely newer committed joint/default-flag
section and changed actual joints; a cursor advance or quaternion sign change
alone cannot qualify. No animation/Sit/early-cancel cause is derived from these
remote samples; the independently queried Primary Rig remains a separate source.
The retained section entries are the latest committed sections at the copy
boundary. They do not identify every earlier sample contributing to per-joint
interpolation. `newCommittedSections` reports newly observed commits alongside
an actual copied-pose difference, without asserting packet-to-pose or
packet-to-draw causality. Per-joint interpolation provenance remains open.

Lock order remains original joint-data lock, then bounded E2E copy/pose
observation. Commit helpers do not reacquire the nonrecursive joint lock.
The reader takes only the observation lock and never takes joint-data lock
while holding it. Native capture/lock behavior is source-reviewed, not compiled
or device-qualified. Four extraction checks verify actual hook order and the
unchanged original non-E2E bodies of the parser, copy, build and interpolation
functions (only empty-line normalization is used).

## Existing transport and durable source owner

`avatar_remote_source.create(adapter, target, phase, subject, source_lock,
primary=...)` reuses `_script_runtime`, `_native_feature_observer` and the exact
already-held Script source lock. The phase area is the unchanged Common v16
`avatar-people`. Source2 also admits an explicit immutable `emotes` area, with
its separate `emote-remote-owner` namespace; it cannot relabel an old Avatar
source. A first client can acquire its own original packet with
`primary=None`, observing the other client's actual UUID. The second client's
owner takes that retained original packet as scope and queries the first
client independently. Its own actual native birth/session must differ, and
both independently measured clients must agree on Domain and run-bound digest.
The Primary's model, scale or requested facts never supply the Actor's subject
facts. This is a private source; no independent worker launcher or physical
cross-process scope-publication authority is added here.

`picoRemoteAvatarSourceVersion: 2` uses the existing `LifecycleProcessFile`
original OFD/CAS owner and `ChatSourceChunks` immutable original files. The
actual original producer host identity is pinned. A cold current-owner
reconstruction requires that same host, binding and original interval; it is
not cross-host adoption, a worker return or proof of the previous host's exit.
`NativePicoRemoteAvatar.restore` separately validates historical packets without
issuing a query or gaining current ownership. A real separate host counter
restores history but is refused current-source ownership with zero queries.
The original host retains and revalidates its actual file descriptors.
Strict Remote1 remains historical-only, requiring its original nonempty local
Rig contract. The source's no-query `archive` reads Source1/2 originals, including
retained failed raw responses; it does not return a current owner. Source1 cannot
authorize a new Source2 read or acquire a new area/deadline. Historical Source1
model positives and real-empty-Rig negatives have separate owning counters.
The original eleven-file v1 packet was saved verbatim with hashes and its tracked
diff before these version changes.

The root records original responsibility before a provider/native request. Each
native command and **every raw response** are durably retained before parsing,
in exact 4096-character fragments with full UTF-8 byte length/hash. Malformed,
foreign, empty or unavailable replies stay available for audit. Raw references
reject Boolean/index aliases, reordering, wrong kinds and changed bytes.
Original Primary scope bytes are retained separately from the bounded root.

Each owner allows at most 32 observations and keeps its initial monotonic,
native and provider-host anchors under the same 120-second budget. The native
reader checks the original 1.5-second admission again after durable request
retention and before send. Each source read keeps original provider bookends,
Rig clocks, exact client continuity and final freshness, including after its
last durable save with a frozen native clock. A refused or late observation
durably marks the source `failed`; pending/lost/refused work cannot become a
cold ready source or renew its interval. Cold reconstruction replays original
native/provider history and restores the committed monotonic floor.

Original source and directory descriptor pairs close only through their actual
verified owner. Uncertain pairs remain strongly owned until host finalization.
There is no file discard, model unload, callback clearance, input or cleanup
action. The pure host namespace check makes generic Pico cleanup refuse before
all native queries/inputs/base stop for every retained target/run root, prepared
file or original child, including a missing root. Closing host descriptors
cannot retire those originals.

## Original stereo provenance and qualification limits

`avatar_remote.remote_draws` validates both original remote brackets and the
unchanged `PicoWorldModelDraws`/WorldRender capture contract. It joins the same
remote Avatar/Model/Rig, loaded Geometry/source, stationary actual pose and
recording frustum to the actual successfully submitted stereo capture. The
remote getter's renderer birth must equal both capture and draw-stream births.
The exact remote model must have actual skinned indexed draws using its original
geometry in **both** recorded eye camera slots. The existing per-eye viewport,
camera accounting, original encoded/pixel hashes and capture/frame identities
are preserved. The returned row is draw provenance; it is not a visible-subject,
challenge-pixel, original PNG ownership or complete Actor verdict.

Thirty-one no-build Python/Node cases compose the real source/factory/filesystem
and existing rig/camera/draw validators over explicit native/Qt/Rig/GPU/provider
models plus the four producer extraction checks. They cover actual intent/raw retention, cross-client identity, lost or
malformed sources, unknown Rig, provider crossing, replaced Model/original
files, late retention and final save, unchanged deadlines/cold clock floor,
original per-eye joins, foreign-renderer refusal and actual bound Pico cleanup
with zero native reads/writes/inputs for rootless originals. The Host owner
also has genuine delays inside the original predispatch and final source
guards; both preserve the original anchors and fail closed with a frozen
native epoch. These are Host guard counters, not compiled native queue tests.
Native simulation and real Python/OFD behavior remain distinct; no hardware
result follows.

The fixed Phone reference is `5e8ff8aa19571f5718b982dc47a165b8f22e0dc0`.
Its selected Avatar sources/native helpers contain no equivalent remote-avatar
session lookup observer. This packet reuses the already integrated original
Avatar/Rig/WorldRender, source-lock and journal primitives instead of copying
Phone UI, Mono, local-render policy or a new journey. Whole Avatar/Emotes flows,
independent worker launch/publication, real remote pose causes, original image
ownership/pixels and complete Actor/native/renderer/resource retirement remain
open. No public capability or completion status is promoted.
