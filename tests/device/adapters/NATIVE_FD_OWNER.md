# Original descriptor ownership

Every `OriginalDescriptor.require` obtains a fresh `fstat` of the exact admitted
descriptor and checks its expected device/inode. The kernel `F_DUPFD_QUERY`
against the independently retained anchor must then return `1`. The
[Linux implementation](https://github.com/torvalds/linux/blob/v6.10/fs/fcntl.c)
compares current open-file-description objects, so successful query equality
also supplies inode equality for those two handles. An independent open of the
same inode is insufficient. A separate anchor inode-only `fstat` is redundant.

All original descriptor-number/type, closed/lost and distinct-handle checks
remain. Query errors or mismatches poison the warm owner; uncertain handles are
retained and foreign replacements are never closed by it. This does not claim
atomicity across multiple syscalls or expand the original ownership threat
boundary. There is no new persisted format, fallback or kernel-query cache.

`require_directory` retains its own fresh held-descriptor and named-path stats,
exact current kernel pathname, node, directory type, owner and mode checks,
including original before/after ownership queries. Full immutable file byte,
permission, eight-field stamp, parent and namespace checks are unchanged.
Missing query support still refuses without inode-based substitution. A missing
anchor may be reported as a query mismatch or `EBADF`; both poison and refuse
the owner while retaining the surviving original handle.
