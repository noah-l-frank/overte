# Safe failure publication observer

This optional host-only helper validates an immutable debug publication. It never dispatches a test, calls a device, changes a verdict, retires an owner or releases a debug hold. A failure-preserving producer and the Jenkins resource lock remain authoritative.

The CLI reads a separately hash-pinned private debug configuration and publication policy. The context is the complete configuration SHA256. The mandatory data index inventories every published data file; the last debug-state receipt uses the producer's 32-character lowercase hexadecimal generation and binds that index and the three required safe summary/JUnit/event files. Literal historical inputs retain their own exact hashes. Additional live logs are limited to policy-declared stream directories and the original diagnostic publisher's index/numbered-parts format. All files are read through bounded no-follow descriptors, with mode/owner/link/inode and tree bookends. Unindexed files are rejected. No wildcard archive is authorized.

The policy envelope accepts at most 1024 files and 256 MiB, matching the pinned producer. Each generation must still fit its declared file/total limits and the existing per-file and stream bounds; an envelope does not authorize additional content.

`--archive-stage` must name a fresh canonical workspace directory under the exact run. Only verified safe bytes are copied there and checked again. Jenkins must archive the returned explicit file list and publish JUnit **before** waiting on the preserved failure. If complete-log verification fails but the bound safe summary/JUnit/events remain independently valid, only those three may be copied; the result stays `PUBLICATION_ERROR` and `fullLogPublicationVerified=false`. Invalid core evidence permits no archive. Partial copies are retained and never adopted or overwritten.

Optional `--after-sequence` projects only timestamp/sequence, closed phase/event and an admitted module ID from the producer's private append-only safe-event stream. It never forwards raw text, arguments, frames or private values. An incomplete line is withheld; malformed, duplicate or decreasing positive cursors fail closed; sparse increasing cursors are accepted. Omit this option when the producer already provides the same console stream.

A parallel Pipeline observer must treat publication errors as errors while keeping the intentional hold and device resource lock. The observer does not implement manual resume or cleanup. External aborts, agent loss and natural app/session evolution are not atomic state freezing. Private originals remain private; complete redacted logs are not unredacted originals.

Tests use temporary files and the repository's actual diagnostic text publisher. They are discovered by the existing Jenkins host-test directory, with no device or controller access.
