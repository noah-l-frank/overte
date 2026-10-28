# Original clock floors and bounded transcript validation

The Places model and World Web transcript readers accept an optional
`native_before_floor` containing an actual, retained native feature observation.
They copy and validate its complete original packet and process identity before
issuing a source query. This replaces only the ordinary before-clock query;
terminal clocks are newly acquired. Both the source acquisition and the interval
from the retained floor to the final clock must remain below 1.5 seconds. The
ordinary calls retain their previous two and three clock acquisitions.

This argument is a before bound, never a current time. Its enclosing owner must
retain the actual raw original and acquisition, prove that they belong to this
acquisition, and include them in historical validation. A valid native packet
alone does not establish that outer ownership. Places records the digest of the
copied floor in its acquisition metadata. No wire schema changes.

`world_web_source.validation_round()` reuses at most 256 successful pure
transcript validations within one synchronous context. The key includes the
actual packet, command, PID and predecessor. Freshness is checked again on every
reuse. Mutated bytes, a different predecessor or a later epoch cannot reuse a
proof. Nested rounds share the entered context; leaving the outer round resets
it. This stores no original files, acquisition results, returned objects or
transport responses, and does not remove durable writes or ownership guards.

Six focused host tests cover both original-clock paths and pure validation
reuse over the committed native/model/transcript fixtures. They reject foreign
PIDs, old floors, mutated packets and warm-proof freshness failures. Existing
source/model regressions also run. These are modeled source tests, not native
compilation, device results or a physical timing acceptance. A positive short
CPU input sequence has not established reliable timing for the full 19-step
World Web journey; that whole adapter remains incomplete.


`PhaseWitnessPublisher` also accepts an optional synchronous `decode_context`.
Only its literal publication decoder enters that context. The World coordinator
selects the actual bound Observer validation round, so one journal decode shares
its current Source/peer/Scope checks. The round checks original owner headers,
file bytes/inodes and membership again before exit. Writes and HTTP publication
remain outside it; a new original-read census executes the original readers
again. Default and historical archive readers keep their literal decoding path.
No wire version, source freshness rule or operation deadline changes.

All 22 selected shared publisher cases pass in 1.679 seconds, including the
17 existing regressions. Four connected World cases pass in 39.540 seconds.
They retain 94 and 547 actual files across 26 and 14 original roots respectively,
with source pins unchanged and no remaining owned processes or fixture threads.
They reject changed source bytes, inode replacement, added unowned files and
owner-context drift, including a mutation during round exit before a WAL write.
These host cases exercise real HTTP/files and declared native/SDK models; they
do not establish full-journey completion, native compilation or device timing.

The changed-source public 19-step attempt subsequently fails after 262.825
seconds at the mandatory subject-pixel change check. The earlier Actor
observation14 now returns within its unchanged real API25 boundary in12.494
seconds; this is one observed call, not complete timing qualification. All605
original files and7715 source/launcher/reference pins remain unchanged, with
owned processes and new threads gone. No complete World Web acceptance follows
from this failed attempt; its image and cleanup failures remain retained.
