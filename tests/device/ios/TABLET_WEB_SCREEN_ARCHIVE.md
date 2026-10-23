# Tablet original screen byte archive

This component owns original PNG bytes only. It establishes no page identity,
capture time, WK/UIKit lifetime, rendering effect or complete feature result.
Native instrumentation remains uncompiled and devices remain untested.

`TabletWebScreenArchive` accepts the original `nativeScreenRawVersion: 1`
receipt: the actual WDA request nonce, unchanged native-screen transport,
session/PID, byte count, SHA-256 and decoded PNG extent. The receipt deliberately
contains no invented native capture timestamp or GPU frame ID. `with_capture`
requires every original raw field to match a later genuine existing
`screenCaptureVersion: 1` record; those original native/host brackets remain
unchanged and must be independently joined by the full feature owner.

The closed `tabletweb-screen` profile of `OriginalPacketSegments` has only the
`png` label and `primary`/`actor` subjects. Its namespaces are
`tabletweb-<role>-screen-parts`; parent/body/frame/original DTO keys remain
Tablet-specific. Existing Avatar, Tablet-source and Snapshot profiles are
unchanged. Bounds are unchanged: each segment parent is at most 4 MiB, each
raw fragment at most 512 KiB, and each immutable file at most 1 MiB. A valid
original PNG may span at most six segment parents within the existing 24 MiB
PNG bound. No generic storage limit was increased.

The caller's durable `intent` callback runs before each parent/child progress
transition. `read` requires a complete parent. `retained` can revalidate actual
complete opened bytes after a lost flush/return without changing any phase.
`inspect` retains actual incomplete prefix lengths/hashes and exact original
inodes. It never supplies a complete PNG verdict for missing/incomplete data.
These originals can survive later removal of the separate owned PNG export
file; final authority and cleanup still belong to the full feature owner.

Three no-build host cases exercise actual private files and original PNG bytes:

- An actual entropy PNG larger than 4 MiB spans two segment parents and nine
  contiguous bounded immutable fragments, reconstructing byte-for-byte with
  0600/single-link ownership.
- A complete original opened file remains readable as retained bytes after
  a real injected failure before the caller saves the child completion. The
  last durable parent remains opened; reads preserve its phases and file inodes.
- Foreign parent hashes/nonces/extents and replaced original inodes fail.

Required contract rows, all writer 1/read 1:
`ios-screen-png-raw-original`, `ios-tablet-web-screen-archive`,
`ios-tablet-web-screen-segments`, `ios-tablet-web-screen-segment-body`,
`ios-tablet-web-screen-segment-frame`,
`ios-tablet-web-screen-segment-original`.

This packet depends only on committed original-screen/immutable-file/segment
code plus the additive closed profile. It imports no unqualified whole Tablet
Runtime, Sample, Feature, worker, cleanup or terminal owner.
