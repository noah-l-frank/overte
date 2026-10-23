# Lossless original bundle parts and private host diagnostics

Version 1 `chat-source-bundles` stores a complete original canonical JSON value
using the existing immutable `ChatSourceChunks`. It grants no live owner,
source query, current observation, input, release or successful journey result.
Every consumer must still validate its actual complete feature DTO and source
ownership after reconstructing the original bytes.

The complete canonical value is compressed with the existing zlib/base64
encoding. Its encoded string is split into ordered parts, each no larger than
half the unchanged 48-KiB packed-leaf limit. Every part is then stored as an
ordinary existing source chunk. Its exact closed fields bind part version,
logical bundle sequence, part index/count and literal data. The root reference
binds the complete original uncompressed byte count, SHA256 and part count.
Decoder EOF/tail checks, canonical base64, complete raw SHA and exact canonical
JSON equality reject truncation, reordering, duplicate/escaped aliases and
mixed bundles. No original field or byte is discarded.

All parts consume the existing total 512 physical-frame and 16-MiB physical
raw budgets. Original logical canonical values also consume a separate check
of the unchanged aggregate 16-MiB uncompressed JSON budget, including their
original list framing. Compression cannot conceal a logical overrun. The
48-KiB packed-leaf and 64-KiB private-file limits remain unchanged. Reference
counts use exact integer types, and the input JSON rejects container/type
aliases before serialization.

`original()` rereads every selected original part under its actual already
admitted physical identity, scope, manifest digest and index. It checks the
complete inventory before and after reconstruction. The caller retains its
root/phase/final-clock checks and may publish `ready` only after every part is
durable and the complete original has been reconstructed. A partial/lost write
must remain unresolved; this codec provides no adoption, deletion or retry.
It does not change legacy chunk/Native DTO interpretation.

The initial consumer is the source-test-only version 1 `chat-host-diagnostic`.
Its private root stays `reading` through every actual part write and becomes
`complete` only after exact reconstruction. Existing roots are never
overwritten. Its explicit scope is `host-diagnostic-not-source-admission`.
Complete reports and suppressed exception-context chains use this format
instead of one oversized private file. A real failing `pack()` frame's exact
unpublished raw bytes, hash and original encoded length can be retained without
claiming that incomplete candidate as a committed/fresh source sample.

The full manual test preserves the original source/cleanup exception even if
its diagnostic write fails. It attempts the error diagnostic once, retains
partial originals and does not retry. If execution itself succeeds, report
loss still fails the test before application/final-archive operations. The
shared engine, actual input owners and all observation windows are unchanged.

Eight focused cases cover a real oversized `pack()` input and flat-file
refusal, exact multi-part reconstruction under unchanged leaf limits, every
part/logical-byte budget, order/missing/foreign/bool/hash failures, actual lost
part writes with no replay, same-byte physical replacement, suppressed raw
failure context and report failure preserving the original exception. These
plus the two existing original prepared-journey cases passed 10/10 in 4.131
seconds. This packet does not yet migrate the live remote reader/returned graph
to segmented records, and it provides no new whole-journey qualification.
