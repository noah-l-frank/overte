# Original Snapshot source packets

The four closed `SnapshotWorkPacket`, `SnapshotCapturesPacket`,
`SnapshotExportsPacket` and `SnapshotInputsPacket` owners retain existing native
version-1 work, capture, export and normal-input DTOs. They reuse the existing
`SnapshotOwnedPacket` query journal and `SnapshotFileWorkPacket` original-byte
storage. No native hook, source version or original field is changed. Live
capture/export callbacks remain live observations; a retained packet cannot
substitute for actual callback or resource retirement.

Each owner binds its full candidate/process, run, role, actual source lock,
query index and private namespace before issuing one passive query. NativeDiag
before/after originals, actual host UTC/monotonic acquisition and the native
getter's original bracket remain separate. Strict qualification uses the
existing 1.5-second join. A late result stays historical and never receives a
new source timestamp. Lost input delivery never causes another query.

Exact AFC JSON, including whitespace, is split through the closed
`snapshot-native-sources` storage profile. Its only subjects are work, captures,
exports and inputs, and its only label is raw. Each component has its own
namespace and query-derived tag. The source's original byte bound remains in
force; journal, part-file and global slot limits are unchanged. The small frame
contains the original part reference and clock bracket rather than duplicating
the raw string and decoded native DTO. Readers reconstruct both from the same
actual bytes and verify the proper existing native codec.

Planned/opened/saved transitions remain durable before writes. A complete raw
original after a lost flush can be adopted without AFC, a query, a replacement
inode or another part write. A partial original remains frozen and owned.
Historical readers use only actual private files and cannot query, mutate or
create an SDK. Component/query/role identity and original file inodes cannot
be relabelled. The released owned-file and file-work packet shapes, namespaces
and history rules remain unchanged.

All four packet contracts, eight small-frame/original contracts and four
segment contracts write/read version 1. Six targeted host checks use real
private files, actual normal HTTP/AFC boundaries and weak host captures/exports
with explicitly modeled native/Script/SDK clocks. Existing file-work and
owned-file/remove regressions independently cover the retained large-ledger and
partial-write behavior. No test compiles or executes the iOS native sources.

These sources still require the full capture/cancel/export input coordinator,
scene fidelity, independent destination/witness originals, lifecycle restoration
and paired cleanup. They advertise no complete Snapshot capability.
