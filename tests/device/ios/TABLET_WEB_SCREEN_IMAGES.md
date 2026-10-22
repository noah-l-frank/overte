# Original Tablet native screen images

`IOSTabletWebImages` uses the closed Tablet profile of `OriginalScreenImages`.
It owns actual WDA screenshot requests and original PNG host files, not a GPU
scene frame. It supplies no native capture epoch, frame ID, page identity or
successful feature verdict.

The shared file owner was extracted from the existing Graphics v1 image owner.
The Graphics facade preserves its public API, original
`graphicsScreenImagesVersion: 1` envelopes and exact `graphics-...png`
filenames. Independently authored old envelope and PNG bytes remain readable
without migration or network access. The Tablet profile uses
`tabletWebScreenImagesVersion: 1` and `tablet-web-...png`. Neither profile may
adopt or delete the other's ownership.

Each capture retains planned/opened/saved ownership, actual device/inode,
private file mode, request nonce, original PNG bytes/hash/extent and distinct
host/native brackets. A lost WDA return never resends the screenshot; the open
file remains owned until actual cleanup. Replaced inodes and corrupt PNGs fail
closed. Repeated cleanup verifies owned paths absent and preserves the
ownership transcript. A no-I/O historical read hook records PNG membership
only after actual inode and full original byte validation; membership is not a
native product or cleanup fact.

A complete Tablet sample must independently bracket this PNG with the actual
foreground UIKit app/window, presented WK view, current native document and
original passive DOM, then validate challenge/page pixels. Other sheets,
windows, source/navigation changes or recycled native views must fail closed.
The file owner performs none of these surface joins. Feature 7 remains partial
until its actual native source, trusted input, all 26 actions, independent
witness, errors/recovery and full repeated resource retirement are integrated.
