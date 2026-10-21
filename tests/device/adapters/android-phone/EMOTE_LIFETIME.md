# Phone original Emote work and quiet-window owner, version 2

`PhoneEmoteLifetime` joins each role's durable source v3 frames to actual
manager-thread timer/callback observations. It implements no cleanup input and
advertises no full Emote capability. Images/fixture lifetime, separate actor
publication, phase-change recovery and whole-run retirement remain required.
Native instrumentation remains uncompiled and devices untested.

## Closed original records

Construct with a real `PhoneEmoteSources` under its existing held source lock.
The exact private header is `emoteLifetimeVersion:2`, `runId`, `fixtureUrl`, `role`,
actual `binding`, `artifactRoot`, `payload`. Primary and actor have separate
`phone-emote-<role>-lifetime.json` files and independent original query histories.
Existing 64 KiB atomic/private metadata limits remain unchanged; overflowing
original records fail without truncation or successful publication.

Payload contains one exact `phase`, `records`, `pending`, `window` record.
Phase is `ready`, `reading` or `complete`. At most 40 original records are stored.
Reading intent precedes actual source/worker acquisition; pending is exactly
`afterRevision`, `index`. Interrupted records remain unavailable through both
same-object reuse and reconstruction. A failed write latches the live owner;
unknown/lost evidence cannot be replaced with an empty success inventory.

Each completed record is exactly `source`, `work`, `providerAfter`, `epochMs`,
`hostEpochMs`, `monotonicMs`. Source is the immutable `{revision,sha256}` frame
reference. Work is the complete original native Script-work packet, with its
own request/capture times, cursors, original selected membership/code, actual
timers/callback counts and complete all-known worker membership. ProviderAfter
is a new original fixture phase after both acquisitions. The current exact
cleanup ticket must match all source/provider originals. Host/device clocks
are never substituted for each other.

Original source files are reopened through actual manifest/file identities and
digests. Local historical replay uses local ownership guards, bracketed by
actual candidate/process guards; it performs no native requests and retimes no
facts. Durable source/input memory substitutions cannot replace original header
or file authority. All original worker packets replay their existing retirement
and strictly advancing counter checks before a new worker read.

## Actual selected worker and stable window

The real selected Script manager comes from the original configured-root/
submitted-code/Rig source group. The later worker packet must independently
match that actual manager assignment URL, load generation/time and submitted
code, native birth and PID. Complete all-known membership must agree with the
earlier original Script read, compared by actual instance identity rather than
an unspecified array order. A requested subject or zero counts cannot stand in
for an actual selected worker. No expected counts, pose or source is sent.

A qualifying observation requires actual inactive Rig override, actual closed
SDK tablet and empty current controls, and an engine not currently evaluating.
For an independently selected compiled source, native work v2 must prove the same
actual compilation and contain the earlier Script compilation prefix unchanged.
Its actual selected-function timers and active callbacks must be absent. An
inactive selected timer is still a retained map entry and fails. Unclassified
pending timers or active callbacks also prevent selected absence. Known foreign
default-script timers are preserved and never declared absent or cleared.

Legacy standalone originals with native work v1 remain readable and still require
the whole actual timer map and active callbacks to be empty. A compiled shared
source cannot downgrade to a legacy manager-wide empty result. Legacy compiled
source/work-v1 records remain insufficient and cannot be relabelled as success.
Normal default Script signal connections are not declared globally absent or removed.
Version 1 standalone lifetime headers remain readable after full original
validation; subsequent writes use version 2 without replacing any raw fact.

The quiet window requires at least three observations, at least three seconds
of actual host monotonic time AND at least three seconds between original native
worker captures. Rig/history identity, actual native call/override counters,
lifecycle counters and consumed-input cursor must remain stable. Busy originals
are retained; only a later actual clean suffix may start a new window. A new
native call during an otherwise idle window restarts that window. Advancing a
host clock alone, a frozen monotonic clock or fresh envelopes over old work
cannot complete it.
Version 2 also pins actual selected-function cumulative signal/timer invocation
and timer-registration counters, plus all unclassified activity rows. A callback
or short timer that completed between reads restarts the clean suffix even if
current active counts are zero. Changes in independently identified foreign
default-script activity do not erase a valid selected-function quiet window.

`wait(sleep=...)` obtains new original observations, up to 32 iterations at 250 ms,
under a 30-second total monotonic limit. Each acquisition retains a five-second
bound and 1.5-second native AND fixture freshness at final delivery, including
independent monotonic age floors, guards, file validation and journal work.

## Retirement and remaining whole-feature join

`retire` requires a recomputed complete window and obtains another new source/
worker observation before removing only its exact lifetime journal. Late actual
activity invalidates a prior green window and preserves ownership. Source files
and native history remain intact. General Phone teardown attempts base cleanup
but refuses success while either lifetime role remains.

This proves only the documented selected-function/Rig/current-UI subresources.
The full feature owner must still join actual ordinary restore/close input
causality, fixture/marker and capture/browser resource release, relevant UI
lifetime, independent actor evidence and final run/host-journal retirement.
No global absence of every future application callback is claimed. The lifetime
helper cannot replace image evidence or declare whole-feature cleanup success.

Device-free counterexamples cover real Python ownership/joins with synthetic
native boundaries: retained active/inactive timers, active callbacks/evaluation,
ignored cleanup, late activity, open UI, native/source/fixture mismatch, old or
reused work, lost results/guards/commits, replaced/missing originals, separate
roles and fresh retirement. These validate test logic only.
