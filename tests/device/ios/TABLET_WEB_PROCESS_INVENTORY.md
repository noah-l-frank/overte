# Tablet process inventory originals

The first actual production-worker unused terminal run acquired both roles'
independent original quiet observations and a genuine four-sample paired seal.
It then failed before Stop: the complete original file inventories exceeded the
unchanged 48 KiB packed process journal limit. All 306 frozen sources remained
unchanged; no process Stop or SDK deletion was attempted.

`tablet_web_process_inventory.py` stores the complete original host inventories
through the existing `OriginalFrameStore`. Each raw fragment is at most 512 KiB;
each wrapped immutable file retains the existing one-MiB limit. The full
inventory document keeps the existing 16-MiB raw bound. Its small parent journal
records every planned/opened/saved transition before the next file operation.
The process journal retains a closed reference with the exact header hash and
every carrier's actual device, inode, mode, owner, group, link count, length,
mtime and ctime. No existing codec or native limit changes.

The process still checks every original file inventory on every use. Only its
actually declared inventory header and fragment paths are excluded from that
tree comparison; their complete bytes and original signatures are independently
checked through the reference. A new carrier with the same filename prefix is
not excluded. Inventory staging occurs before acquiring fresh phase authority.
These host metadata files grant no native/resource retirement or Stop authority.

A complete opened original can recover a lost saved-intent return without
rewriting its bytes, inode or recorded phase. An incomplete original remains
owned and blocks qualification. A historical owner cannot write or recover.

Thirteen actual host-file/process-WAL/SDK cases pass in 3.310 seconds, including
an actual 1,800-file inventory that exceeds the old packed journal and spans
multiple bounded immutable frames, lost saved intent, genuinely empty opened
files, same-inode rewrites, hardlinks, foreign bindings and an unregistered
same-namespace carrier that prevents an OS query. Native and OS producers are
models; native code is uncompiled. The whole Tablet end path remains pending.

This new process inventory and process journal composition are unpublished
Tablet WIP version 1. Shared protocol, native source and legacy feature schemas
are unchanged. Proposed internal registry keys are
`ios-tablet-web-process-inventory` and
`ios-tablet-web-process-inventory-original`, both version 1.
