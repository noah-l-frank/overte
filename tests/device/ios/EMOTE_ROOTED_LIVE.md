# Rooted Emote live original journal

`IOSEmoteRootedLive` retains each actual cleanup cut for later qualification by
the existing terminal window protocol. Both roles use the same closed owner.
Metadata contains at most 96 small index/hash/length/device/inode references.
Each immutable `OriginalFrameStore` file contains the actual five-envelope
[component snapshot](EMOTE_ROOTED_ARCHIVE.md) and its measured-graph digest.
The shared one-MiB original-file and 64-KiB metadata limits remain unchanged.
Fixture URL, phase instance and image policy are fixed by the original owner
and checked against every snapshot along with both process bindings and locks.

Reading a record derives its public state, source public DTO, held resources,
ticket, acquisition and scene retirement from the original graph. A stored
digest is only an integrity join. It cannot establish facts independently.
The existing bounded `AvatarRecordCache` is reused as an operation-local
immutable-record primitive: two actual cold decodes, exact contributing file
signature inventories, read-membership restoration and refusal after any
change. Mutable current metadata is checked outside this cache. No source
timestamp or acquisition clock advances on replay.

Appending an identical snapshot is idempotent. Distinct cuts require advancing
measured sequences and original acquisition order. Current metadata detects
unaccounted originals; a read-only archive can revalidate an exact older prefix
after later cuts. Selection matches complete actual public observations, not
requested sequences or expected baseline fields.

A pending save records the exact selected cleanup reference and snapshot and
measurement hashes before immutable file creation. Original file intent then
records planned/opened/saved phases and actual observed file birth. Recovery
adopts only the same fully written opened/saved file. A planned-only file stays
pending, including when a file now exists: its inode cannot be guessed. No
native query or ordinary input is replayed by this file-only recovery.
An uncertain metadata-write return poisons that in-memory writer. A new owner
must reopen the actually committed journal before it can continue.

The rooted coordinator records its measured cleanup public result through this
journal for both roles. Before another cleanup acquisition it reopens earlier
responsibility and resolves a fully saved pending original first. The default
version-one coordinator keeps its existing path; no capability is broadened.

Two connected host cases initially pass in 98.870 seconds: compact idempotent
storage, pure archive replay, original tamper refusal, saved-return loss with
same-inode recovery, and planned unknown birth retaining responsibility.
The corrected three-case packet passes in 168.615 seconds, including loss of a
completed metadata commit return and mandatory owner reconstruction. An earlier
additional test run failed with a misplaced test block (`NameError`); that test
driver error was corrected and is not counted as a pass.
After the final context joins, the integrity/schema/context/orphan case passes
in 73.510 seconds. The connected existing whole-coordinator case passes in
277.076 seconds through ordinary playback, both role journals and real loopback
Actor scene3 publication. It independently reopens both latest typed graphs
and matches their actual cleanup references and resource aliases.

The subsequent [terminal-window packet](EMOTE_TERMINAL_WINDOW.md) verifies
three original pairs and their independent Actor publications, and adds a pure
description/seal join. Whole terminal-controller persistence, remaining-owner
archival, once-only per-role Stop/OS/SDK end and canonical and worker replay
still require implementation and verification. These declared model clocks
do not qualify real operation budgets.
The native/Qt/GPU/SDK/clocks are declared models. The journal alone does not
establish paired quiet, process death, SDK deletion or complete Emote capability.
Native compilation and device tests remain unexecuted.

The five no-build project suites pass in 6.92 seconds. Contract-version and
whitespace checks pass; none of the eight guarded packet runs attempted a
blocked operation. No build, compiler, device, simulator or laboratory ran.

The first three-pair host attempt was interrupted for measured repeated archive
work, with no pass claimed and all 855 original files retained unchanged.
[Scoped historical validation](EMOTE_ARCHIVE_ROUND.md) now replays its actual
Primary two-cut graph in 29.046 real seconds, within the unchanged thirty-second
bound. This is narrower than full terminal qualification, which remains open.
