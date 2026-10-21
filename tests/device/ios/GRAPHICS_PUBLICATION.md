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
