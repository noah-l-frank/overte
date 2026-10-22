# Original Linux host descriptor ownership v1

`adapters.native_fd_owner.OriginalDescriptor` retains an original descriptor and
a separate `F_DUPFD_CLOEXEC` alias. Before use or close it checks the original
nodes and the kernel's actual `F_DUPFD_QUERY` open-file-description identity.
Opening the same original inode again under a recycled descriptor number is
foreign ownership. A lost/recycled original or anchor permanently poisons the
owner; neither uncertain half is closed or adopted. Host process finalization
owns eventual release of those retained handles.

This reuses the already reviewed Pico candidate read seal's kernel identity
approach in a small platform-neutral importable helper. Import remains possible
without `fcntl`; attempting strict admission without the Python/kernel query
fails closed. Actual OFD-positive tests require that source and do not supply a
fallback based on inode, file contents, path or descriptor number. These host
handles and proofs are separate from the target actor's native-held descriptor
inventory and do not establish target resource release.

`LinuxChatActorProcess` always uses the original descriptor owner for its actual
`/proc/<owned-pid>/exe` handle. `OwnedChatPeer` additionally requires it for the
original actor-directory descriptor in `ChatActorFiles`. Guards cannot continue
under a same-file descriptor replacement, and `close_host` cannot close the
foreign replacement. The peer process, native SOURCE and private original
journals remain owned. Legacy standalone `ChatActorFiles` construction retains
its existing default and gains no strict host descriptor qualification; the
complete owned Pico peer factory explicitly selects `require_original_fd=True`.
No native/product behavior, actor launch/discovery, installation or device run
is changed.

Ten focused real-kernel/file/owned-stdin-worker cases passed in 0.701 seconds:
original aliases, ordinary close, recycled original/anchor for both files and
directories, different-file replacement, missing/unsupported query with no
escaped descriptors, the existing peer acquisition/identity cases, actual peer
executable-FD recycling, and strict actor-directory recycling before publication.
The isolated four helper tests passed in 0.002 seconds after the import-only
portability guard. Worker SOURCE/build/script rows are explicit synthetic seams;
the kernel OFD/PID/start/executable/environment and private filesystem originals
are real. No Assignment Client, headset, native compiler or service was run.
