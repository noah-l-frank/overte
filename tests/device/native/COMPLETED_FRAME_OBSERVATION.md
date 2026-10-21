# Original fence-completed iOS Vulkan frame metadata

These version-1 sources provide original frame/allocation/draw/lifetime metadata.
They provide neither pixels nor a Graphics verdict. Native C++/Objective-C++ is
uncompiled; devices remain untested. Full iOS Graphics is still in progress.
The separate [Vulkan world-frame action](VULKAN_WORLD_FRAME.md) now uses the same
original ticket/fence with its own versioned PNG/storage contracts. The existing
metadata-only action and its closed packets remain unchanged.

## Original producer

The default-off E2E build adds one explicitly requested capture group to the
existing GPU context/frame. An actual primary mono forward frame records its
original camera position, quaternion, numeric projection and native clock.
The dedicated Vulkan counter advances immediately after actual `vkCmdDraw` or
`vkCmdDrawIndexed` calls. Rejected/unsupported CPU draw opcodes cannot advance
it. Original callbacks bracket forward/mirror batches and retain actual API draw
deltas; haze attribution records the existing bound haze/light state. This is
issued work, not proof of visible shading. Independent effect pixels are required.

The tone-map callback reads actual GPU framebuffer objects. Extents are recorded
only after `vkCreateFramebuffer` returns `VK_SUCCESS`, tied to the current handle
and backend owner. The active target additionally requires its actual bound
render-pass framebuffer and issued Vulkan viewport/command-buffer pair. No
observation framebuffer is created, requested texture sizes substituted, product
readback TODO implemented, or Vulkan source labelled OpenGL.

Recording and successful submission do not publish a completed frame. The
existing display fence wait must return `VK_SUCCESS`; resize/teardown use that
original fence's actual `vkGetFenceStatus` result. No additional device wait or
product recovery is added. Native record/begin/draw/submission clocks and
`fenceObservedEpochMs` remain unchanged. The last field is native time when
completion was observed, not a hardware GPU timestamp or host/AFC file time.
Repeated reads return the same original frame and clocks.

## Lifetime and retirement

The original frame, queued batches, trace/Args copies and fence callback retain
one capture-group ticket. `callbacks` is a 0/1 count of retained capture groups,
not the number of individual lambdas. The final actual destructor clears original
trace metadata before decrementing it. GPU submission responsibility is separate.
Losing a submitted frame's fence proof leaves `gpuPending` sticky; weak-pointer
expiry or a release ACK cannot clear it.

Release permanently retires the acquisition nonce and clears the stored packet.
Fresh inspect must show retired, not present, zero capture groups, no GPU
responsibility and zero source-owned metadata bytes. An old command cannot rearm
the nonce. The 4096-entry retired set is bounded without forgetting ownership.
New acquisition cannot replace an active slot or older undrained capture. Whole-run
cleanup still needs the common quiet window and, when applicable, actual old-PID
death. Resetting the source is not cleanup.

## Closed existing transport

The command has exactly version-1 `schemaVersion`, iOS-prefixed `commandId` and
`requestId`, action `feature-completed-frame`, and `read`/`release`/`inspect`
operation. It accepts no expected scale, settings, view, backend, frame index or
source version. The native Test interface reads the existing GPU context; the
existing probe writes untouched originals to `feature-completed-frame.json`.
Pending native reads use that same slot; the host sends one command. Release
cancels the matching probe timer and rejects its queued closure before another
source read. Native retirement separately prevents late rearm.

`native_completed_frame.py` validates original nonce/PID/context/cursor, native
clock order/freshness, closed shapes, recorded geometry and issued draw counts.
Storage separately observes actual retained resources. The reader requires a
caller-owned intent callback before delivery and never resends a command ID.
The full coordinator must supply durable ownership; this low-level component
alone is not a feature owner or evidence publisher.

`completed_frame_lease.py` now supplies that durable acquisition owner through
the canonical iOS Graphics runtime. A private binding/run/role/stage transcript
records each command before delivery, retains compressed immutable originals,
and restores original instance/sequence/clock continuity across host objects.
There is at most one active capture. A lost read cannot be acquired again;
a lost release can only be followed by fresh inspection. File CAS failure,
foreign bindings, reused frame IDs, retained groups and missing GPU completion
leave ownership unresolved. Release is sent once, then at most 81 bounded
inspections establish actual absence. This individual lease drain does not
replace the whole feature's three-second cleanup quiet window. The transcript
remains available for that owner; this component does not erase it or publish
a feature verdict.

Seven additional no-build lease tests pass for host reconstruction, missing
fences, lost release responses, CAS changes, failed persistence, foreign scope
and reused frame/cursor evidence. These synthetic originals qualify ownership
logic only.

New acquisitions now persist an original native-source inspection before the
first frame request. Context birth/cursor continuity is therefore available even
if the later frame answer is lost. Empty storage from a replacement Context
cannot retire the old responsibility. Complete legacy transcripts remain
compatible; an old lost read without any original birth is explicitly refused
for adoption. This hardening keeps the version-1 serialized shape unchanged.

`FeatureObservation.completed_frame` uses existing iOS HTTP/AFC and an independent
native clock. `IOSGraphicsRuntime` constructs it through the canonical candidate/
existing-session gate. Native frame times, host acquisition and later original
screen captures must remain separate. No Graphics triple is advertised here.

## Reconciliation and verification

New shared version-1 contracts are `native-completed-frame`,
`native-completed-draw-trace`, `native-completed-frame-storage` and
`recorded-render-view`. Numeric view validation derives from frozen Phone
`fe4684bf46585088370b3a328a738f147e670b97`. This Vulkan issued-draw trace is distinct
from Phone's CPU draw-opcode/world-PNG trace; preserve their separate semantics
when reconciling headers/registries. No Android mirror-enablement or functional
renderer changes are imported.

Eighty-one selected no-build source/parser/probe/iOS transport regressions passed.
New counterexamples cover missing fences, ignored release, retained consumers,
clock skew, altered backend/allocations/pose, CPU-opcode substitution, partial
originals, PID replacement, failed intent and late queued reads. Node runs the
existing probe; native GPU and SDK positives are synthetic. Native compilation,
Vulkan commands/fences, UIKit and physical pixels remain unverified. Existing
compiler-based framebuffer lifetime tests are explicitly not run here.

Five existing no-build rendering checks passed: rendering integration inventory,
Application graphics diagnostic boundary, Vulkan backend selection, physical
buffer-safety source contract and pending-output presentation source contract.
The existing scissor-state source contract fails because it expects legacy
`_iosScissorEnabledDraws`/`_iosScissorDisabledDraws` members. The same failure was
reproduced against an isolated copy of the unchanged committed baseline. This
pre-existing check is not weakened and is not reported as passing.
