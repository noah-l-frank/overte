# Phone original Emote PNG files, version 1

`PhoneEmoteImages` extends the existing `PhoneGraphicsImages` private-file engine.
Both run the same real-filesystem ownership/interrupt/security tests. Existing
Graphics v1 records, names, stages, limits and archived bytes remain compatible.
There is no second filesystem implementation or native image generator.

An Emote record is exactly `emoteImageVersion:1`, actual `binding`, `runId`,
`role`, `stage`, `ticket`, complete original `capture`, `name`, `phase`, `file`.
Role is `primary` or `actor`; stage is the actual acquisition index 1–256.
The original GPU capture owner retains its independent 256-capture bound.
The name is `emote-<run>-<role>-<index>-<capture-request>.png`, at most 120 ASCII
characters. Different roles/acquisition indices cannot adopt identical bytes
from another scope. Graphics records and names cannot be read as Emote records
or vice versa. No expected result, native selector or arbitrary path is stored.

The actual parent is private and canonical. Original PNG digest, pixel digest,
dimensions, PID and capture envelope must validate before any write intent.
Exclusive 0600 file creation is preceded by durable `planned` intent with null
file identity. The actual new device/inode is persisted as `opened` before bytes
are written. After flush/fsync and independent original file read, `saved`
intent is persisted. Existing callback/atomic metadata limits are unchanged.

A lost planned/opened/saved return preserves the corresponding responsibility.
A preexisting file is never overwritten or adopted. Reads reject missing,
changed or replaced inodes, mismatched digests, links, exposed permissions,
foreign roles/indices/bindings and invalid versions. Absence is separately
inspected; it never returns an empty successful PNG. Final decoding, callback,
guard and filesystem work consume the existing five-second operation budget.
Historical `archive` returns only original bytes/timestamps and invokes no SDK,
repair or native query. It does not make old evidence current.

The caller must durably preserve each callback record and validate legal
planned→opened→saved transitions. This file component owns no native lease,
fixture, camera, browser or run. The existing render owner must still retire
actual native buffers/callbacks and issuer receipts; the complete Emote owner
must join original source/pixel/actor facts and whole cleanup. PNG artifacts can
remain retained private evidence after the active ownership journal is retired.
No complete capability or device acceptance follows from successful file IO.

Seventeen Emote host cases include the fourteen existing real Graphics file
counterexamples plus explicit Emote version/scope/index coverage. Graphics also
runs its original fourteen cases independently. Native code is uncompiled,
all devices untested, and complete Phone areas remain three of fourteen.
