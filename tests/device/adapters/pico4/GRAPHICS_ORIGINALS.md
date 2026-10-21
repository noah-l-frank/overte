# Original stereo PNG and native metadata ownership

`graphics-journey-originals` v1 stores whole unchanged world-render v4 PNGs and
separate original native JSON metadata under the
[independent stereo evidence profile](../../native/STEREO_GRAPHICS_EVIDENCE.md).
The original PNG storage protocol is adapted from the frozen source recorded in
[`FROZEN_REFERENCE.json`](../graphics_journey/FROZEN_REFERENCE.json). Phone image
readers and files remain unchanged.

Each record pins candidate/process/session binding, run, primary/actor role,
restart stage, ticket, original capture, kind, exact derived filename, original
byte count/SHA-256 and actual file device/inode. Metadata is bounded to 2 MiB;
PNGs retain the existing 32 MiB bound. Their original capture epochs are never
changed. Native metadata must have the closed original schema and exact matching
run/role/stage/ticket/binding/capture; it carries no requested or expected facts.

`write()` validates original bytes, calls the durable owner's intent before
creation, creates a new mode-0600 file exclusively, then records actual opened
inode ownership before writing any bytes. It flushes/fsyncs, rechecks original
bytes and only then requests a saved intent. A failed callback, lost saved write
or existing filename keeps the unresolved original; no file is overwritten or
removed. The parent owner must use `transition()` under its actual source lock
and compare-and-swap journal. Immutable fields, inode changes, phase skips and
regression cannot be accepted as new history. This helper does not create a
second journal or replace the full sample transaction.

Reads require a regular, owner-only, single-link file with original device/inode,
size and hash. Symlink/hardlink, replacement, truncation, changed mode, lost guard
and expired/regressing monotonic budget fail. The complete file operation is
bounded to five seconds. `archive()` validates historical storage only; it has
no current clock, live native read, input, repair or retiming API.

A PNG's storage hash/inode cannot establish its action ticket by itself. Exact
ticket history belongs to the immutable owner transition and independently
decoded original challenge in each eye. Metadata independently pins its original
ticket. Original files do not replace fresh native/fixture/process observations
or actual effect/cleanup verification. The role/process sampler and complete
Graphics coordinator remain required; no complete capability is advertised.
Host fixtures exercise storage logic only. Native source is uncompiled and all
devices are untested.
