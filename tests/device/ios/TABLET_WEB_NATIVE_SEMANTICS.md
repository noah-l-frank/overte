# Exact native semantic validation reuse

`tablet_web_native_semantics.py` is a context-local, per-runtime optimization
for the nine existing pure Tablet native DTO validators. The default has no
selected memo and executes the original validator. There is no new persisted
schema, native source, capability, limit increase or authority.

Keys retain the exact canonical PID, packet, query and previous original,
plus actual module/validator identities and validation kind. Numeric argument
types remain distinct. Only successful validation can create an entry. Unknown
or unserializable input keeps the original validator's failure path. The cache
stores no product result, and is bounded to 512 entries and 32 MiB of exact
argument bytes. Nested scopes reset normally, including exception exits.

All original file/fragment reads, inode/permission/link checks, hashes, raw
parsing, ownership journals and surrounding prefix rules still execute. A new
source birth, counter, query, PID, pending transition or previous original is a
different input and must be validated. No current clock, reader freshness,
input, SDK/process guard, recovery or publication behavior is memoized. The
initial standalone privacy check before writing a live raw reply is unchanged.

The scope is selected by the unfinished whole runtime. Pure historical replay
also uses the same selected runtime memo. The exact native modules still own
their original grammar and continuity decisions; no normalized facts or other
feature DTOs are used as substitutes.

Six focused host cases pass, including real validation failures for altered
PID types/nonce/source birth/counter, all nine actual validators under forbidden
file I/O, strict cache bounds/default/nested scope behavior, and actual original
read membership plus hardlink refusal. The existing fourteen Packet/WAL tests
also pass under a selected memo, including unsafe raw privacy, pending-to-ready
transitions, abandoned floors and lost-send/no-resend recovery. Native hooks
remain uncompiled and unexecuted. This is not complete-journey or device timing
evidence.

The integrated deferred command exposed a separate original-read boundary:
historical Packet construction previously passed a forbidden live guard into
its immutable file readers. Historical originals now use a read-only guard;
every existing live mutation and its before-write intent still rejects a
historical owner. The sixth case reads actual retained raw files with a live
guard that throws, then proves capture/save cannot query or alter any file.
