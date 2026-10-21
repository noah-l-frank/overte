# Original test-only iOS Vulkan world target image

This source is inactive outside the dedicated E2E configuration and test script.
It provides original pixels and metadata, not a Graphics verdict. Native sources
are uncompiled and devices untested. The full iOS Graphics owner is still partial.

## Actual acquisition

The `feature-vulkan-world-frame` command arms the existing GPU frame/context
ticket. The ordinary primary mono forward render records original view geometry
and issued Vulkan draw counts. At the end of the original tone-map batch,
before HUD rendering, the executing backend checks the original successful
framebuffer allocation, bound target and actual viewport. A separate test-only
host-visible coherent buffer receives `vkCmdCopyImageToBuffer` from that actual
color attachment. No observation render target, desired setting, fake texture
extent, product screenshot API implementation or renderer repair is introduced.

The original tone-map render pass ends at its existing batch boundary. The
observation copy ends it at the last draw callback, transitions the color
attachment to transfer source and restores the same original color-attachment
layout. A transfer-to-host barrier covers the copy buffer. There is no added
GPU wait, queue submission or retry. Only the existing matching successful
submission fence permits mapping/copying the buffer. Actual RGBA/BGRA formats
are normalized to declared top-left RGBA8 bytes and encoded losslessly as PNG.
Original PNG and decoded RGBA SHA-256 hashes, physical extents, issued draw trace,
frame index, view and native fence/read/publication times remain in the packet.

The ordinary Vulkan `downloadFramebuffer` TODO remains untouched. The existing
OpenGL capture and metadata-only completed-frame contracts remain separate and
compatible. This source never labels a Vulkan image OpenGL or native-screen.

## Ownership and failures

The frame, queued trace/Args/batch callbacks and original fence retain their
capture group. Native storage independently reports actual retained groups,
pending GPU responsibility, allocated copy-memory bytes, source-owned PNG bytes
and stored metadata bytes. Release clears stored PNG/metadata and permanently
retires the selector. It cannot cancel GPU work or pretend callbacks have died.
Only fresh original retired/not-present and all-zero storage permits absence.

A failed/unknown submission or missing successful fence retains the actual copy
allocation. Context destruction quarantines remaining allocations until process
exit rather than freeing memory potentially still consumed by the GPU. This
intentional test-only quarantine is unresolved responsibility, never a cleanup
verdict. A changed source birth cannot adopt the old owner; actual process-death
proof remains necessary when normal completion cannot be established. Failed
allocation/mapping/encoding or expired acquisition produces no usable image.

## Existing private transport

The closed version-1 command accepts iOS-prefixed `commandId`/`requestId`, action,
and `read`, `read-bytes`, `release` or `inspect`. Only `read-bytes` accepts an
integer `offset`. No expected backend, frame, scale, source version or settings
are accepted. The root original contracts are `vulkanWorldFrameVersion: 1` and
`vulkanWorldStorageVersion: 1`; they do not modify the metadata-only versions.

The existing native Test interface, probe, fixture validator and iOS HTTP/AFC
factory are connected. All original image metadata, 64-KiB PNG chunks and final
release/inspect receipts use the same private atomic
`feature-vulkan-world-frame.json` carrier. Final storage replaces earlier byte
content. The queued probe callback checks ownership before entering the native
source; release cancels its timer and native retired selectors reject late rearm.

`native_vulkan_world_frame.py` verifies closed shapes, actual original allocation/
frame/clock identity, complete immutable PNG/decoded-pixel hashes and contiguous
chunks. Commands require caller-persisted intent before delivery and are never
silently resent. This low-level reader advertises no full journey capability.

`owned_vulkan_world_frame.py` now persists one full-candidate/run/role/stage
acquisition. It records its filename before opening, actual inode before native
acquisition, each command before delivery and its validated receipt before the
next chunk. It first pins the actual native GPU-context birth through a fresh
inspection, before arming any capture. A lost read followed by a replaced Context
cannot use the replacement's empty counters as the old source's cleanup.
The metadata-only completed-frame lease now has the same preflight guarantee;
complete legacy transcripts remain readable, while a lost unbound legacy read
is retained rather than adopted without an original source birth.

The private compressed transcript retains complete frame/storage originals.
Chunk transport summaries retain the original header, exact data size/SHA and
whole original-packet SHA without duplicating all PNG bytes into JSON state.
Archived reading reconstructs each original chunk packet from its recorded PNG
slice and checks that original hash. This is explicitly transport summarization,
not a newly minted original observation. The original full PNG and decoded pixel
hashes remain bound to the actual frame. All state limits fail closed.

Lost read/chunk/release responses, failed persistence and host reconstruction do
not authorize another acquisition or another release. Fresh inspection observes
real consumer/buffer/PNG absence. Native release preserves the original host
evidence PNG and ledger; explicit artifact removal independently verifies its
owned inode and actual path absence after fresh native retirement. No method
erases the owner's metadata or substitutes for the full feature's three-second
quiet window. The outer Graphics owner must retain its private owner paths and
compose scene/preferences/samples, actor and full journey cleanup.

## Local verification

Twenty-seven selected no-build tests pass: six new world-frame protocol cases,
two new iOS HTTP/AFC SDK cases and nineteen completed-frame/lease/transport
regressions. Original GPU/SDK sources are synthetic; Node executes the actual
probe. Positives include multiple original PNG chunks, exact RGBA/PNG hashes and
separate native clocks. Counterexamples cover missing fences, retained copy
allocations, ignored/lost chunks, failed intent, corrupted PNG/pixel metadata,
wrong offsets/process/extent/format, late evidence, closed input grammar and a
retired queued callback. These do not qualify native compilation, actual Vulkan
allocation/layout/barrier behavior, device pixels or product functionality.

New shared version-1 registry entries are `native-vulkan-world-frame` and
`native-vulkan-world-storage`. The E2E-only backend readback interface, original
frame ticket and separate source/storage parsers must be reconciled as a unit
with parallel platform changes. No moving Phone/Pico work was imported.

The durable ownership packet passes 37 further selected no-build cases across
the new owner, preflight/legacy lease cases, original frame/PNG protocol and iOS
transport. Counterexamples include Context replacement after a lost frame,
changed chunk-header digest, foreign file/candidate/role, lost release without
resend, failed durable writes and preserved original transcript prefixes. All
native/GPU positives remain synthetic. New contracts are
`owned-vulkan-world-frame: 1` and `vulkan-world-chunk-summary: 1`.
