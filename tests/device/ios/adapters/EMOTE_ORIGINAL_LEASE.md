# Original continuity during final metadata retirement

`IOSEmoteFinalArchive` first freezes every actual fixed-owner value. Its full
historical decoder validates the original native, Script/VM, file, entity weak
lifetime, Qt pointer, GPU, peer/publication and PNG proof. No digest or proof is
derived from filesystem metadata.

The full decoder runs between the initial `EmoteOriginalLease` inventory and an
unchanged post-validation inventory. This transient lease is never serialized
as a verdict. It inventories every file and directory under the original
artifact root, including the immutable archival copies and PNG bytes. Regular
files retain actual device/inode, mode, owner/group, link count, size and
nanosecond modification/change timestamps. Symlinks, hardlinks, missing entries,
new entries, changed inodes or changed original bytes fail closed. Directory
entry inventories and identities remain exact. Each individual scan compares
its full directory stat signature before/after enumeration, including size,
link count, mtime and ctime, so an entry created after enumeration is refused.
Between separate snapshots, directory timestamps may change when the exact
known metadata files retire.

Only the exact supplied CAS-owned runtime metadata paths and finalization
journal are excluded from the immutable inventory. Each such metadata value is
independently compared with its exact retained copy immediately before its
normal `PrivateFeatureState.discard`. The whole feature finalizer also binds
these paths to its deterministic actual owner snapshots. Unknown extra paths
cannot acquire deletion authority merely by appearing in a saved plan.

Before every metadata discard, current candidate/process continuity is checked,
then the unchanged original inventory is checked again. The inventory is also
checked after the discard and before recording its completion. An actual
original write after one discard blocks every later discard and leaves the
remaining responsibility durable. A lost discard return resumes from retained
copies. Reconstruction runs the full byte-based decoder again and takes a new
transient lease before proceeding.

This removes repeated full PNG/native-history replay before each metadata
unlink while retaining original validation and mutation detection. The durable
DTOs, file names, source clocks and resource-closure predicates are unchanged.
Host tests exercise real files, same-byte rewrites with restored mtime, new
inodes, inventory changes, symlink/hardlink/mode changes, lost actual discard
returns and source mutation between metadata retirements. Native sources in the
host fixtures are modeled; no device qualification follows from these tests.
