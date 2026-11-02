# Original archive-index computation and physical verification

Root profiled the retained partial Browser archive from d430227d07 using only
read-only method views. These have no query/unlink/retire/transport operation
and do not adopt its unresolved warm owner. All2,236 retained originals match
their previous full physical stamps and SHA256 before/after each profile.
There are1,087 immutable archive files,80 complete PNG originals,14 confirmed
source unlinks and one unresolved pending unlink; its outcome is not inferred.
An initial diagnostic incorrectly assumed1,070 original copies; the corrected
reader derives the count from the actual complete manifest/parts and namespace.

Full physical index checks cost37–50ms and current-copy/manifest checks with
both indices75–79ms under cProfile. Full80-PNG reads cost10–11ms; two actual
namespaces10–11ms. Release admission strict JSON/digest validation costs37ms
and its complete original control41–42ms. These are historical host costs,
not new source observations or a complete cleanup execution.

The earlier optimization pinned each exact admitted tuple, original Path object and its
immutable canonical snapshot bytes. Verification still visits every physical
file through the held original directory, checks the complete namespace and
full stamps, original byte/owner identities, and recomputes the same SHA256
chain. It constructs the exact same canonical pair from the original serialized
snapshot instead of invoking the JSON encoder and constructing/comparing Path
objects for every file on every pass. The persisted v4 format and chain value
remain unchanged. Current-copy/manifest full byte windows remain on both sides
of the original guards. No source query, clock anchor,250ms/16-unlink window,
quiet window, final deadline, file/byte/frame cap or capability changes.

Afterward, equivalent historical full indices cost10–11ms and current-copy/
manifest checks21ms. Every complete PNG/namespace/release-control measurement
remains essentially unchanged. Three new memory-index fault variants at the
actual landed unlink intent refuse before any original source disappears;
existing foreign-copy, same-byte replacement, root-swap, delayed-final-index
and immutable-byte/digest/stamp counterexamples remain active.

The four selected groups pass81.47s: Chat archive73cases/7.658s, Browser
archive7/36.923s, Browser host-close2/36.790s and coverage10/0.094s. All13,522
tracked/new source hashes match before/after. Four repository suites pass2.63s.
This selected result does not establish complete Browser cleanup; the next
separate full owning execution must remain within the unchanged120s.

Shared Phone reconciliation: only the shared ChatEvidenceArchive v4 warm
in-memory verification index and its original file/cursor counterexamples
change. Existing v1/v2/v3 writers/readers and every persisted schema remain
unchanged. No Phone or iOS file is edited.

## Pinned immutable chain, fresh physical checks (2026-11-02)

The original canonical chain is now computed and pinned at each immutable
append. Every pass still verifies the exact sealed immutable index tuple and
admission identities, every mutable row/owner/raw/stamp field, complete fresh
held-directory enumeration and every fresh physical file stamp. Current-copy
and manifest byte windows, original source/phase guards, query counts, clocks,
quiet windows and unlink/file/byte bounds remain unchanged. This avoids
rehashing immutable canonical tuple bytes on every physical pass; it does not
cache a physical observation or source verdict. A changed digest or replaced
index refuses before the next copy can reseal it.

A private cost-only fixture held 1,070 actual immutable files. Fifty complete
passes cost0.274/0.273s before and0.218/0.218s with the candidate, about20% less
for this index method alone. All original bytes and complete physical stamps
match before/after. The fixture performs no unlink or product observation and
cannot establish a complete Journey speedup or cleanup result.

The new append-boundary counter genuinely failed for both digest and tuple
replacement before the fix. Its retained rerun contains the same two failures;
the initial diagnostic retained its log but not its temporary originals.
After the fix, all54 affected index, original-unlink, legacy archive and Browser
namespace cases pass in1.036s with128 loaded source SHA-256 and full physical
signatures unchanged. This is separate component evidence; the previous120s
whole Browser failures are not reclassified.

Exact scripts, source manifests, logs, retained failure/success originals and
cost measurements are private under
`/home/user/.local/state/overte-pico-resume-integration-20261102-24qkewqw`.
Shared reconciliation remains additive: no persisted format/version or Phone/
iOS source changes.
