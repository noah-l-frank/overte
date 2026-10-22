# Original Emote Rig measurements, version 2

`adapters/emote_rig_measurements.py` joins original source identity and native
Rig history. It accepts no requested animation, Sit variant, progress, pose or
restoration verdict. It supplies no full feature capability. Pico remains at
three complete source/host adapters; native compilation and all device qualification
remain pending.

## Inputs and provenance

The exact source group contains `rootsBefore`, `script`, `native`, `rootsAfter`.
The two original configured-root reads bracket submitted Script code and the
original native Rig acquisition. All packets must agree on actual PID/native
birth; nonces, clocks and complete original shapes are revalidated. The source
profile joins the original manager assignment, complete membership and actual
UTF16 code identity, as specified in [the root contract](SCRIPT_RESOURCE_ROOTS.md).
All acquisitions must fit the existing 1.5-second freshness window. Later owning
transports must also enforce an independent monotonic age floor.

The current native packet requires an actual later Rig evaluation beyond its
native request fence, animation history version 2 and its latest original
sample. That sample must match the current override generation and active flag,
have an evaluation no later than current Rig state and be less than 75 ms old.
The native history samples every 75 ms; equal evaluation counters additionally
require identical actual final joint values. History is never retimed.

`playback(group,native_barrier,pid,epoch)` joins a pre-input original native
barrier to exactly one later override. The observed clip URL must resolve under
the actual assigned Emote source's animation directory. Its actual URL selects
one of the nine non-Sit clips or three Sit variants. Original file and Qt qrc
assignments resolve the reviewed relative resource directory. Generic
`urllib.urljoin` cannot resolve qrc URLs and is not used here. The original request must follow source
submission and the barrier. Two or more loaded evaluated frames must advance
their actual clip counters/frame positions and change final joint poses.
Quaternion sign reversal alone is not movement. A native call without loaded
playback, a frozen clip, a frozen pose or a foreign resource fails.

Compiled source profiles additionally require [actual consumed FBX provenance](ANIMATION_SOURCE.md)
for every advancing original frame and the active current clip. Actual loaded
URLs select the fixed twelve byte pins; another file at the correct URL fails.
The resource/model identity and original consumption time remain unchanged
throughout a playback generation. A cache hit may predate its input. Completed
playback still checks its original data rather than borrowing a current cache.

The actual [native Script caller](ANIMATION_CALLER.md) must match the original
selected manager instance, physical assignment URL, load generation/time and
submitted code. Its original invocation must follow the pre-input native
barrier. Missing, null, legacy or foreign origin fails even when the clip URL,
loaded frames and changed poses otherwise match. Completed playback additionally
requires the selected original restore caller. Restoration joins also require
its advancing caller cursor, and ordinary cancellation requires the original
restore invocation after the cancel barrier, not merely late queued execution.

The returned proof has exactly `emoteRigVersion:2`, `kind:"playback"`, complete
original `group` and `barrier`, measured `state`, original `event`, original
`frameSequences`, original `restore` or null, and `inactiveFrameSequences`.
The five measured state fields are `animation`, `sit`, `override`, `poseProgress`
and `restoredBeforeNominalEnd`. An already completed clip may establish past
playback, but its current state is idle. Panel visibility needs independent
original widget/visibility observations and is not supplied by this join.

`poseProgress` is the fraction of the nonempty original pre-input joint set
whose actual current final pose changed. Joint counts must agree in the same
Rig. The existing antipodal-quaternion-aware pose comparison supplies the
movement threshold. Clip position establishes advancing playback separately;
it never supplies this fraction. For example, one changed joint out of four
reports 0.25 even when the actual clip is halfway through its frame range.

## Restoration and continuity

`restoration(group,played,pid,epoch,native_barrier=None)` first recomputes the
complete original playback proof, including exact types. It then requires the
same manager/source assignment/code, advancing original native clocks/counters
and actual Rig evaluation,
the same Rig/history birth, immutable surviving history prefixes, and a current
inactive override with an original restore followed by an inactive evaluation.
Unseen dropped calls cannot be silently adopted.

An optional pre-input native barrier must itself observe that override active.
The new restore must follow both its native time and call cursor. A restore that
already happened before an attempted cancel cannot prove cancel. Early restore
is derived only from original request range/rate and original invocation and
execution times, using the existing 250 ms margin. Both the actual Script-call
interval and native Rig-event interval must end before that margin. Queuing an
override late must not make its natural timer appear to be an early user abort;
an early Script call with late actual native restoration also cannot succeed.
Natural completion cannot be relabeled as early.
The returned exact restoration proof retains `emoteRigVersion`, `kind`, `group`,
the recomputed `played` proof, the optional original `barrier`, measured `state`,
original `restore` and original `inactiveFrameSequences`.

`replacement(group, native_barrier, pid=..., epoch=...)` additionally verifies
the ordinary final override flow. The native pre-input barrier must observe an
actually loaded active Sit1/2/3 from the selected source. A new selected native
restore must follow that barrier, precede the new override, and genuinely end
the old Sit early under both original time intervals above. The new override
must have a new generation, different actual loaded URL, advancing frames and
moving poses. An instantaneous stop/start need not render an intermediate idle
frame. The returned playback proof keeps its v2 wire shape; original groups
retain every old/new event needed to recompute these checks. A play from idle,
replacement of another gesture, missing/foreign old restore, natural delayed
old restore or wrong consumed old data fails.

## Required owning adapter composition

These functions are pure bounded joins and perform no input, transport, waiting,
fixture registration or cleanup. The complete Pico adapter must durably bind
run/role/process/candidate, original phase history, pre-input barriers, original
normal UI actions, independent actor reads, current avatar images and original
timer/callback/input ownership. A successful proof alone cannot establish the
input's cause, peer delivery, visible avatar rendering or complete cleanup.
Malformed/foreign evidence fails; no caller may retry a product input to repair
missing evidence. Quiet-window and actual resource absence checks remain
mandatory before retirement. Historical proofs never satisfy a fresh read.

Device-free counterexamples execute this Python join against synthetic original
source boundaries. They establish test logic only, not product behavior.
