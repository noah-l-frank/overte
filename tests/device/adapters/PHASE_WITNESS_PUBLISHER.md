# Original phase witness publication

`PhaseWitnessPublisher` shares the existing Graphics publisher's durable
intent/receipt approach without depending on a Graphics provider or observer.
It uses the existing `PhaseFixtureReader`, actor-only `/samples` route, original
actor journal, candidate binding, private state files and source serialization
lock. Existing Graphics contracts and implementation remain unchanged.

The constructor takes a private store, actual actor candidate binding, already
attached phase reader, source lock, live candidate guard, historical original
validator, host epoch clock and monotonic clock. Its fixed state filename is
`phase-publication-<area>-<run>-actor.json`. Only the independent actor receives
the actor credential; the primary adapter's restricted reader cannot publish.
All fourteen existing closed witness projections are supported. This generic
transport does not qualify any feature's observations or complete capability.

`validate_original(original)` must validate immutable original files, process,
run, role, counters, native clocks and measurement composition without acquiring
new product data. It returns exactly `ticket`, `public` and `acquisition`.
`public` is the complete original `feature.<area>.observe` result;
`acquisition` contains its original `hostBeforeEpochMs`, `hostAfterEpochMs`,
`hostBeforeMonotonic` and `hostAfterMonotonic`. The public capture time must lie
within that original window. The callback must never derive expected product
values from fixture input or manufacture a new time around old evidence.

`publish(original)` persists the original, derived result and exact closed POST
body as planned, checks the actual active input ticket and original freshness,
then persists issued responsibility before sending once. Acknowledgment alone
does not complete publication. `resolve()` independently brackets the original
actor journal with actual phase snapshots and retains the exact server entry,
including both original capture and receive clocks. An uncertain issued POST
is never sent again. New samples remain blocked until its responsibility resolves.

Facts and retirement publishers also retain the original acquisition window
through the actual HTTP send. After serialization and opener preparation, the
shared client checks that window immediately before `open`. The registered
guard reads only the original host clocks; candidate SDK continuity is checked
before entering it to avoid recursive SDK requests. Expiration leaves the
issued journal owned and prevents delivery or a later retry. This changes no
wire fields, projections, authentication rights or contract versions.

A genuine later phase may retire an unknown old publication responsibility.
Two original inactive phase snapshots may similarly retire it after run deletion
without requesting the deleted actor journal. Neither mode claims publication,
absence of earlier delivery, provider cleanup or target resource drainage.
An actual matching retained entry remains a published receipt even if its phase
has since advanced. A missing or evicted original cannot become a fabricated
entry. Active-phase ambiguity remains unresolved.

Record files are immutable private, bounded, independently hashed envelopes.
Lost record returns adopt the existing record without HTTP or POST replay.
Existing orphan receipts prevent a new live owner from interpreting absent or
truncated metadata as an unused sequence. `archive(...)` validates retained
metadata and record originals without app/SDK/HTTP access or retiming.
The whole feature owner separately retains artifacts, revokes authority and
verifies all product/provider lifetimes and quiet windows before retirement.

Sixteen host tests use actual loopback HTTP, actor authentication, phase/sample
journals and private atomic files. The product-source validator is an explicit
modeled seam. Tests cover all fourteen projections, ignored/uncertain delivery,
ACK without a record, stale/foreign/changed originals and receipts, phase crossing,
monotonic deadlines, lost receipt returns, absent ownership metadata and historical
validation after metadata removal. Together with fifteen existing phase tests,
31 tests pass. These tests establish publication logic only; no device or native
product qualification is implied.
