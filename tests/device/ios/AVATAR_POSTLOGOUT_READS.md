# Owned Avatar postlogout account/model originals

`IOSAvatarPostLogoutReads` captures genuine account, State3 model and account
originals after ordinary logout. The actual account lifecycle must establish the
owned child logout before the model query. State3 preserves the actual session
UUID, including null after the product resets NodeList. Active Avatar readers
continue to require a nonnull session.

Every model query and independent native-clock query is durably admitted before
transport. The actual model packet fields are retained before qualification. Both
account samplers retain their own native packets and query histories. The model
native bracket, append-only model history and all account/native prefixes are
validated without relabelling their original clocks. A complete acquisition
includes validation, immutable private-file writes and the final metadata save
within its original 1.5-second host bracket.

A lost query is retained as abandoned and is never sent again. A completed saved
original is adopted without SDK access. Version 1 retains its original rule:
an incomplete writer prevents a later query. Version 2 durably retains the
actual partial bytes/hash and inode, including a zero-byte opened file, before
abandonment and a later distinct passive acquisition. A new query never replaces
the old file, repeats its nonce or turns a partial write into a saved receipt. Historical reconstruction is file-only and
rejects all mutation entrypoints. Actual unrestored model packets remain raw
observations: a later distinct read can qualify, while the old proof still
fails and its bytes remain unchanged.

The runtime composes the existing bound native/account/model transports. Host
tests use explicit native packet producers and real private files, with the
actual runtime factory and query admission checks. They cover lost query and
saved-file returns, partial writers, wrong subject factories, native-clock
brackets and a slow final save. Native compilation and device behavior remain
unverified. This component proves restored account/model properties only;
scene/pixel retirement and complete paired cleanup require separate originals.

`ios-avatar-postlogout-reads` and `ios-avatar-postlogout-record` write 2 and
read 1 and 2. An independent literal version-1 producer verifies the old metadata
and original-file bytes stay unchanged across a later version-2 acquisition.
The underlying native DTOs retain their own existing version boundaries.

Version 2 stores each actual account-owner boundary, returned model DTO and
native-clock DTO as canonical JSON in separate private `AvatarPostLogoutSegments`
files. These are representations of the original typed fields, not newly stamped
native observations or copies of transport whitespace. Every segment transition
is owned before file creation and actual writes. Completed row metadata contains
one immutable partial-record reference; it no longer duplicates every growing
account-owner history inside every prior row. The original model record retains
the exact part references and acquisition bracket. Resolving them revalidates the
original child account histories, native packets, binding and clock prefixes.

The closed parts/partial and segment contracts write/read 1 in their own
`avatar-<subject>-postlogout-parts` namespace. Partial carriers can be locally
adopted after a lost return; an interrupted carrier retains its real prefix
before any distinct local writer. Orphan carriers must have the actual current
row tag and `partial` label. The 48 KiB packed-journal bound, 1 MiB private-file
bound and native source bounds remain unchanged.

Operation-local `AvatarRecordCache` instances reuse only exact decoded immutable
account records and segment material. Keys bind the complete original context
and row/boundary. Cold entries are decoded twice between actual file inventories;
every reuse checks private parents, inode, mode, ownership, link count, length,
timestamps and planned-path absence, including dangling symlinks. It restores
actual file-read membership and returns copied typed fields. A parse uses its
own local material once and checks that material's full inventory again before
returning. Model, account, acquisition and cross-row prefix verdicts are always
computed outside the cache. No decoded result authorizes a native input.

The host-only four-acquisition measurement after this change was approximately
0.65, 1.04, 1.43 and 1.88 seconds. The fourth acquisition still exceeds the real
1.5-second limit. Explicit native test producers retain their original modeled
clocks; functional tests do not establish real device timing. A paired whole
cleanup run also stopped at its original overall deadline rather than extending
it. Whole-feature completion and the real timing budget remain unqualified.

When a normal Avatar API scope is already active, its existing 25-second budget
owns separate account and segment byte-cache namespaces. Reconstructed live and
historical owners can share those original-byte decoders for that one call;
all complete context keys, file signatures, read membership and planned-path
absence checks still apply to every use. Nested scopes retain the original
deadline. Outside an API scope, owners keep their independent local caches.
A new API budget starts separate shared namespaces and cannot renew the prior
deadline. An existing owner can retain its own guarded cache reference, as it
could without the optional shared scope; it gains no new input authority.
Fresh-owner measurements with the actual optional hooks were approximately
0.71, 1.06, 1.42 and 1.96 seconds; the budget remains unqualified.
