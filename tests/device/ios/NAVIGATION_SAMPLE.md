# One durable original iOS navigation image attempt

`NavigationSampleOwner` retains one complete image attempt under a private
Worlds-specific context: installed binding, PID, run, primary/actor role,
pre/post-restart stage, original request ID and private artifact root. It does
not implement the whole Worlds operation, input journal, cross-attempt history,
independent publisher, restart or finalization.

The owner writes its private record before reading the fixture or issuing a
capture. Original sources and acquisition intent are checkpointed in the existing
bounded compressed-history format with compare-and-swap writes under the shared
`ScriptSourceLock`. A reconstructed owner cannot capture that request again,
including after an uncertain result, missing marker or phase change.

Acquisition follows the existing native architecture: a phase-consistent
read-only fixture read, native clock acquisition, actual navigation state,
original Vulkan capture, actual GPU retirement, another navigation read, final
native clock packet and another fixture phase read. The actual initial state
must already have settled at the matching controlled viewpoint. The original
challenge/scene validator independently qualifies the retained PNG and current
ticket. A phase crossing preserves responsibility and produces no image result.
A missing current visible marker preserves its original failed image and reports
`NavigationMarkerPending`; any new attempt needs another request owner.

The shared `VulkanWorldFrameOwner` still owns actual command intents, PNG inode,
chunks and callback/GPU resources. Its sidecar path here is explicitly
`navigation-world-frame-<role>-<stage>-<request>.json`. The Graphics historical
filename helper is not used. Native release is permitted only after the original
empty-slot inspection and a durably recorded owned read intent. A pre-existing
occupied native slot does not authorize release of somebody else's resource;
the failed owner remains unresolved. No release acknowledgment substitutes for
actual callback/buffer/metadata/PNG-storage absence.

`drain` observes fresh actual GPU absence through the same native source and
persists each original proof. It preserves host PNGs and all metadata. Repeated
drainage uses inspect after the original one release. A never-started attempt
can prove that no frame owner/file was created and be drained repeatedly. An
explicit parent intent records when frame ownership could have started: missing
native owner metadata after that point cannot be interpreted as no capture.
Guard/process loss, uncertain ownership and foreign/replaced files stay failed
with responsibility retained.

`archive` reads the original owned PNG and validates its unchanged context,
bytes/chunk hashes, native lifetime originals, source/phase record and challenge
result. Historical construction accepts no native/fixture/factory ports and
performs no SDK query. It retains the original clocks and returns historical
facts; it cannot turn an old image into a fresh observation or initiate cleanup.

Host tests use actual private state files, original PNG hashes/inodes, source
locks, immutable history and short real HTTP fixture reads. Native/GPU/process
and acquisition clock boundaries are modeled; they do not qualify real device
deadlines. Counterexamples cover lost capture results,
reconstruction, explicit acquisition deadline expiry, old markers, phase
crossings, ignored motion, missing owner
metadata, foreign occupied native slots, replacement files/candidates and process
guard loss. Native code remains uncompiled and devices untested. Whole-run
quiet windows, metadata retirement, new-process admission and paired OS/SDK
finalization remain separate pending work.
