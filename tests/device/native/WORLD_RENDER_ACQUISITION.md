# World render acquisition, versions 1/2: partial instrumentation

This source packet supplies E2E-only GL readback, a main-mono frame hook,
original-memory/chunk readers and the closed existing probe/fixture dispatch.
Persistent acquisition/receipt ownership and closed Android receipt IO now
exist; the Phone internal factory is connected. No world image can be obtained through a
complete feature adapter at this stage. Full capabilities remain unadvertised.
Native C++ is uncompiled and all devices unqualified.

The Phone factory now uses [role-bound v2 ownership and native issuer-verified
receipt cleanup](../adapters/android-phone/GRAPHICS_ACQUISITION.md), including
separate read-only actor acquisition and general teardown checks for both roles.
The unscoped v1 owner remains explicit for legacy components. Copying or silently
migrating one role's journal cannot authorize the other role's image or cleanup.
The full Graphics fixture/settings/source/publisher coordinator is still missing.

## Same-view execution provenance, capture version 2

An E2E `--testScript` primary mono forward view now creates its own native
`FeatureRenderTrace`, retained with that view's original GPU command closures.
A Present-thread marker before `PrepareForward` records execution start. Separate
markers after each complete root opaque/transparent batch and root mirror
composite inspect the original finalized batch's draw commands. Named/instanced
calls have already been expanded by `Frame::finish`; recording-time item counts
and input ACKs do not advance these counters. A discarded frame publishes no
trace. No global last-frame trace is read. Nested mirror and secondary views do
not start or replace the main trace. Deferred capture uses legacy version 1.

The same original tone-map readback carries `captureVersion:2` and `renderTrace`:
`traceVersion:2`, random native `frameId`, original `recordedEpochMs`,
`begunEpochMs`, `completedEpochMs`, `renderer:"forward"`, `view:"main-mono"`,
and integer `forwardBatches/forwardDrawCommands`, `hazeBatches/hazeDrawCommands`,
`mirrorBatches/mirrorDrawCommands`. Haze counts identify draw-containing original
forward batches with actual bound active Zone haze and enabled bound lighting
model. Mirror counts identify the root mirror composite batches with actual
draw commands. Empty batches contribute zero. All callbacks require the same
actual executing backend, and the image and trace travel in the same acquisition
packet. Missing execution cannot downgrade a declared trace to legacy version 1.

Trace version 2 additionally retains the immutable `recordedView` taken from the
actual primary RenderArgs frustum at command generation: original world position,
quaternion rotation, row-major 16-number projection, FOV, aspect ratio, near/far
clip and perspective flag. The CPU view is kept with the same GPU command/frame
object that later yields the original image and execution facts. No requested
camera pose or expected matrix is accepted. It is a recording provenance source,
not a separate GPU-uniform readback or fragment/visibility verdict.

Readers continue explicitly accepting closed trace-v1 history. Full Phone
Graphics measurement version 2 requires trace-v2 view provenance. The internal
capture factory's `require_frame_view=True` implies required trace and rejects
legacy capture/trace data. Missing views are never reconstructed from live
Camera getters or guessed FOV matrices. Validation preserves valid off-axis
projections, rejects singular/nonfinite/nonperspective data and checks original
view aspect against target extent. Seven new shared cases and three Phone
join/factory cases exercise these boundaries without compiling or rendering.

These facts prove execution of draw-containing batches with those bindings.
They do not identify visible fragments, prove shader arithmetic or prove an
actual haze/reflection pixel effect. Complete Graphics must additionally require
the controlled subject/view inventory, current challenge pixels and independently
classified original image effects. No feature verdict or preference value is
returned as a pass measurement. No full Graphics capability is advertised yet.

The reader accepts closed v1 and v2 packets; `require_trace=True` refuses v1.
It requires native trace recording before its capture ticket, ordered execution
before original readback, a trace no older than the existing freshness bound,
integer subset/zero/count consistency, at most two root forward draw batches,
and a previously unseen native frame ID. The 256-frame inventory fails closed
without forgetting used IDs. The existing native acquisition/memory/receipt
ownership, deadlines and cleanup remain unchanged. Reader recreation by a full
feature must restore original frame/cursor provenance from its durable ledger.

Fourteen new device-free reader cases cover fresh same-view originals, refused
legacy fallback, missing/unknown traces, reused frames with fresh control/image
cursors, stale/out-of-order clocks, foreign views, injected verdicts, malformed
or impossible draw counts and bounded history. They simulate original source
boundaries only. This native source has not been compiled or exercised on GL.

## Implemented GPU primitive

`gpu::Backend::featureReadFramebuffer` exists only with the default-off
OVERTE_E2E_FEATURE_TESTS option. The default implementation clears the output
image and returns false, including Vulkan/Null/unknown backends. Production
`downloadFramebuffer` remains unchanged; Vulkan's existing void TODO must never
be interpreted as a successful image acquisition.

The GL override additionally requires explicit --testScript and a current GL
context. It reads only an already created, nondefault original GPU framebuffer
that is the actual current draw target with color attachment 0 selected.
The observer now resolves the backend from a scoped thread-local identity set
by actual GL/Vulkan `do_runLambda` execution, rather than retaining the batch
recording context's backend. That scope restores its predecessor on return.
An observer outside actual backend execution cannot read pixels. The GL source
texture, destination texture and framebuffer must belong to that exact backend
and retain the actual original Qt GL creation-context identity. Destroyed,
foreign or merely shared contexts are rejected in version 1. The current
attachment's real texture name must also match the original destination GPU
texture. Coincident numeric GL object IDs in another context cannot authorize
an image. This conservative ownership path still requires native compilation
and device qualification; the host reader cases cannot establish GL behavior.
It never synchronizes/creates a missing framebuffer or falls back to the UI/default
target. Extents are 1..4096 on each axis and at most 8,388,608 pixels. It acquires
only a single-sample 2D color texture. Its actual attachment object, mip level,
GPU texture width/height and current full-target viewport must agree with the
CPU framebuffer description. Requested dimensions alone cannot authorize a
read. The original texture binding on the current active unit is restored;
renderbuffers, multisample textures and unsupported query paths fail closed.
It acquires
original RGBA unsigned bytes synchronously, checks framebuffer completeness and
GL errors, and publishes only a newly acquired nonnull image. Failure clears the
output. Explicit RGBA byte order covers GL/GLES and does not borrow legacy ARGB
screenshot conversion assumptions. The vertical flip converts only the native
coordinate origin, without painting, compositing or resampling pixels.

Original read-FBO binding, that source FBO's read selection, pixel-pack-buffer
binding, alignment, row length and row/pixel skips are restored. Draw binding and
backend draw cache are untouched. Any acquisition/restoration or existing GL
error prevents evidence. Actual state preservation and driver behavior require
later native compilation and Proxmox device qualification; Python tests cannot
establish those facts.

## Closed acquisition contract

The existing private probe accepts exactly
`{schemaVersion:1,commandId:<32hex or ios-32hex>,action:"feature-world-render-observe"}`.
It calls `Test.featureWorldRenderCapture(requestId)` only if that native hook
exists in the installed E2E build. Absent/unsupported sources save unavailable.
Native pending reads are retried for at most 50 callbacks/50ms with the same ID;
they cannot issue new capture intents. Superseded requests and script teardown
cancel the timer. Missing/foreign/late native results never acquire an image.
The original JSON receipt is `world-render-observation.json`.

The original receipt has exactly:

* schemaVersion 1, original requestId, native context instance (32 hex), advancing
  source sequence, original requestedEpochMs/capturedEpochMs and actual processId.
* source: captureVersion 1, available true, actual acquisitionSequence,
  recordedEpochMs, startedEpochMs, capturedEpochMs, backend "opengl", stage
  "tone-map-before-hud", view "main-mono", sourceExtent [width,height],
  sourceViewport [x,y,width,height], targetExtent [width,height], pixelFormat
  "rgba8-top-left", and image metadata below.
* image: name, bytes (1..32MiB), original encoded sha256, original canonical RGBA
  pixelSha256, width and height. Name is exactly
  `world-render-image-<request's normalized 32hex nonce>.png`. It is not a caller
  supplied path. Dimensions equal the actual target extent. The PNG decodes as
  original RGBA pixels; both encoded and decoded checksums must match.

Source viewport must fit the actual source texture. `measured_scale` divides
actual source viewport dimensions by actual destination extent; a preference
getter is not an allowed source. All times must be original and ordered:
request <= GPU-command recording <= acquisition start <= acquisition completion
<= receipt publication. Acquisition and receipt are fresh in the native clock.
The acquisition sequence advances only for successful actual GPU readbacks,
never for control requests, repeated polling, file copies or reconstructed bytes.
An unchanged static image can be a valid new acquisition; it proves no changed
feature effect. Required challenge/subject/actor assertions remain separate.

## Native frame hook and remaining ownership work

`gpu::Context` owns one `FeatureWorldRender` state. An explicit request reserves
only a later original main/default, mirror-depth-zero, mono ToneMapAndResample
batch. Its `runLambda` follows the original draw before subsequent HUD jobs;
recording alone publishes nothing. The callback measures the original source
texture's actual GPU extent, requires agreement with the source description,
and retains the original source subregion used in the recorded tone-map
transform. This is distinct from a preference getter. Qualification must still
verify backend execution/order and effective sampled subregions on hardware.
Mirror/secondary/shadow/stereo are excluded. Vulkan/default backend methods
return false. A backend/view extension needs a reviewed contract migration.

Only one request or undrained callback may exist per context. A 1500ms native
monotonic deadline includes waiting, readback and PNG encoding. Up to 256 retired
IDs are retained without eviction/reuse; after exhaustion a new process/context
is required. Completed receipts preserve original times. A captured ticket
survives execution or discarded-frame destruction, and remains inventoried
until its local image/chunk buffers and callback have drained. Cancellation
clears retained result/PNG immediately and prevents publication by later work.
Memory owns at most one 32MiB PNG plus bounded temporary RGBA/encoding buffers.

PNG names are logical nonce identities, not physical paths. The private storage
contract is independently versioned at 1. A command has exactly schemaVersion 1,
commandId, action `feature-world-render-storage`, requestId (the acquisition ID),
operation `read|release|inspect`, and offset only for read. Reads return at most
65536 original encoded bytes as canonical base64, without recompression.
Replies have exactly storageVersion 1, commandId, requestId, instance, advancing
source sequence, actual processId, original capturedEpochMs, present:boolean,
callbacks:0|1 and pngBytes:0..33554432. Read additionally has offset and data.
No arbitrary path, expected pixel, dimensions or requested content is accepted.

`release` retires the active ID and clears retained bytes. The reader then issues
fresh `inspect` commands until present is false, callbacks is zero and pngBytes
is zero. A release ACK alone cannot establish absence. Each storage command's
original receipt is `world-render-storage-<normalized command nonce>.json` in
the existing private results channel. Platform IO must remove these owned
receipt artifacts and independently verify absence, including partial/timeout
receipts. `WorldRenderOwner` persists explicit unscoped v1 or role-bound v2 acquisition and
each unique receipt intent before dispatch, using the existing private atomic
store. At most 1024 receipt IDs fit within its 64KiB bound. Recovery cannot
adopt a different process/session/candidate or replace an unfinished capture.
`OwnedWorldRenderCapture` first requires fresh native memory absence, then
removes only journaled receipt files and separately queries each absence, before
discarding the journal. Failure preserves ownership for later recovery. The
Android IO performs closed, nonrecursive run-as removal without following
receipt/parent symlinks, under before/after binding guards. The latest storage
command is deduplicated by the single-in-flight probe channel; release cancels
the owned capture timer before cleanup, so periodic polling cannot recreate a
deleted receipt. Deliberate original acquisition metadata remains private run
evidence; all chunk copies and release/inspect transport receipts are removed.
The PNG itself never needs a writable filesystem fallback. Concrete platform
factories are connected separately in the owning platform branches. Full
feature coordinators remain missing. Cleanup has one total 45-second default
budget (the existing session default), including native memory inventory,
unlink and every independent existence query. A stricter caller budget can be
passed; expiry/regressing clocks preserve ownership.

The shared native `feature-world-render-receipt` operation supplies the iOS
removal route without assuming an unsupported driver delete command. The
separate version-1 command has schemaVersion 1, commandId, action, requestId,
receiptId (original storage command nonce) and operation `remove|inspect`.
Native state records each issued storage result's original JSON digest and
capture identity, bounded to 65536 historical receipts per context; quota
exhaustion fails closed. Receipt cleanup requires that exact issued nonce to
belong to a retired acquisition. The results root must retain its existing
private nonsymlink/canonical permissions boundary. A present receipt must
match the native original digest; foreign/changed/symlink files are refused.
The private writer also refuses non-native content or wrong nonce paths, and
does not rewrite an existing foreign document.

Native remove and later inspect are distinct actual filesystem operations.
Replies have receiptVersion 1, commandId, requestId, receiptId, operation,
native context instance, advancing source sequence, actual processId, original
capturedEpochMs and source. Remove source has performed:boolean; inspect source
has exists:boolean. No caller-supplied existence, digest, content or arbitrary
path is accepted. The original atomic private result is
`world-render-receipt-result.json`, retained as bounded run metadata like the
original acquisition receipt; it contains no image bytes. The reader correlates
fresh nonces, PID/context, exact issued owner journal and advancing source
cursor. iOS bounds the whole query to 1.5 seconds without equating wall clocks.
It retries only original reads and never replays uncertain deletion. The probe
deduplicates the command, preventing periodic writes after receipt consumption.

`NativeWorldRenderCapture` requires a durable owner intent callback before the
request because observation can create private native artifacts. A failed intent
prevents request/file creation. Its platform IO must preserve existing actual
installed-candidate/process/session/root guards and read only that exact owned
nonce filename. Metadata, original binary transfer and PNG decode all count
toward the timeout; process/context changes before or after transfer fail.
Android uses the existing five-second/51-read limit with actual device clock.
For the unbound iOS component the total limit is additionally 1.5 seconds: fresh
unpredictable nonce causality bounds image age without assuming equal native and
host clocks. Full-area clock/lifecycle joins remain required. No read is replayed
as a mutation. Failed ownership/release must keep a run red.

Forty-eight device-free cases cover ignored GPU versus fresh control cursor,
missing/stale/foreign originals, RGBA/PNG checksum/shape errors, timing/context
changes, unsupported Vulkan/stereo/post-UI sources, original probe dispatch,
finite retries, transfer/decode budgets, original chunk offsets/digests, ignored
release, undrained callbacks, separate fresh inventories, durable intent failure,
real local journal/receipt cleanup, ignored unlink, symlink/foreign-context
rejection, whole-cleanup budgets and recovery with ownership retained. The
native removal reader additionally rejects unissued paths, foreign/stale
inventories and numeric existence flags; actual local files demonstrate ignored
delete ACK versus a separate existence query. These prove
test/reader logic only, not GL correctness, product rendering or device acceptance.
