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

The archive now pins each exact admitted tuple, original Path object and its
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
