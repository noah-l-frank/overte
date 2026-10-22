# Interrupted Avatar source groups

`ios-avatar-source-recovery` version 1 preserves interrupted SourceOwner2
acquisitions. `ios-avatar-abandoned-source` version 1 retains the exact prior
owner and any actually opened frame inode, private file size and hash. The
file/CAS ownership sequence derives from committed `941cefb30a`; original
Avatar source and archive DTOs keep their existing versions and bytes.

Call `recover()` before a distinct passive read and `follow(frame)` after its
completed original has been retained. Recovery writes only private ownership
metadata. It sends no source request, input, service write or file deletion.
An already committed source CAS with a lost return is adopted by its exact
original transition. Empty and partially written files remain owned honestly.
Changed inodes, hardlinks, rewritten records and foreign candidates fail closed.

Every abandoned prefix has the actual source read order, typed original
packets and acquisition hashes. A later frame must extend every returned
native clock/history, Avatar state, whole renderer tree, social XHR history,
Pal model, submitted script/timer history, actual entity-return ledger,
widget generation and phase history. Retired script workers are tracked
across all completed and abandoned originals, including two interrupted reads
with no completed frame between them. A retired worker cannot reappear.

Source-v1 abandoned groups remain exact originals without invented entity
facts. A new SourceOwner2 read supplies real entities through the current
reader. Historical `archive()` and `follow(..., historical=True)` validate only
retained private files, without a live guard or SDK access.

Host tests use real private files, CAS operations and immutable source archives
at synthetic native boundaries. They cover all six source instance resets,
lost source-CAS returns, actually opened empty files and replaced inodes,
strict prefix/acquisition hashes, worker retirement between interrupted reads
and explicit frozen Source-v1 data. The whole observation owner must retain
the recovery ledger alongside its source originals and validate it before
publication. This helper neither resolves uncertain ordinary input nor proves
product/GPU/authority cleanup or feature capability.
