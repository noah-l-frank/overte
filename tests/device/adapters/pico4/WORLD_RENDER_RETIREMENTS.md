# One original window for historical capture inventories

`PicoWorldRenderRetirements` version 1 is a private warm read-only source.
It takes validated original Graphics retirement proofs, preserving their
candidate binding, role, capture ID, complete issuer list and memory/file
retirement. The command contains only selectors and fresh query/run nonces.
No requested absence, expected state or host path reaches the native reader.

The Pico/E2E-gated native entry uses the existing bounded GUI queue, refuses
inactive/non-HMD contexts and consumes each query nonce before acquisition.
One dispatch invokes the unchanged `featureWorldRenderReceipts` getter once
per capture, always with `inspect`. That getter retains the actual GPU ledger,
complete issuer validation, private-file identity/hash checks and its original
4096-query lifetime cap. The new wrapper does not release captures or remove
files. Native absence can retire an already undelivered storage intent through
the original ledger's existing tombstone behavior; that cap is unchanged.

All original DTOs are returned intact within one native wall/elapsed interval
strictly below 1500 milliseconds. The command admits 1–256 distinct captures
and at most 1024 globally distinct receipt selectors, within 49152 command
bytes. Output is bounded to 200000 bytes; oversized or partial acquisition is
unavailable. The wrapper records its original start/end, PID, instance and
cursor, alongside each original getter's nonce, cursor, epoch and full source.

The Python reader validates every packet against its corresponding original
proof and unchanged issued flags. Complete manifest order, native instance,
PID, original nonce uniqueness, advancing global getter sequences and all
source epochs are required. One host/native deadline includes transport,
validation, exact result copies, final source guard and actual canonical
Script source-lock exit. Lost/late/invalid results latch failure and preserve
the pending command; a later result cannot trigger a resend. Actual raw bytes
and their SHA-256 are retained separately from decoded JSON. The Pico factory
uses the existing candidate transport, native observer and exact shared lock,
and refuses any existing capture owner across Browser/Graphics/Emote stores.
The generic observer and GPU context create independent native UUIDs. Their
UUIDs are not compared to each other. The actual GPU inventory must match its
original GPU memory proof; the existing candidate transport binds both sources
to the process. A prior single-capture helper incorrectly equated those UUIDs;
that join is corrected with a counterexample using distinct producer births.

This source alone does not establish that its supplied manifest includes the
entire historical browser run. The [durable capture owner](BROWSER_CAPTURE_RETIREMENT.md) now derives that
complete set from admitted original histories and preserves each query intent.
The enclosing finalization still must include every original journal/PNG/context
in its immutable archive before host closure. Cold reconstruction of this reader is not an
authorized recovery route. Browser `finalize()` and public capability remain
closed until that composition and the whole unchanged Journey are verified.

The disjoint `world-render-retirements` selector runs the actual new native
header and complete new TSI method with selected exact original GPU inventory/
getter bodies and actual Qt mutex/private-file code. Actual queued thread
dispatch, duplicate/unavailable query retirement and cancelled functor ownership
execute as well. GPU capture production, application lifecycle and HMD mode are
explicit harness seams; this is not a full TestScriptingInterface translation
unit or APK build. The Python/Node cases exercise the actual Pico
factory, existing capture proof, complete original validators and real host
source lock, with explicit native transport/render/clock seams. The 80-capture
positive is source logic qualification, not an HMD capture claim. Counters
cover missing/duplicate/foreign packets, live callbacks/files, changed issuers,
old query nonces, malformed schemas, stale clocks, final copies/guards, actual
lock-exit time/errors and uncertain delivery. No complete feature is added.
