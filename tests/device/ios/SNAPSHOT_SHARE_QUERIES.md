# Durable Snapshot Share process queries and quiet originals

`SnapshotShareQueryOwner` now retains the independently admitted archive's
extension-query responsibility before an ordinary SDK command is issued. It
uses the existing source lock, exact candidate/process/session binding,
selected final archive, original OS source and the original code-admission
journal. Its private namespace does not overlap the Photos Save or Share code
admission owners. Existing process/Photos contracts and defaults remain exact.

The repository Node source adds a read-only
`mobile: overteSnapshotShareExtensionOriginal` command. A new source query
retains issued status before DVT access, then stores its original JSON once
after actual connection and socket closure. Lookup accepts only that same
archive binding and original nonce, performs no DVT read, advances no source
counter and adds no clock. Unknown, pending or failed queries have no successful
payload. Returning or modifying a lookup result cannot mutate the source's
retained JSON. This repository source was not installed or activated.

The host writes query intent and its original send bracket before crossing
the SDK boundary. An uncertain return stays issued. Recovery reads the exact
stored producer JSON using the same nonce; it cannot send that query again or
start another query while responsibility is unresolved. A request that never
reached the source remains unresolved. Immutable host files retain the actual
JSON, original source clocks, old PID anchor and conservative original host
acquisition bracket. A late original remains historical and cannot satisfy
the 5.5-second qualified acquisition used by quiet checks.

The original file store persists planned/opened/saved transitions before each
write. A complete saved original before the parent journal update is adopted
without another source lookup, allocation, file write or query. An interrupted
partial file stays frozen and owned. Identical replacement bytes do not replace
the recorded device/inode. Historical reconstruction uses only the actual
retained files and independently selected/admitted archive; it issues no SDK
calls and creates no fresh measurement.

Receiver binding reads this run's actual `original-extension.json` through
`IOSSnapshotShareArchiveRuntime`, with the same held lock, binding, archive
forest and original code admission. Those exact bytes are retained separately.
The source's original live PID anchor must match the completed, finished native
Receiver ledger's actual PID and qualified embedded bundle. A foreign PID or
changed raw ledger becomes an unqualified retained original; reconstruction
cannot overwrite it with a repaired result.

Quiet requires three distinct qualified retired-query originals, each proving
both receiver-bundle absence and absence of the original numeric PID after
actual DVT connection closure. The first complete reply's end and last query's
start span at least three seconds independently in Node-host UTC/monotonic and
owner-host UTC/monotonic time. Both clock pairs remain original; neither native
Receiver nor host monotonic epochs are transplanted. A partial presence reply
does not enter the quiet set. A later attempt uses a new passive query while
retaining the old reply. The resulting historical quiet receipt explicitly
requires filesystem retirement and the complete outer feature.

All new getter, query owner, inner query/Receiver frames, immutable outer
query/Receiver frame/original and quiet contracts write/read version 1. No
source version was relabeled and no complete Snapshot capability was enabled.

On 2026-10-26, the final explicit no-build host selection passed 49 tests in
23.540 seconds: three source-original reply tests, nine query-owner tests,
eight Share process tests, nine original process-plugin tests, ten retired
process tests, seven Share admission tests and three Photos factory tests.
The actual repository Node producer runs against fake DVT/OS boundaries and
actual unconnected socket close callbacks. Query/Receiver storage, byte reads,
kernel file identity, clocks, the 5.6-second late-return case and both quiet
intervals use real host operations. No server, device, build, compiler,
installation, dependency change or laboratory was used.

Feature 11/14 remains partial and the total source-complete count remains 5/14.
Next connect the normal Share open/cancel/receiver-selection/receive/inspect/
finish/import flow to these original query and Receiver journals, existing
client export operation and actual capture PNG. Conditional owned App Group
and Documents retirement must consume fresh absence and immutable native
artifact anchors, then retain separate file/run quiet proof. Authenticated
upload/body originals, actual OS permission/confirmation recovery, Actor/scene
image witness, lifecycle resume, final client capture restoration and paired
cleanup also remain required before the unchanged full journey can qualify.
