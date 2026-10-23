# Original independent Chat observer process

`LinuxChatObserverProcess` and its `chat-observer-process-presence` version 1
result qualify the original Linux host process separately from native Pico and
AssignmentClient ownership. The fixture controller must supply the original
live PID/start/boot identity, exact reviewed entry and private configuration
paths, expected executable/entry SHA-256 values and its actual ownership
predicate. These inputs cannot be inferred from the Pico revision, an Actor
result, a historical build receipt or an already absent process.

The reader reuses `LinuxChatActorProcess` for actual executable descriptors,
kernel UID/start/boot, ownership and directory checks. It additionally retains
an original entry-file OFD pair and checks the full original entry bytes and
physical stamps. The complete command line must be exactly the interpreter,
reviewed entry, `--config`, and the original private configuration path. No
`-c`, `-m`, extra argument, alternative entry or configuration alias qualifies.
The configuration's original physical metadata is checked without reading its
credential-bearing contents. Cached program hashes and input stamps remain
bound to their original admission.

`require_absent()` keeps both originally acquired OFD pairs and performs two
actual `os.kill(pid, 0)` ESRCH checks, each also requiring the original PID's
`/proc` path to be absent. A live process, zombie, reused PID, changed source or
lost descriptor remains unavailable. The result is copied before the final
source and kernel checks. Both original monotonic elapsed time and host epoch
age must remain within 1.5 seconds. The method never discovers processes,
launches one, sends a nonzero signal or accepts a stop acknowledgment as
absence. The caller still owns the reader's two host descriptor pairs and must
close them through the real `close()` implementation.

The result contains `chatObserverProcessPresenceVersion`,
`sourceRole=independent-chat-host-observer`, the original `hostProcessIdentity`,
`queryProcessId`, `presence=absent`, `errorSymbol=ESRCH`, observed qualified
`executableSha256` and `entrySha256`, original `configurationStamp`, and actual
`requestedEpochMs`/`capturedEpochMs`. This is a current kernel absence sample,
not an exit-status or complete Actor graph receipt.

Seven tests use temporary reviewed Python stdin workers with explicit private
test ownership, actual executable/entry hashes, original Linux descriptors,
kernel start times and real process reaping. They cover live refusal, real
absence, cold acquisition refusal, same-byte configuration replacement,
wrong program/start/arguments, cached hash mutation and a frozen monotonic clock
with a 2000 ms final-copy epoch jump. The focused run passed 7/7 in 0.145 seconds.
No product App, AssignmentClient, observer entrypoint, service or device runs.

The complete Parent path still needs the original process acquisition before
Actor shutdown, a fresh returned-byte consumption handshake with that same
Actor, immutable graph validation and the final actual absence sample. This
reader does not adopt unknown Actor journals, qualify a hermetic native binary
graph, replace missing final CAS/return evidence, or enable public Chat.
