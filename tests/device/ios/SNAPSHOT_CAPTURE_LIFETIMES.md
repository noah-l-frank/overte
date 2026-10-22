# Original native Snapshot capture lifetimes

`feature-ios-snapshot-captures` is a closed source query through the existing
guarded HTTP/AFC transport. The passive native observer records every actual
`Snapshot::beginCapture` attempt, acceptance/rejection, native status enqueue and
delivery, and successful cancellation/delivery. The observer adds no capture,
timer, callback, deletion or product decision. All additions are gated by the
dedicated iOS feature configuration and `--testScript`; disabled event macros
evaluate no arguments. Existing wire contracts remain unchanged.

Each capture has its own native birth and weak `SnapshotCaptureRequest` owner.
The reader samples its real atomic state and announcement without retaining it
beyond the read. Renderer lambdas, posted Qt callbacks, workers and watcher
connections already retain the actual request; their live references therefore
prevent weak retirement after success or cancellation. The observer also
registers weak QObject identities for the real animated timer, GIF watcher and
360 conversion watcher. It records actual QObject destruction separately from
the transient QPointer-clear interval. Native activity samples include real
request membership, secondary-camera timer/frame flags and animated capture,
encoding, frame and timer state. Counts and states are observations, not inputs.

Only actual `snap_<digits>_<count>` request IDs are exposed; other callers' IDs
are redacted. Paths, titles, image bytes and error strings are not exported.
The fixed observation file uses private atomic compact publication. The source
is bounded to 64 capture births, 256 resources and 1,024 events; exhaustion or
lost membership prevents qualification. No history is silently discarded.

The strict decoder preserves native bracket clocks, original births, immutable
event prefixes and weak death. A dead source cannot revive; a completed or
cancelled live request cannot become active. `drained()` requires all request
references expired, all observed QObject destruction delivered, and real native
activity empty. Native success or a cleared application pointer is insufficient.

`pending_cancellation()` joins the unchanged
[Script/timer originals](SNAPSHOT_WORK.md) to native before/after originals from
the same process and run. It requires the actual capture ID, both live unfired
350 ms/60 s timers, the real cancellation entry/return/finally after the pending
original, complete native begin history excluding that ID, and fully drained
final Script/native work. Idle cancellation, a fired delay, thrown cancellation
or foreign process cannot satisfy the join. Its source-only result explicitly
requires the separate durable normal-input owner and original owned-file
absence; it does not count a successful capture/export or complete a journey.

Ten no-build checks use real host weak references, actual callback retention,
private transport codecs, genuine probe dispatch and modeled native producer
facts. They cover queued owners after cancellation, timer destruction gaps,
active secondary/GIF work, altered history/clocks/PID/births, weak resurrection,
and early-cancellation counterexamples. Native C++ remains uncompiled; no SDK,
device, simulator, build, installation or laboratory is accessed.

Remaining whole-feature work includes actual normal capture/cancel and system
permission/sheet recipes, original encoded files and image comparison, Photos
destination bytes and deletion of only owned assets, an independent external
share receiver, authenticated upload/body receipts and paired final quiet
cleanup. Current add-only Photos permission does not expose a saved-original
read API. Existing private capture files and native export success cannot fill
that independent destination boundary. These components advertise no complete
Snapshot capability.
