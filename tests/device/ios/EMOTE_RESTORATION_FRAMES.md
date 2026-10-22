# Original marker restoration frames

`OriginalMarkerRestorationFrames` owns raw Vulkan fences and untouched private
PNGs before the first marker input and after actual marker cleanup. Its closed
profiles are `emote` and `avatar`; native World, Renderer4 and Vulkan DTOs retain
their original schemas. `IOSEmoteRestorationFrames` selects the Emote profile.
An Avatar facade can select `PROFILE='avatar'` without editing the shared owner.

Construct the owner with the existing `IOSScriptRuntime`, qualified selector,
matching `OriginalMarkerScope`, private artifact root and held source lock.
`capture('initial')` requires an untouched Scope with no baseline or frames.
`capture('cleanup')` requires a released Scope without pending input. Neither
operation changes the camera, scene, avatar or marker. Each result is an exact
`{index, sha256}` reference. `frame(reference)` reads the actual original payload
and PNG. `archive(...)` reconstructs ownership without product reads.

Every capture owns a distinct native request and GPU lifetime. Accepted native,
World and Renderer packets are durably retained before later queries. Recovery
uses `resolve()` for an already returned immutable candidate, or `abandon()` to
retire GPU ownership while preserving every partial original and PNG inode.
An uncertain capture is never sent again. A release with an unknown return is
reconciled by inspection; a reservation without a created owner uses one actual
native release tombstone. An existing owner grants release authority only when
its original initial inspection proved an empty slot; a preexisting occupied or
unknown slot remains unresolved and is never read or released by this owner.
Historical decoding independently replays completed
and interrupted native/World/Renderer/GPU source floors. Every accepted original
GPU receipt, including byte chunks and cumulative drain transcripts, retains its
original instance, sequence and timestamp; matching repeated snapshots cannot
rewrite an accepted receipt. Unqualified camera/body observations may be
abandoned, but cannot become eligible image evidence.

The separate pure `original_marker_restoration_image.restored(...)` joins actual
initial and cleanup frames with the original admitted marker World and a native
cleanup barrier. It requires restored original camera/domain/body/tree, a new
fenced frame, native GPU absence, and the full actual former marker projection.
It compares the untouched pre-marker and cleanup PNG pixels over that projection:
at most one percent may differ by more than ten channel levels, with mean channel
delta at most two. A new frame/hash, entity absence, or GPU release alone cannot
qualify stale marker pixels.

Internal writers/readers are version 1: `markerRestorationFramesVersion`,
`markerRestorationFrameVersion`, `markerRestorationAbandonedVersion` and
`markerRestorationImageVersion`. The registered keys are
`original-marker-restoration-frames`, `original-marker-restoration-frame`,
`original-marker-restoration-abandoned`, `original-marker-restoration-image`.
These are prerequisites; they advertise no whole-feature capability. The image
predicate covers the former marker projection, not arbitrary avatar pixels.
Whole Emote coordination and publication must separately require original pose,
input/VM/entity/receiver cleanup and complete feature integration.

Host verification uses modeled native/SDK/GPU producers with actual private
files and PNG bytes. Twenty-one tests cover Emote and Avatar profiles, genuine
restoration, stale renderer pixels, interrupted creation/read/release, immutable
write recovery, original source floors, camera rejection, file mutation and
incorrect native barriers, occupied/proven-empty initial slots and original GPU
birth/counter resets after abandonment, and foreign or malformed pending GPU
owner carriers. Native C++ compilation and device execution remain unperformed
in this source-only task.

The normal-journey host test runs the actual staged marker Script in Node and
uses the ordinary Script/File/View recipes. It captures the untouched initial
first-person view, changes to Look At with a distinct actual modeled camera
position, then restores the original view before the cleanup fence and pixel
comparison. Temporary native-read journaling is removed in `finally`, including
lost begin/end returns and interrupted abandonment; it never remains installed
on a reader that another owner uses later.
