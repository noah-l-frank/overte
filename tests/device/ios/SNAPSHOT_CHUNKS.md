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
