# Account originals after Avatar scene retirement

Ordinary `AccountManager` logout emits `logoutComplete` and `usernameChanged`.
The actual `NodeList` connections call `reset()`, clear the session UUID and
soft-reset the Domain. A postlogout check must therefore retain account-only
native originals instead of requiring a joined Avatar or repairing the Domain.
Both participants must finish their scene, file, GPU and pixel checks before
either logs out.

`IOSAvatarAccountReads` retains the unchanged native feature/account DTO from
the existing SDK transport. Its actual independent native clock queries are
also durably admitted before send, and their original packets are retained.
Private immutable files keep the matching source packet; a separate bounded
host bracket includes validation and the final metadata save. Account/source
history, actual process/birth and native cursors must advance unchanged. A
historical original never becomes a fresh read after reconstruction.

Lost queries are abandoned before a distinct later nonce. A completed saved
acquisition is adopted without transport. A returned source whose writer is
still planned/opened retains that exact inode and blocks later queries. The
writer transitions and partial-file checks reuse the committed input-read
owner; this sampler adds no native endpoint, account mutation, login authority
or Domain/session request. The runtime supplies its actual bound clock source.

Seven host tests exercise account originals after an explicitly reset Avatar
session boundary, actual runtime factory wiring, ownership before every native
and clock query, unknown delivery, lost original/metadata returns, historical
file-only reconstruction, partial inode replacement and slow final saving.
Native packet production remains an explicit synthetic seam. These originals
must still be joined to each participant's genuine prior owned login and
logout causality by the whole-feature decoder. They do not alone establish
logout, provider retirement or complete paired cleanup.

Contracts `ios-avatar-account-reads` and `ios-avatar-account-read-record` both
write/read version 1. The underlying native DTO retains its original version.
