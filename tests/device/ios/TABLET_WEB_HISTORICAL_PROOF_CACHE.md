# Tablet historical proof reuse

`adapters/tablet_web_proof_cache.py` is an internal, per-runtime optimization
for complete historical decoders. It creates no product observation, receipt,
clock, original or permission. It changes no persisted grammar or version.

A first result must come from the full typed decoder between independent
complete filesystem inventories. Inventories retain actual device/inode,
owner, mode, link count and file size/mtime/ctime. The existing inventory
primitive also checks the complete directory stat before and after each scan.
Every hit repeats the complete inventory check and returns a deep copy of the
previous full result. Only the exact paths actually read by that successful
decoder are propagated to an enclosing original-membership audit.

Any new, missing or changed original, failed query, pending owner, source-prefix
journal or artifact invalidates all results. The next attempt must run the full
decoder again, including its original continuity and failure checks. Changed
in-memory bootstrap, admission, binding, origins or configured roots also
invalidates all results. External reads without an independently configured
inventory can finish a full decode but cannot create a reusable entry.

The sole inventory exemption is the exact role/run's PhasePublisher CAS file.
The historical decoder is forbidden to read that file. The publisher continues
to decode its own real journal and receipts, and its issued-once, freshness and
last-send checks are unchanged. Newly written publisher receipt files are not
exempted. No filesystem writes or SDK/process/native queries occur in the cache.

The unfinished whole owner uses this only for historical observation, tail and
image/publication reconstruction. Current validation, source acquisition,
readiness, cleanup proof, process/input guards, clocks and send checks remain
independent. Historical terminal reconstruction retains its original decoder.

Eight host counterexamples cover changed context, new failed prefixes,
immutable membership/deep copies, publisher exclusion, inode/mode changes,
hardlinks, independent artifact roots and concurrent graph mutation. Six
existing runtime/CLI admission cases also pass. In the explicitly modeled
same-SDK Actor diagnostic, profiled image publication fell from 197.781 seconds
to 56.650 seconds. The latter run passed in 93.576 seconds; parent and child
actual Python imports had no drift or unfrozen additions. This measures host
decoder work only. It qualifies neither native timing nor the complete Tablet
journey.
