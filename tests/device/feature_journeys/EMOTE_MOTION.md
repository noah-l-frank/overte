# Original native Emote motion evidence, version 1

This private evidence format is implemented and host-tested. Its common journey
integration and complete Phone Emote facade remain pending. It registers no
feature capability. Native instrumentation remains uncompiled and all clients
remain untested on devices.

The bundled Phone script submits non-looping 60 FPS playback and restores after
the actual loaded frame count divided by 60. Static FBX v7300 curve metadata
contains at most 44 values for Waving and 64 for Clapping: about 0.73 and 1.07
seconds. Three sequential image/source RPCs plus the generic half-second stable
window cannot be assumed to fit. These source figures explain the scheduling
problem; they are never substituted for measured native duration or success.

`emote_motion.packet(call, before, after, role=...)` copies existing original
source frames. It does not send input, acquire a new observation, replay an
animation or redate packets. `read(bytes, call=..., role=..., epoch=..., state=...)`
recomputes the original proof and checks its five native Emote facts against the
current public state. Both functions reject invalid proofs. The caller must own
and reopen the actual native pre-input barrier and its role's current source
files; a generic earlier frame or another role's effect is insufficient.

The closed UTF-8 JSON file is bounded to 2 MiB and contains exactly
`emoteMotionVersion: 1`, `role: primary|actor`, `call`, `before`, `after`.
`call` is the complete current versioned `feature.emotes.act` input. Each frame
part contains exactly `group`, `phaseBefore`, `phaseAfter`, `epochMs`,
`hostEpochMs`. These are unchanged originals from source acquisition; platform
UI data, target selectors, ownership bindings, computed statistics and expected
states are excluded. Original fixture packets must retain the same run, birth,
activation history, input/ticket and active phase throughout. Original native
root requests must follow the actual fixture activation.

The existing Rig measurement version 2 verifies configured compiled code,
actual V8 caller, exactly one new override after the native input barrier,
process/Rig/history continuity, actual loaded advancing clips, changed poses,
and the actual consumed pinned FBX bytes/resource/model identity. The motion
reader additionally requires the same selected compiled source before/after,
current active playback, the measured selected clip matching the normal input,
60 FPS without looping, and at least three original native frames with strictly
advancing capture/evaluation/clip cursors. At least two adjacent frame pairs must
change real joint poses, treating antipodal quaternions as the same rotation.

The required native span in milliseconds is
`max(150, min(500, observedNominalDuration / 4))`. The duration is derived from
the native override's actual range and FPS, joined to actual loaded data, never
from the requested name or this static audit. All qualifying frames must remain
within 1.5 seconds at use. Native epochs retain their clock; the original
native/host acquisition pair plus actual elapsed host time bounds age. Host
acquisition may be at most 250 ms in the future. Completed historical motion
cannot qualify a current active checkpoint.

The returned report summary contains only the format version, actual native
sample count/span, required span, nominal duration and first/last native frame
sequences. It excludes raw packets, URLs, paths, process IDs and private fixture
metadata. Store the original file with the existing private artifact policy and
delete it during verified cleanup. A public descriptor uses existing `kind:
file` fields, the current public sample sequence/time and owned action ticket.
The descriptor's acquisition time must come from the original source frame.

The native proof supplies only motion provenance. Actual required PNG bytes,
image source/marker/body-pixel checks, independent actor facts, public source
freshness, lifecycle continuity, deadlines, and full cleanup remain mandatory.
Do not loop/slow clips, repeat an acknowledged input or forward primary facts to
the actor to fit a checkpoint. Baseline, idle/restoration, negative and cleanup
windows retain their ordinary stable-sample requirements.

Host counterexamples cover ignored/old overrides, unknown/foreign compiled
callers, wrong consumed bytes/birth/phase/ticket/name, frozen poses/clip frames,
duplicate times, too few frames, insufficient spans, stale acquisition/native
frames, completed playback, malformed/oversized/duplicate-key/expectation-bearing
files and public facts contradicting the original measurement. They qualify
test logic only, not product functionality or device performance.
