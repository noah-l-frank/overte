# Historical recovery prefixes and current journals

Recovery archives are read-only views of exact retained source and peer
originals. A later actual abandonment does not invalidate an earlier complete
recovery prefix. Every record referenced by that prefix still requires its
original private bytes, inode, acquisition and native histories. Historical
data cannot send another query or become a fresh product observation.

The reader compares the supplied recovery bytes with the actual current
journal. An exact current snapshot retains the strict next-record absence
check; an older prefix may coexist with later records. Both reads of the
current journal must agree across archival. Fresh observation decoders
separately validate the actual current recovery journal and all relevant
abandoned-source floors. No cached historical prefix replaces that check.
An absent live parent also refuses an existing first abandoned record.

`archive()` returns the supplied immutable original as `previous`. Its save,
recover and live-follow entrypoints refuse mutation before any write or query.
Only `follow(..., historical=True)` verifies historical prefixes. A planned
artifact pathname uses `lexists`: an actual dangling symlink remains owned and
cannot be recorded as absent by recovery.
Actually opened partial files also register in the original readset, including
empty files, so a typed archive cannot omit their owned byte dependencies.

The private format remains version 1, with unchanged original DTOs and file
names. Tests use actual private files, CAS operations, inodes and symlinks;
receiver/native producers are explicit host models. They cover both closed
peer profiles, later legitimate records, missing originals, current-journal
rollback and change during decoding, absent parents, prohibited historical
writes and planned symlinks. The proposed shared peer-reader patch requires
central integration; isolated in-memory tests do not establish repository,
whole-feature, native compilation or device qualification.
