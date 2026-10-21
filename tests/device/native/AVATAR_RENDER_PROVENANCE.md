# Original avatar and model-draw provenance, version 1

This additive E2E-only instrumentation and its Phone read-only factories identify
the actually loaded local-avatar geometry among executed main-mono model draws.
They produce no pixel/Emote verdict, input, product setter or full capability.
Native sources remain uncompiled and devices untested. Existing Graphics
subject v2, world acquisition v2 and GPU trace v2 contracts stay unchanged.

## Loaded avatar observation

`Test.featureAvatarRenderObservation` accepts exactly `schemaVersion:1`, fresh
`commandId` and `action:"feature-avatar-render-observe"`. No subject selector,
desired avatar, URL, pose, camera or expected output is accepted. Nonces are 32
lowercase hexadecimal characters, prefixed with `ios-` only on that transport.
The actual original object is saved as `feature-avatar-render.json`.

The standard closed envelope is `schemaVersion`, `requestId`, native `instance`,
strictly advancing `sequence`, actual `processId`, `requestedEpochMs`,
`capturedEpochMs`, `source`. Source has exactly:

| Field | Original source |
| --- | --- |
| `avatarRenderVersion` | Integer 1 |
| `modelInstance` | Per-object E2E identity of MyAvatar's actual SkeletonModel |
| `rigId` | That actual Model's Rig ID; join separately to original evaluated Rig history |
| `loaded`, `visible`, `addedToScene` | Original Model state |
| `localRenderingEnabled`, `avatarShouldRender` | Actual MyAvatar/Avatar render gates |
| `geometry` | Null when no loaded HFM exists; otherwise `instance`, `sourcePresent`, `sourceSha256` |
| `pose` | Original feet position, world orientation and model scale |
| `cameraMode` | Actual camera mode string |
| `view` | Actual position, rotation, row-major 4×4 projection, FOV, aspect, near/far clips and perspective flag |

The source hash is SHA-256 of the **loaded immutable HFM `originalURL` UTF-8**,
not `Model::getURL`, a preference, requested FST/root URL or fixture expectation.
An absent URL has `sourcePresent:false` and the actual empty-byte SHA-256; it
does not authorize a visual join. For FST bundles the loaded inner model URL
may differ from the requested bundle URL. Controlled fixture expectations must
account for this actual distinction rather than substitute the requested URL.
Raw URLs, account data and native pointers are not exported.

Model object IDs are diagnostic metadata only. Geometry copy construction and
assignment create new diagnostic identities. No pointer-address reuse or copied
ID can establish another loaded object's identity.

## Executed draw table and exact PNG ownership

Only the existing E2E main forward, default, nonmirror, mono view has a
`FeatureRenderTrace`. Each actual `ModelMeshPartPayload` records immutable
Model/Geometry/source metadata from its loaded mesh at construction. After an
actual positive indexed draw with a valid cluster palette, a GPU callback
records it on the currently executing backend. Discarded batches, nonexecuting
backends, shadow, stereo and mirror draws cannot populate this table.

The payload retains only a weak identity of its original draw mesh. Ordinary
scriptable mesh replacement is counted but contributes zero to
`originalGeometryDrawCommands`. The loaded HFM hash cannot turn those foreign
mesh draws into original-geometry evidence. A mixed table stays mixed.
This compares original mesh object identity, not a hash of all vertex/index or
texture bytes. It does not certify absence of in-place buffer edits, material
changes or unrelated animation. Controlled fixture/content and original pixel/
Rig checks remain necessary for that higher-level claim.

The trace's separate `modelSnapshot` contains exactly `modelTraceVersion:1`,
actual same `frameId`, original `recordedEpochMs`, `begunEpochMs`, last model
`completedEpochMs`, `renderer:"forward"`, `view:"main-mono"`, total
`drawCommands` and `models`. Empty actual tables are allowed observations, never
proof of an avatar. A row contains exactly:

- `modelInstance`, `geometryInstance`, `loadedSourcePresent`, `loadedSourceSha256`;
- positive `drawCommands` and summed actual index count `indices`;
- actual `skinnedDrawCommands`, `blendshapedDrawCommands`, `originalGeometryDrawCommands`;
- componentwise union of actual world payload bounds: `minimum`, `maximum`.

Rows aggregate by both original Model and Geometry ID, retaining mixed geometry
for the same Model. The bound is render/culling geometry, **not a visible-pixel
mask or fragment coverage**. At most 128 distinct pairs and 1,000,000 model draws
are admitted. Overflow, inconsistent source metadata or invalid bounds make the
whole model table unavailable; no truncation supplies success. Other primitive
or instanced draw types are outside this ModelMeshPartPayload table.

The existing capture owner stores the table alongside its exact original PNG.
`Test.featureWorldModelDrawsObservation` accepts exactly `schemaVersion:1`,
fresh `commandId`, `action:"feature-world-model-draws-observe"` and the owned
`captureRequestId`. This is a capture selector, never an expected model.
The original result is saved as `feature-world-model-draws.json`.

Its standard fresh query envelope uses the capture context's actual native
instance/PID and an independent query sequence. The source is exactly
`modelCaptureVersion:1`, `captureRequestId`, original `captureSequence`,
`acquisitionSequence`, `captureCapturedEpochMs`, `imageSha256`, `pixelSha256`,
`modelTrace`. All source times and identities remain original on repeated
queries. The reader joins them to the existing complete capture packet and its
original GPU trace/frame, image digest and pixel digest. It rejects old tables
under fresh query envelopes and every foreign capture/context/frame/image.

The source exists only for the current successful original capture. A new
capture, failure or existing owned storage `release` clears it; retired or
foreign capture requests cannot retrieve it. It holds neither extra pixels nor
Model/Geometry strong references. Existing world-render storage/receipt ownership
and callback-drain cleanup remain mandatory. These two static observation files
do not create a new render lease or replace that cleanup.

## Reader limits and composition

Both getters retain the private `--testScript`, results-root and native lifecycle
guards. Phone factories require an existing read-only candidate-bound session;
they do not launch or repair the app. The probe deduplicates commands, forwards
the original object and reports missing hooks as unavailable. Host readers
enforce exact versions/shapes, finite matrices/bounds, complete counts, original
birth/PID/counters and clocks. They allow at most 262,144 UTF-8 bytes and 51 reads
within five seconds (1.5 seconds for the existing iOS clock-independent route).
Actual source age is bounded to 1.5 seconds with the existing future-clock
tolerance. Final guards, decoding and copies consume the budget; a frozen
device clock cannot hide their host monotonic age. No native clocks are replaced
with host wall time. Historical avatar cursor replay preserves original times
and makes no native requests.

`avatar_draws` additionally requires fresh before/after avatar originals bracketing
the exact frame recording/readback, a stable loaded Model/Geometry/Rig and render
gates, steady pose/camera and agreement with the original frame projection.
Exactly one geometry row for that Model must match the actually loaded source,
contain actual skinning and exclusively original geometry draws with positive
world bounds. Quaternion sign equivalence is preserved. The returned value is
the measured row, with no inferred visibility or success flags.

The complete Emote owner must still join controlled avatar content and actual
Rig/VM input causality, project the measured body bounds through the retained
view, verify current challenge PNG pixels and meaningful body-region changes,
obtain an independent actor's originals, and retire fixture/UI/browser/capture/
whole-run ownership. Draw counts alone cannot prove visible playback, cancel,
restoration or cleanup. No full Emote capability is advertised by this packet.

Device-free tests execute the real Python readers/joins, original JavaScript
dispatch and Phone factories against synthetic native boundaries. Counterexamples
include ignored input, missing/old/foreign originals, replaced meshes, mixed
geometries, bad counts, overflow, changed pose/projection, stale final delivery
and missing hooks. Source wiring assertions are **not native execution tests**.
