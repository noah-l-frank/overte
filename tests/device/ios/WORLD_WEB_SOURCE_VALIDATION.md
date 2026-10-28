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
observation 14 now returns within its unchanged real API25 boundary in 12.494
seconds; this is one observed call, not complete timing qualification. All 605
original files and 7715 source/launcher/reference pins remain unchanged, with
owned processes and new threads gone. No complete World Web acceptance follows
from this failed attempt; its image and cleanup failures remain retained.


## Phase-stable image baselines

A repeated observation in a changed-image phase now selects the latest
qualified image from an earlier ticket. It retains that original comparison
through subsequent reads of the same phase. Image-only phases keep their
nearest qualified predecessor. Failed or incomplete samples cannot supply a
baseline. The original pixel threshold, marker exclusion, fresh frame custody
and before/after causal checks are unchanged.

Four connected actual Node/page/PNG cases pass in 91.043 seconds, preserving 729
original files and 7726 source/launcher/reference pins. Repeated same-page
images qualify against the same earlier image with distinct fresh frame IDs.
Missing prior images and a genuinely unchanged subject on a new changed-image
ticket still fail. The earlier 605 failed-run originals remain unchanged; owned
processes and new threads are gone.

The changed full19 attempt passes the former image failure and subsequently
fails its unchanged API25 boundary during Primary foreign-URL input, while
re-decoding Source history after capture. Its 791 originals remain retained and
unchanged; this failed run supplies no whole-journey or timing qualification.
The successful focused cases retain declared native/SDK/GPU/OS models.


## Passive current acquisition and primary errors

`WorldWebActions.current()` enters the existing Source append boundary only
for capture and its frame read. This passive variant permits Source-WAL
transitions while retaining the input WAL, including its prior absence, in the
immutable original census. Ordinary input rounds retain their existing mutable
input-WAL boundary. No action WAL, input delivery or scope mutation occurs in
the passive round. Newly acquired frames avoid a second semantic validation;
old originals still receive complete byte, inode and membership checks.

If an operation and its mandatory Source exit validation both fail, the same
original exception survives with a constant secondary-failure note. Exit-only
failures still reject the round, and all temporary round state is cleared.
The inventory, header, state-digest and compare-and-swap checks remain active.

All 15 selected host cases pass in 74.700 seconds, retaining 1,059 original
files across 27 roots with 7,762 source/launcher/reference pins unchanged. They
cover fresh frames, foreign navigation through normal inputs, unknown files,
changed original bytes/inodes, header drift, input-WAL birth/replacement/change
and original exception identity. Owned processes and new threads are gone.
Two earlier test expectation failures and the corrected 12-case pass remain
retained separately; no expected product measurements were substituted.

The subsequent full 19-step attempt fails after 485.408 seconds. Its explicitly
retained exception-context chain establishes API25 exhaustion during Primary
foreign-URL input: the next native acquisition saves its original-clock query
and reaches the unchanged API guard. All 789 originals and 7,762 source pins
remain unchanged after owned processes and fixture threads stop. This does not
qualify the whole journey or attribute earlier flattened failures to the same
inner cause. Native/SDK/GPU/OS behavior remains modeled and native compilation
and devices remain unverified.
