# Immutable source-file guards

Reading an already owned private source file does not acquire product data.
`IOSAvatarSources` now checks the complete live candidate guard before and
after construction, including reader-history restoration. Its immutable
`IOSAvatarOriginals` reads use the actual held source lock and retain every
existing file identity, mode, link-count, byte/hash and deadline check.
Captures, every source journal save, native transports and final returns keep
their complete live candidate checks. No native DTO, source history, source
prefix, schema version or public fact changes.

Explicit historical construction is SDK-free and still fully decodes every
original source packet and history. Its storage-intent entrypoint refuses
mutation before changing even its in-memory pending state. Historical data
does not become a fresh observation through this reader.

Three real-original-file counterexamples cover live entry/exit authority,
candidate change after an actual old-file read, and historical construction
with a forbidden live guard. In the three-frame fixture, live reconstruction
uses two candidate checks instead of eight and issues no source/native query.
The source/recovery regressions and planned-path counterexample also pass
(17 tests). Native/Qt producers are explicit host models. This is no physical
CPU, SDK, native-build or iOS timing qualification.

Separately, `IOSAvatarSourceRecovery.file()` uses `os.path.lexists` for a planned
pathname. A real dangling symlink is an existing filesystem responsibility;
it cannot be recorded as absent or cleared by abandonment. The focused case
creates that actual symlink before the original file opens and verifies that
recovery refuses it without sending another query. The private wire format
and all existing recovery originals remain unchanged.

Each source-group join validates its current typed channel once, with the
complete previous-packet checks in the same call. It no longer validates the
current packet twice before returning the same frame. All native, process,
run, clock, acquisition and history checks remain mandatory. The actual
repository's combined source suite passes 24 cases, including the historical
recovery and original-readset cases described in `AVATAR_RECOVERY_PREFIXES.md`.
