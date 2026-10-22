# Bounded Avatar tail byte ownership

`AvatarTailSegments` stores exact host-returned bytes in immutable private
OriginalFrameStore files. It supplies no native effect, time, input receipt or
resource-retirement fact. Each parent binds its byte length and SHA-256,
logical closed label, actual query tag and ordered child descriptors. Each
child binds the same parent, observing role, SDK subject and original offset.
The caller must durably retain every parent and planned/opened/saved child
transition before the writer proceeds.

A 512 KiB raw segment occupies one canonical file below the existing 1 MiB
file limit. Near-2 MiB valid UIKit2 originals use four actual files. No raw
source, shared storage bound or native DTO is enlarged or rewritten.

`inspect()` reads actual opened-file prefixes, including empty inodes.
`retained()` compares their original lengths, hashes and completeness before
later historical use. A complete opened file is readable without pretending a
saved acknowledgement arrived. An incomplete file remains an owned byte
prefix and cannot supply a complete native original. Reads reject changed
parents, offsets, subjects, hashes, hardlinks and dangling planned paths.

Host tests use real private files and an explicitly modeled UIKit2 producer.
Its actual ordinary host callbacks produce contact/dispatch history; pooled
native-object lifetimes remain separate from quiescence. The largest valid
source below the unchanged 2 MiB reader limit is decoded before and after
segmentation. Native compilation and real UIKit execution remain unverified.
This storage component does not advertise an Avatar area capability.
