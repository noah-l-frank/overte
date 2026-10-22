# Original native Snapshot file-job lifetime

The gated `IOSSnapshotFileWorkObservation` observes the existing native
`iosSnapshotFilesRequest` worker. After the actual native semaphore accepts a
read, the real queued Qt functor captures one responsibility token. The source
ledger holds only a weak reference. Actual GUI/queue/functor/body captures may
keep it alive; the getter never retains it and no timeout releases it.

The source records the exact accepted read-only query, native queue and body
entry times, the actual existing QSaveFile publication result, normal body
return, scope exit and independently observed weak expiry. Publication and body
return do not imply functor destruction. The semaphore release still follows
the existing worker scope. Native storage is read once and existing output
operations keep their order and short-circuit behavior. Observation is gated
by both iOS and the feature-test configuration; the ordinary producer's
existing dedicated iOS E2E gate remains in force.

The separate passive `feature-ios-snapshot-file-work` getter supplies a native
source birth, sequence, PID and before/after clocks. All known matching-prefix
jobs remain in its bounded history (1,024 jobs and 1.5 MiB source bytes); there
is no history trimming. Capacity, clock or lifecycle inconsistency fails the
source. File requests carry the existing 16-hex controlled run prefix; full
candidate/run/session ownership remains the canonical outer owner's duty.

Worker events may happen after a preceding getter copies its rows but before
that getter's actual after-clock. The validator preserves that original
bracket: newly visible worker events may begin at its before-clock. An event
before that original bracket, rewritten query/time, missing known job, reused
source nonce, clock discontinuity or resurrected weak owner is rejected.

`snapshot_file_work.drained` requires complete originals, exactly one actual
job for every retained query, successful original publication, normal return,
scope exit and actual weak expiry of every matching known job. It does not
derive file presence/absence from that publication, query receipt or worker
retirement. The independent original file packet and manifest remain required.
The fixture, one-read-per-nonce probe and existing AFC factory expose this
separate version-1 source with an explicit 2 MiB bound. Generic decoder and
default native observation channels retain their existing limits.

Eight no-build host checks cover actual Python weak capture retention after
return/finally, release of the last cached functor, events within the preceding
read bracket, immutable histories, missing/failed originals, the actual native
callsite wiring, actual Node probe, fixture and AFC factory. Native workers and
Qt destruction are modeled; the C++ source remains uncompiled and device tests
are unexecuted. Durable whole Snapshot ownership must still retain these
originals and join repeated fresh quiet reads before final retirement.

The separate `snapshot_file_work.retired` error-path check requires the actual
entered/finally boundary and last weak-capture expiry for every retained query
and all observed jobs. It also accepts a real publication failure or a body
that threw before publication/normal return. The successful `drained` query
check remains unchanged and still rejects those originals. Neither error-path
retirement nor its callback exit establishes any output bytes or path absence;
the enclosing cleanup retains query and partial-file responsibility. Three
additional no-build host cases exercise real throwing/cached functors and
normal false-publication branches, and reject missing, foreign, unentered,
unfinished, live or duplicate job claims.

## Durable original packet ownership

`SnapshotFileWorkPacket` reuses the exact owned native-query admission, one-send
intent, original clocks and historical recovery of `SnapshotOwnedPacket`. The
original file-work DTO and its bounds remain version 1. Its separate private
owner/frame/part formats are version 1; no existing owned-file frame changes.

The exact original raw reply is retained in the shared closed
`snapshot-file-work` segment profile. Only `raw` and the actual primary/actor
role are admitted. Each query owner reserves eight frame indices in its own
role namespace, up to the existing 128 owners/1,024 indices. The native raw bound
needs at most four parts. Every actual part retains planned/opened/saved inode
responsibility and stays below the unchanged 1 MiB frame limit. The small frame
references these original bytes and acquisition clocks; it does not duplicate a
large decoded ledger into the metadata journal.

Complete raw bytes after a lost flush can be read without another query, AFC
read or part write. Incomplete parts remain owned. Their actual partial prefixes
are frozen after failure, and later same-inode changes fail historical validation.
The original body-frame write is also one-shot; complete opened body recovery
uses the existing original-file adoption rules. Historical readers validate the
actual original bytes only and cannot issue native operations.

Host tests exercise the 1,024-job ledger with real weak callback holders and
multiple actual private files. The native work/clock boundary is explicitly
modeled. These tests establish neither native compilation nor physical timing
qualification. The enclosing Snapshot cleanup still needs fresh original empty
manifests, original file-read job retirement, and the required quiet window.
