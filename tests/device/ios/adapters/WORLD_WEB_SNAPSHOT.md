# Passive native World Web snapshot prerequisite

`IOSWorldWebSnapshotObservation` calls existing passive original getters under
E2E+iOS, `--testScript`, and the actual application main thread. It changes no
product input, document, callback, queue, resource, or retirement state. Native
sources remain uncompiled and unexecuted in this source-only session.

The closed command is `{schemaVersion:1,commandId,action:
"feature-ios-world-web-snapshot",runId,fixtureUrl}`. The private output file is
`feature-ios-world-web-snapshot.json`. `IOSWorldWebSnapshot` exposes
`read(run,fixture_url,*,native_before_floor=None)` through the existing guarded
HTTP/AFC path. Its live packet and lossless body contracts are version 1.

The native snapshot retains an immutable actual source instance, acquisition
sequence/start, exact internally generated getter commands, ordered call
brackets, and each original returned JSON string. LedgerBefore precedes the
asynchronous DOM read. Every poll uses the same actual inner DOM nonce;
pending payloads retain the full original call prefix. Every pending native
DOM packet passes its own schema validator at its actual call time. Repeated
pending replies remain identical; a terminal reply preserves native birth,
increases its actual sequence, and cannot move its capture clock backwards.
The reader retains pending originals across polls and rejects an outer restart,
rewritten prefix, or clock advance without a new actual getter call.

After DOM readiness the snapshot obtains original World, Work, Geometry,
privacy-qualified Keys2, Pointer, Entity lifetimes, and LedgerAfter sources.
An absent document stays null. Global Qt key originals contain no private text.
Individual source grammar, byte bounds, clocks, process identity, original
freshness, and callback ownership retain their existing meaning. UIKit and Qt
widget observations remain outside this snapshot.

The body is Qt qCompress: a four-byte big-endian length followed by one zlib
member. Limits are 8 MiB plain, 1,500,000 compressed bytes, and 2 MiB total wire.
The strict decoder checks canonical base64, both byte counts and SHA-256 hashes,
the declared bound before decompression, actual decoded bounds, EOF, no preset
dictionary or trailing/concatenated members, duplicate keys, and nonfinite
numbers. It never uses unbounded decompression or flush.

There are at most 512 known nonces, eight pending acquisitions, and 64 actual
calls per acquisition. Only two completed compressed bodies remain cached;
older known nonces return explicit unavailable and never recapture. Pending or
unavailable output, body eviction, and a successful original DOM result do not
prove callback return or native resource drainage. Existing original callback
and weak lifetime ledgers remain mandatory for whole cleanup.

Host tests exercise real Python validation and lossless transport bytes against
explicit native/Qt models. They include all pending originals, native and outer
history resets, held callbacks after eviction, privacy downgrade, malformed
compression, and a high entropy original body exceeding 2 MiB plain while its
actual compressed wire remains within the fixed transport bound. This packet
alone does not qualify or advertise the complete World Web feature.

## Detached projection copies

Each selected projection still validates its exact parent, original ordinal,
actual read membership and unchanged private file identity. Its outward value
can now use the existing in-memory JSON graph copier. One detached result from
that copier replaces the literal deep copy for supported builtin graphs; no
decoded verdict or current observation is reused. Changed helper aliases, code,
defaults or copying semantics retain the original copying behavior and error.

Six new and six existing projection cases pass in 0.341 seconds, retaining 18
original files with 7,998 source/launcher/reference pins unchanged. They cover
Snapshot1 and Whole Snapshot2, independent returned values, graph aliases and
cycles, Unicode, changed copiers, fresh original-read scopes and same-byte
inode replacement. All owned process/thread and retained-original checks pass.
This targets copying costs measured in the failing normal World Web action;
it does not qualify that full journey or change its 25-second API budget.
