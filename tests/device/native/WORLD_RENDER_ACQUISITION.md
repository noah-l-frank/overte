# World render acquisition, version 1: partial instrumentation

This packet supplies an E2E-only GL readback primitive, a strict original-image
reader and the closed existing probe/fixture dispatch. **No native main-frame
capture hook or platform image-file transport is connected yet.** No world image
can be obtained through these adapters at this stage. Full feature capabilities
remain unadvertised. Native C++ is uncompiled and all devices unqualified.

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
It calls `Test.featureWorldRenderCapture(requestId)` only if that future native
hook exists. The hook is currently absent, so dispatch saves `available:false`.
Native pending reads are retried for at most 50 callbacks/50ms with the same ID;
they cannot issue new capture intents. Superseded requests and script teardown
cancel the timer. Missing/foreign/late native results never acquire an image.
The original JSON receipt is `world-render-observation.json`.

The complete future original receipt has exactly:

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

## Required native hook and ownership work

Before activation, join a fresh native request to a later actual main-view
ToneMapAndResample GPU execution before RenderHUDLayer. A CPU job invocation
or recorded-but-unexecuted batch is insufficient. Preserve actual render args,
source viewport, source texture and destination extent from that execution.
Exclude mirror/secondary/shadow/UI captures. Version 1 rejects stereo and
unimplemented Vulkan; neither a left-eye guess nor an empty QImage is success.
A later backend/view extension needs a reviewed version/reader migration.

The native hook must reject retired request reuse, preserve completed original
metadata without retiming, bound pending acquisition/memory leases, and expose
original PNG files only in its exclusively owned private context. Files require
exclusive no-follow creation with private permissions, actual content hashing,
known native ownership and separately observed cleanup/absence. Never overwrite
or adopt another session's path. Capture-file/observer buffers must appear in
owned resource inventories until verified release, including timeout/error cases.
No native file writer, release/absence hook or complete cleanup coordinator is
implemented by this packet. They are prerequisites, not simulated successes.

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

Seventeen device-free cases cover ignored GPU versus fresh control cursor,
missing/stale/foreign originals, RGBA/PNG checksum/shape errors, timing/context
changes, unsupported Vulkan/stereo/post-UI sources, original probe dispatch,
finite retries, transfer/decode budgets and durable intent failure. These prove
test/reader logic only, not GL correctness, product rendering or device acceptance.
