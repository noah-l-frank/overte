# Original global Chat sources in the Pico archive

`pico-chat-cursor-archive-extension` version 1 is an optional extension of the
existing version 4 archive plan. It preserves that plan's full cold byte pass,
original descriptor ownership, bounded reopen windows, immutable physical
stamps, current directory inventories, final freshness fences, unlink policy,
and separate host finalizer. Legacy archives do not acquire this proof.

The warm `ChatCursorCleanupConsumption` supplies its exact returned receipt,
the original shared cleanup bytes, both returned `ChatCursorSourceSeal`
receipts, and the live objects for both complete graphs. The plan explicitly
catalogs their roots and immutable chunks, including every initial, active,
and cleanup observation, the actual global cursors, the Actor publisher, all
sample owners and compiled-code predecessors. The catalog checks the physical
root and chunk stamps against the received seals and checks those same seals
again after acquisition. No directory scan discovers or adopts a source owner.
The existing final inventory still rejects any extra unresolved original.

With this extension the plan does not reconstruct the legacy private witness
with 26 fixture publications. A repeated global query keeps its actual cursor
and original local observation sequence. The extension's metadata fields are
`chatCursorCleanupConsumptionVersion`, `chatCursorCleanupConsumptionSha256`,
`chatCursorSourceSeals`, and `chatCursorSequenceSucceeded`. The cold Pico parser
requires all four fields, version 1, a true Boolean sequence result and two
distinct SHA-256 seal hashes. It rejects mixed legacy baseline metadata,
partial fields, aliases and unsupported types.

`PicoChatComposition.restart_and_close_application` accepts the optional exact
warm `cleanup_consumption`. Before constructing restart IO or the archive plan,
it requires the original one-shot shared hook, actual engine success, the same
cleanup activation, run, bindings, final samples and fixed private store.
The existing restart, new native birth, independent old-process absence,
physical profile comparison, deferred IPC closure, archival and primary host
handle finalization continue through their existing owners. A returned direct
three-second wait with `sequenceSucceeded=false` cannot authorize this path.

The low-level catalog acquisition can inspect that false diagnostic receipt
without changing its result. Its test joins actual global source graphs and
then proves the parent refuses restart or final archival. It also replaces a
sealed root with identical bytes and verifies that neither a new catalog nor
the old captured catalog accepts that replacement. Native producer, fixture
transport, input recipe prefix and Actor scheduling remain the declared seams
of the underlying source fixture. This is not an external whole-journey test.

The private public-operation bridge and a persistent independent Actor process
still need to compose this path from a successful full shared `execute()` hook.
The independent Actor must finalize its own original host handles before shared
cleanup can succeed. This extension does not supply that process receipt,
stereo evidence, a qualified Actor binary receipt, cold RPC ownership or a
public Chat capability. The historical full warm archive diagnostic predates
these global sources and is not relabeled as evidence for this extension.
