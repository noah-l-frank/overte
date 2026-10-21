# Durable original iOS Graphics actor publication

`IOSGraphicsPublisher` uses only the independently credentialed actor's own
`IOSGraphicsObserver`. It advertises no feature capability and supplies no
ordinary input. The complete Graphics owner/worker must still compose it.

A newly acquired original frame creates a private `planned` intent containing
the complete original observer snapshot, unchanged public sample and exact
projection derived from that frame. Decoding revalidates original PNG bytes,
source/file/binding ownership, effect proofs and native/controller clocks. No
requested Graphics value or primary observation can fill those facts.

Before POST, the owner rechecks actual phase, frame age and the separate original
monotonic/controller acquisition interval, then persists `issued`. An ACK alone
cannot complete publication. A separately read actual fixture journal must
contain exactly the original actor sequence, ticket, captured time and facts.
The original response, entry, provider-before/after histories and controller
acquisition interval are preserved in an immutable hash-referenced receipt.
Provider identity, complete prefixes, phase and clocks remain checked.

An issued POST whose return was lost is never sent again. A committed journal
entry resolves it unchanged. Missing same-phase delivery remains unresolved and
blocks further captures/publication. A later actual phase can retire that
uncertainty without publishing old facts; the record explicitly has no entry.
An unissued planned intent can likewise retire on a later phase. A committed
receipt with a lost return is adopted from its exact immutable record without
another POST or journal request. New publication still requires a new frame.

`IOSGraphicsObserver.archive` and `IOSGraphicsPublisher.archive` perform pure
original validation after runtime metadata removal or app death. They read
retained original evidence, create no SDK/clock and never refresh historical
timestamps. PNG changes or missing originals fail. Artifact files and original
receipt copies remain evidence; paired runtime retirement belongs to the final
coordinator. Earlier component `observer.publish` remains available for its
existing source tests; the full owner must use this durable publisher.

Fourteen selected no-build host cases pass: twelve publication/archive cases
and two existing independent-observer/phase-retirement regressions. They use
real loopback journals/private files and synthetic iOS native/SDK sources.
This establishes test logic only; native code remains uncompiled and devices
remain untested. Graphics still has no complete capability.

## Original authority retirement after journal deletion

Publication records now write version 2 and read versions 1 and 2. The publisher
owner remains version 1 because its header/state/reference layout is unchanged.
`retire_run` retains an exact planned or issued intent as `mode: run-retired`
using `IOSGraphicsRunRetirement`'s separately acquired original retired journal
authority and inactive resource-provider packets. The closed history must extend
the intent's original provider history and contain its actual original ticket.
An active journal, missing/foreign authority or changed provider cannot authorize
this path. The new record form cannot be relabelled as version 1.

A deleted original journal has no readable entry/outcome. The retirement record
therefore contains neither a journal nor an entry. A POST that actually committed
before deletion and a POST that never arrived both remain unknown outcomes. No
requested fact, ACK, expected receipt or empty fabricated journal is supplied.
Planned intents can retire without ever issuing a POST. Neither capture nor POST
is redelivered. A committed retirement record with a lost return is adopted as
history without another authority query, input or fresh timestamp. Pure archives
validate the same originals after runtime metadata removal and app death.

`resolve` selects this path when the original provider is inactive. A close that
races an earlier active-provider lookup may still interrupt live journal lookup;
its exact pending intent remains owned and the finalizer can call `retire_run`
explicitly. The [complete worker/finalizer](GRAPHICS_FINALIZATION.md) now uses this
path in the integrated fifteen-step host case. These
methods do not stop an app, remove runtime metadata, prove complete quiet or
advertise a whole Graphics capability.

The fixture reader also preserves retirement when two originals have the same
millisecond epoch and activation-prefix length. An old active caller floor must
be validated as an ancestor of the retired source; it cannot be mistaken for a
new advancing active source. Original timestamps and nonce histories remain
unchanged. This fixes a real host source-reconstruction failure at closure.

The combined retired-publication, existing publication and original scene
selection passes 27 no-build cases in 73.477 seconds, including lost committed
and uncommitted POSTs, never-issued intent, lost retirement-copy return, exact
same-epoch retirement, v1 compatibility/downgrade refusal, and pure archive
validation after metadata and SDK retirement. All native/driver/pixel boundaries
remain synthetic; native compilation and devices remain unexecuted.
