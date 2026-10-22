# Owned Avatar postlogout account/model originals

`IOSAvatarPostLogoutReads` captures genuine account, State3 model and account
originals after ordinary logout. The actual account lifecycle must establish the
owned child logout before the model query. State3 preserves the actual session
UUID, including null after the product resets NodeList. Active Avatar readers
continue to require a nonnull session.

Every model query and independent native-clock query is durably admitted before
transport. The untouched model packet is retained before validation. Both
account samplers retain their own native packets and query histories. The model
native bracket, append-only model history and all account/native prefixes are
validated without relabelling their original clocks. A complete acquisition
includes validation, immutable private-file writes and the final metadata save
within its original 1.5-second host bracket.

A lost query is retained as abandoned and is never sent again. A completed saved
original is adopted without SDK access. An incomplete writer keeps its original
inode and prevents a later query. Historical reconstruction is file-only and
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

`ios-avatar-postlogout-reads` and `ios-avatar-postlogout-record` write/read 1.
The underlying native DTOs retain their own existing version boundaries.
