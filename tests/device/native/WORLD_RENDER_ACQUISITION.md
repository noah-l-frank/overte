# World render acquisition, version 1: partial instrumentation

This source packet supplies E2E-only GL readback, a main-mono frame hook,
original-memory/chunk readers and the closed existing probe/fixture dispatch.
**Concrete platform transport/receipt cleanup and persistent ownership
coordination are not connected yet.** No world image can be obtained through a
complete feature adapter at this stage. Full capabilities remain unadvertised.
Native C++ is uncompiled and all devices unqualified.

## Implemented GPU primitive

`gpu::Backend::featureReadFramebuffer` exists only with the default-off
OVERTE_E2E_FEATURE_TESTS option. The default implementation clears the output
image and returns false, including Vulkan/Null/unknown backends. Production
`downloadFramebuffer` remains unchanged; Vulkan's existing void TODO must never
be interpreted as a successful image acquisition.

The GL override additionally requires explicit --testScript and a current GL
context. It reads only an already created, nondefault original GPU framebuffer
that is the actual current draw target with color attachment 0 selected.
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
receipts; **that receipt cleanup and the persistent acquisition owner journal
are still missing**. Memory absence does not prove file-artifact cleanup. Full
area activation must remain closed until both are implemented. The PNG itself
never needs a writable filesystem fallback.

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

Twenty-eight device-free cases cover ignored GPU versus fresh control cursor,
missing/stale/foreign originals, RGBA/PNG checksum/shape errors, timing/context
changes, unsupported Vulkan/stereo/post-UI sources, original probe dispatch,
finite retries, transfer/decode budgets, original chunk offsets/digests, ignored
release, undrained callbacks, separate fresh inventories and durable intent failure. These prove
test/reader logic only, not GL correctness, product rendering or device acceptance.
