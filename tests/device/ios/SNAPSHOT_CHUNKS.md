# Bounded original Snapshot chunks

The existing gated iOS `snapshot-files` producer now additionally accepts a
closed version-2 `read` request with exactly `chunkBytes: 524288`. Version 1
keeps its existing list/read schema and 4 MiB chunk size. Version 2 cannot list,
choose another chunk size, supply bytes, select another directory or change a
file. Its original filename, offset and source-owned revision checks remain the
same. Native reads still check the actual open descriptor and source directory
before/after reading; the response reports its actual version and EOF.

The real fixture and iOS HTTP transport admit this exact new schema. A separate
probe branch claims each version-2 query nonce before native entry, including an
unknown return, and never resamples it after another query. Missing/busy native
support remains unresolved; the legacy version-1 branch retains its behavior.

`snapshot_chunks` strictly checks the version-2 packet, native PID, exact query,
original revision, size, offset, fixed byte count, EOF and canonical Base64.
The largest chunk response fits an explicit 704 KiB decoder ceiling, within the
existing generic 2 MiB maximum. Neither the default decoder nor original-frame
limit is raised. Reassembly requires every uniquely queried original in exact
offset order, a constant original revision and size, nondecreasing native sample
times and the independently observed complete file hash. Even an empty original
requires one actual zero-byte EOF response and its real whole-file hash.

Seven explicit no-build host checks cover real private multichunk files, exact
byte equality, changed/missing/reordered chunks, stale clocks and nonce reuse,
strict versions/bounds/EOF/Base64, actual fixture admission, the actual Node
probe and existing HTTP/AFC transport. Native filesystem calls are modeled in
these checks. The C++ producer remains uncompiled and device-unexecuted.

These codecs do not supply the whole capture/file owner. The adapter must still
durably own every query before sending, retain all immutable original packets
and partial files across interrupted writes, join independent native clock
brackets, recheck the final native manifest, and observe actual native file-job
and artifact retirement. No new complete capability is enabled by this source
prerequisite. The old UI-component Snapshot reader remains scoped as before.

## Durable chunk query owner

`SnapshotChunk` now extends the existing manifest query owner with a closed
byte-chunk profile. Default manifest JSON, paths, bounds and version-1 files
remain unchanged. The new profile has separate chunk journal/frame namespaces,
a distinct version-1 owner and an explicit bounded version-2 native query.
It selects the filename and revision from an actual retained manifest row;
missing filenames, unaligned offsets, extra EOF reads and foreign manifest
bindings cannot reserve or send a query. Full-file coordination must retain
that originating manifest alongside every chunk.

The owner persists the actual query and independent native before-clock before
one send. Reconstruction never repeats issued work. A lost native return can
read its actual AFC original; the unchanged native clock join and full raw
packet are retained in a private inode/hash-bound `OriginalFrameStore` file.
The original-frame 1 MiB ceiling remains strict, including clock originals; an
oversized source fails and stays owned. Lost saved-file returns adopt the same
original locally without another AFC/clock request or file rewrite. Incomplete
opened files stay owned and block replay. A file-only historical constructor
requires no SDK and preserves original native timestamps.

Seven composed host checks exercise real private multichunk originals, actual
HTTP/AFC transport over native boundary models, durable pre-send queries,
native/saved-file return loss, interrupted files, exact real manifest row/offset
selection, unchanged default manifest profiles, separate namespaces and
file-only revalidation. As with the source checks, modeled native clocks do not
qualify physical deadlines. Artifact assembly, final manifest verification,
image/outcome proofs, native file-job joins and whole paired cleanup remain
the next integration work.

## Full original file join

`snapshot_original_file.original` now reads the retained manifest/chunk owners
and joins their actual originals. Both manifest inventories must be identical;
the complete file bytes must reproduce the original manifest hash and revision.
The owners share the full run/role/process/candidate binding, private directory
and source lock. Chunk indexes and offsets remain ordered without duplicates.
Every independent native clock keeps its original nonce, source birth,
sequence, lifecycle counters and timestamp across the complete read sequence.

The separately acquired native file-work original must follow the final
manifest. Each query must have exactly one actual job, with its packet sample
inside the actual entered/publication interval. Every observed job must have
returned, reached its finally boundary and separately lost its last weak
capture. A cached functor remains held even after successful publication and
return. Missing jobs, failed publication and foreign or incomplete sources
cannot produce the joined file.

This pure historical join returns a version-1 fact and private original bytes.
It does not access the SDK or write an artifact. The enclosing feature must
retain the actual file-work original and every participating owner, durably
own any assembled artifact, verify real image and destination outcomes, and
complete independent quiet-window and paired cleanup. These requirements are
explicitly retained in the fact; no complete capability is enabled here.

Five composed no-build tests use real private multichunk files, immutable
owners, HTTP/AFC transport and actual host cached-functor weak lifetimes.
They reject changed final inventories, source-birth changes, missing/reordered
or modified original chunks, live/failed/unknown jobs and foreign sources.
Native file IO and clocks are modeled; this does not qualify an iOS device or
physical acquisition deadlines.
