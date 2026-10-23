# Private original Chat observation owner v1

`ChatObservationOwner` projects newly acquired `CompiledChatSamples` or
`CompiledChatCacheAbsence` into the unchanged common v16
`feature.chat.observe` result shape. It issues no ordinary input, cache
activation/retirement, peer stimulus, restart or publication. No public binding,
capability or stereo evidence is added. The actual first public RPC/cleanup
choreography remains separate work.

One owner has one role and one stage: initial absence, active Chat or cleanup
absence. It holds the exact two existing source-lock objects. Its private flow
file supplies only original consumed-input authority and the transcript names;
state, resources, lifecycle and timestamps come exclusively from new original
queries. Cleanup additionally requires the original admitted Phase27 and its
exact complete 26-row flow hash. The public observation sequence is a host
cursor, not an invented native counter.

Repeated reads of the same fixture phase acquire different native request IDs
and different compiled Root/Script/Root transaction UUIDs. The activation ticket
and original activation epoch remain unchanged. A newer phase can never relabel
an earlier frame. A final independent HTTP phase query after the last owner CAS
checks input authority only; it does not refresh any target timestamp. The
original multi-source 1.5-second bound still includes all source/history I/O,
result copies, CAS operations and final guards/clocks.

The root contains `chatObservationOwnerVersion`, `contractVersion`, `runId`,
`fixtureUrl`, `role`, `binding`, `peerBinding`, `stage`, `transcript`,
`flowJournal`, `cleanupAdmission`, `phase`, `revision` and `chunks`. Existing
`ChatSourceChunks` preserves complete immutable rows under its unchanged limits.
Each row contains `sequence`, `before`, `after`, `authority`, `reference` and
`sample`. A reference includes the existing index/ticket/query/epoch fields plus
`sourceSha256`. The referenced original source chunk is reread and compared to
its exact physical manifest and in-memory frame; a mutable cached frame cannot
replace its original bytes. The observation row itself is also compared with
its written original before return.

Construction refuses every existing root and every rootless chunk. A ready
source row is not an independently received public-RPC receipt. Unknown/lost
reading, final CAS or return paths remain owned and cannot be reconstructed,
retired or replayed through this class. The explicit later RPC lifetime join
must qualify only fully consumed transactions; this version supplies no cold
ownership adoption.

The focused host module `self_tests.test_chat_observation` passed seven cases in
5.996 seconds: repeated same-phase originals, measured active UI without another
input, cold/reading/rootless retention, changed phase after final CAS, frozen
host with native jumps during final CAS/copy/guard, in-memory source mutation,
strict compiled-source type admission and future-cursor refusal. Native/V8/
widget producers and their clocks are explicit seams. No app, AC, device,
network service or OpenXR runtime runs.
