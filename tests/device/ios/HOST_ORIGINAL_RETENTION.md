# Host fixture original retention during interruption

`self_tests.retained_host_roots.retain_owned_root` is an explicit opt-in for an
already owned private host `TemporaryDirectory`. Call it at construction,
before the first original is acquired, with that exact root. It detaches the
directory's independent weak finalizer and replaces only that instance's normal
cleanup with an original directory identity/permission check. It changes no
global tempfile behavior, production cleanup, native packet or SDK operation.

Replacing `TemporaryDirectory.cleanup` alone is insufficient: a
`KeyboardInterrupt` can bypass unittest cleanups, and interpreter shutdown then
invokes the separate weak finalizer. The Avatar baseline diagnostic interrupted
on 2026-10-24 lost all 1,760 temporary original files this way. Its pre-signal
metadata and log remain; no bytes or original inodes were recovered. The run is
`INTERRUPTED_NO_PASS`; its earlier end milestones cannot substitute for the
missing historical/canonical graph. No originals are reconstructed or retimed.

The helper refuses a different root, changed directory inode, symlink, unsafe
permissions, foreign owner or mismatched original finalizer. Repeated retention
is allowed only for the same actual root. It does not assert that any original
file, native lifetime or process end is valid. Independent test code must still
close its owned Node/HTTP processes and locks and audit actual original bytes,
paths and inodes. Explicitly retained host roots require intentional later
cleanup; no production resource may use this helper to avoid its own retirement.

Host tests exercise actual cleanup and GC, a separate Python process receiving
SIGINT and unwinding the interpreter, the exact preserved file inode/hash, and
changed/unrelated directories. These tests run no native compiler or device.

Four cases pass in 0.055 seconds. A separate actual two-root Avatar fixture
probe also passes normal fixture cleanups and GC with the same file
paths/devices/inodes/bytes. Selecting retention in the full Avatar fixture
remains in its pending integration packet. No missing original or result for
the interrupted diagnostic is supplied by these tests.
