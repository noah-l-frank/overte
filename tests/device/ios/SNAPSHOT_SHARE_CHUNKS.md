# Anchored unchanged Snapshot Share archive bytes

The separately selected Share extension now writes native original version 2.
It retains the actual exclusively created App Group run directory's stable
kernel identity and the completed original file's full stat revision. The copy
checks both opened and named source/output file identities, synchronizes the
actual bytes, verifies owner/mode/link/size, and treats failed descriptor or
directory closure as unresolved. It never requests an image preview or encodes
a new representation. Read version 1 remains supported with its exact original
grammar; it cannot supply a version-2 anchored chunk flow.

The archive's ordinary Import button still performs one exclusive import. It
requires the finished original version-2 source, unchanged source run root and
original file revision. After the actual byte copy it rereads the native source
metadata unchanged, checks the source identity again, and writes import version
2 with the initial source/output file revisions and source/archive root
identities. Literal import version 1 remains readable separately. The original
extension metadata is exposed byte-for-byte; the archive does not retime its
clocks or turn import completion into extension process absence.

The archive adds ordinary nonce/offset fields and a read-only
`snapshot.share.archive.chunk` button. Each unique nonce reads at most 512 KiB
of the actual imported file. The reader checks the initial completed inode and
full revision before the first chunk, validates the named/opened file and run
directory before and after the read, closes the actual readers, and emits one
bounded original `snapshot-share-chunk.json`. The source preserves the archive's
own UTC and monotonic clocks and the 1.5-second read bound. Chunks from another
revision, process, source instance, offset, nonce or native clock cannot be
combined. Byte reconstruction checks the original exact size and SHA-256.

`IOSSnapshotShareArchiveRuntime` requires a held source lock and the actual
historical independent Share code-admission owner for the same selected IPA,
run, installed process and original OS source. Its foreground guard remains
strict. It exposes only this run's `import-original.json`,
`original-extension.json` and the bounded chunk output over the retained AFC
SDK; no arbitrary file or whole unbounded original can be pulled. Its pure
readers distinguish import provenance from independently received original
bytes and later client Share completion.

The 2026-10-26 targeted host selection passed 13 tests in 0.396 seconds: five
new chunk/runtime tests and eight existing Share original regressions. They
use actual private source/archive files, actual PNG decoding including an image
crossing the 512 KiB boundary, kernel identity/replacement, byte reads and
independent original metadata. Native chunk/OS sources remain declared models.
Cases cover same-byte inode replacement, source/root substitution, literal
grammar isolation, missing closure, repeated nonces, reordered offsets,
changed bytes/hash/process/clocks and an actual admission-bound AFC facade.
No Objective-C, CMake configuration, device, install or laboratory was run.

The outer durable Share input/selection/import coordinator, actual system
cancel/finish handoffs, original live extension process anchor, separate
extension absence, App Group/Documents retirement and repeated quiet cleanup
remain required. The existing process plugin rejects queries for a foreign
bundle under the main/archive driver; this transport does not weaken that
boundary or assume that extension completion means process disappearance.
The complete Snapshot feature remains closed.
