# Tablet private storage and live source guards

Immutable original-file replay supplies historical bytes, not a current native
observation. `TabletWebPackets` therefore accepts an optional private-storage
guard independently of its live source guard. Its default remains the same
caller guard for both roles. No envelope, version, path or native grammar
changes.

The complete Tablet source supplies its actual shared lock as the nested
storage guard. The full live source guard still runs before first ownership,
at both ends of each complete component history traversal, before every WAL
write, at capture admission and after capture completion. The genuine reader
also retains its original process and last-send guards. A source change during
private file traversal refuses the returned live result. A storage refusal
cannot be replaced by successful process admission. Historical mode continues
to forbid all mutations and current acquisition.

All file opens, private permissions, link count, inode, byte length, canonical
bytes, SHA, typed DTO and original-read membership checks still execute.
Queries, clocks, pending owners, continuity floors and completed records are
unchanged. This removes repeated external SDK/process reads per private-file
fragment, not validation of the stored originals.

Host qualification: 32 existing Packet/SourceOwner/native-semantic cases pass
in 12.919 seconds. Three new actual-private-file cases pass in 0.294 seconds:
source loss during traversal denies its result and all subsequent writes/input;
false source admission creates no first journal; and storage refusal remains
closed with no native query or byte mutation. Native/device behavior and the
whole Tablet feature remain unqualified.
