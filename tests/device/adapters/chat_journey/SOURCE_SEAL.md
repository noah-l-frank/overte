# Warm original Chat source seals v1

`ChatSourceSeal` freezes one actual warm cleanup `ChatObservationOwner` or
`ChatCleanupWitness` before those originals can enter the final archive. It
does not run a baseline, retire a journal, close native/Qt/process/host
resources, publish another sample or grant capability. It adds no source
timestamp and does not turn a historical sample into a current one.

The seal binds a once-only optional freeze guard to the exact operation
objects. Existing callback ownership cannot be replaced. The guard is checked
before and after acquiring the original source locks, and again before the
publisher's POST. The default unbound path is unchanged. A durable sealing
intent, any unknown seal failure or actual completion prevents subsequent
source queries/publications before any new CAS or transport. A cold owner may
not adopt either an existing root or rootless original chunks.

`run()` requires complete ready source rows. It rereads all physical chunks,
compares them with the mutable in-memory rows/frames/transaction map, and
preserves root and chunk manifests/digests. Original root identity includes
device, inode, mode, UID, link count, size, mtime and ctime; chunk identities
have the same complete stamp coverage. Identical rewritten roots are refused.
All target/query limits remain unchanged. The root records
`chatSourceSealVersion`, `runId`, `role`, `binding`, `peerBinding`, `kind`,
`journal`, `phase` and `originals`. Each original has `journal`, `sha256`,
`chunkCount`, `stamp`, `chunkManifestSha256`, `framesSha256` and
`chunkStampsSha256`.

The original native/host 1.5-second checks include the complete physical pass,
sealing and sealed CAS, final result copy and last seal-stat read. Native guards
and clocks run after the seal-specific filesystem checks. Source-lock exit
also performs real metadata checks; the same frozen original clock functions
and epochs are checked again after successful lock exit, without guard/lock
reentry or another query. No new target query refreshes an older source. The
returned root is marked completed only after those final checks actually
return. A sealed-looking disk row with a
lost CAS/return or stale final clock remains unknown and cannot authorize
retirement or another attempt.

`receipt(returned_value)` accepts only that actual warm completed owner and
the exact received value, physical seal stamp and unchanged original files.
It is a historical closure receipt. It does not call old-PID native guards or
reacquire the actor's source locks. The parent may therefore validate received
frozen originals while holding its distinct lock objects at the same flock
inodes, including after controlled process finalization. It does not assert
that cold objects or old host descriptors survived. Actor sealing itself must
finish under the actor's own locks before the parent takes its locks.

Pico's fixed `_chat_source_seal(..., witness=...)` accepts only the declared
primary cleanup observation or independent cleanup publisher paths and binding.
Both seal paths and their rootless chunks keep generic cleanup closed.
Actual baseline consumption and full archive catalog inclusion remain the
next composition; no public/cold-RPC or whole-feature claim is added.

Ten focused source cases are covered by the initial five-case pass in
79.321 seconds, a three-case follow-up in 45.449 seconds, and the final
last-stat/positive follow-up plus actual Pico orphan case in 34.371 seconds.
They cover original primary/actor closure without another native query,
callback ownership, lost final receipt, frozen-host native jumps during final
CAS/copy/stat, changed physical roots and mutated cached historical rows.
Two exact final-clock/source-lock-exit cases subsequently passed in 28.455
seconds, including a real failed lock exit. The updated positive plus the
earlier metadata-jump case passed in 29.144 seconds. The actual Pico
seal-factory case separately passed in 2.518 seconds. Native,
V8, widget and input metadata producers are explicit seams; the factory case
uses an actual owned Linux stdin worker. No product app, AC, service, device
or OpenXR runtime runs.

The source module offers three disjoint catalog selectors:
`source_seal_positive_tests()` (one case), `source_seal_admission_tests()`
(five) and `source_seal_freshness_tests()` (four). Keep their existing
120-second catalog budgets separate under host load. The combined recovery
convenience selector and entire module must not also be registered alongside
those three. No full archive repetition was performed.
