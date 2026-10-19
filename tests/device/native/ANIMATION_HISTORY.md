# Actual Rig call and evaluated-pose history, version 1

This E2E-only, default-off source supplies original native facts needed for short
Emotes. It does not fix the current draft's ordinary-override/chooser assumptions
or the original tablet Sit end-frame concern, and enables no full area producer.
Native C++ is uncompiled; host cases establish reader logic only.

The actual `Rig::overrideAnimation` records an event after its ordinary state
update, with the original URL, framesPerSecond, loop, firstFrame and lastFrame.
An actual active-to-inactive `Rig::restoreAnimation` records restore after its
ordinary update. No test request, UI ACK or getter increments those call counters.
These calls alone do not prove an animation loaded, executed or visibly changed.
They record no inferred timer/button/cancel cause; those require a separate
ordinary-input/source/lifecycle join.

Actual positive-delta graph-enabled animation evaluation samples native final
joint rotations/translations after the animation/IK/flow pass. A saved frame
retains original evaluationSequence/capturedEpochMs, actual overrideActive and
the real clip observation where present. At most 32 joints are distributed
across the existing maximum 256-joint diagnostic. Rows carry actual joint indices,
not expected poses. Frames normally have a 75ms minimum interval; a changed
override generation or active state bypasses that interval. At most 32 frames
and 64 call events survive, with explicit dropped counters. Acquisition never
retimes history or invents missing evaluations. Zero-delta, graphless or disabled
updates cannot become newly evaluated history frames.

History has its own 32-hex instance. A changed actual animation-graph or skeleton
shared-owner identity resets that context, even in the same Rig. Weak owner
identities avoid retaining obsolete graphs/resources and distinguish reused
addresses. A history beginning with an already active unknown override cannot
provide the absent original call; a new ordinary action is needed. Readers reject
Rig/context replacement instead of borrowing a previous avatar's evidence.

The atomic existing `animation` observation optionally adds `history`, with
exactly historyVersion 1, instance, available, callSequence, overrideSequence,
frameSequence, droppedEvents, droppedFrames, events and frames. Event rows have
eventSequence, kind (`override|restore`), overrideSequence and capturedEpochMs;
only override additionally has the original request fields above. Frame rows
have frameSequence, overrideSequence, evaluationSequence, capturedEpochMs,
overrideActive, joints and optional original clip. Joint rows are index/pose;
pose is seven finite original quaternion/translation components. Clip fields
retain the existing independently loaded URL, request URL, original frame,
range/rate/loop, loadedFrames and real clip evaluation time/cursor.

`NativeFeatureObservation.read(require_animation_history=True)` rejects older
sources. Once seen, downgrade is rejected even without repeating the flag.
Surviving events/frames are immutable, all cursors/drop counts advance
monotonically and only explicit bounded trimming may remove old records.
History events can follow the latest pose evaluation but cannot postdate the
native envelope. Historical frame times must precede that actual latest pose.
The existing 262144-byte/five-second/51-read/private-result limits remain in
force; overflowing diagnostics fail rather than truncating facts into success.

`clip_run` requires a new actual override after the caller's original **native**
action/event barrier, the selected real URL in loaded and requested sources,
at least two advancing non-loop clip frames within their actual range, and
changed native joint poses. Quaternion sign alone is not motion. A fresh control
envelope with old calls/poses cannot qualify. The helper returns original events
and frames, without an expected pose or feature verdict. It cannot infer visible
rendering or peer replication; actual current image/peer evidence remains needed.

`restored_after` requires an actual later restore event and a later inactive
evaluation in the same override generation. Its optional before_nominal_end
check requires restoration at least 250ms before the original native requested
clip interval could expire; a delayed natural completion cannot satisfy that
narrow early-restoration condition. **This is not a measured button/cancel cause.**
The complete adapter must additionally correlate the original ordinary input,
loaded source profile, original native timestamps and independent peer/image
effects. Never compare iOS host epochs with these native history timestamps.
Missing/trimmed events or insufficient short-clip frames remain unavailable.

Eleven host cases cover completed short clips, ignored/native-call-only inputs,
missing/unloaded/stalled/foreign frames, frozen/antipodal poses, restore without
later evaluation, delayed natural completion, previous-action reuse, old-source
downgrade, historical retiming, graph/Rig replacement and legitimate ring trimming.
They execute no native C++, renderer or device and establish no product acceptance.
