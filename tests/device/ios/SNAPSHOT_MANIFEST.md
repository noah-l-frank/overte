# Owned original Snapshot manifests

`SnapshotManifest` adds a separate durable owner for the existing closed,
read-only `snapshot-files` list operation. It does not change native capture,
storage, input, public permissions or file deletion. The legacy UI-component
`SnapshotFiles` reader retains its original contract and scope.

The owner requires the canonical candidate/session/process context, held source
lock and candidate guard. These are admission prerequisites; this transport
does not derive installed-code identity from a PID. Every live operation also
checks the actual foreground process through the existing `FeatureObservation`.
Only a controlled run prefix and the five existing Snapshot filename modes are
admitted. Each owner has one private run/role/index journal and one query UUID.

`reserve` durably retains that exact query. `send` starts an independent native
clock acquisition and persists `issued` and its original before-clock before
the HTTP boundary. The final transport guard includes foreground verification,
the enclosing guard and the unchanged 1.5-second acquisition deadline. An
issued query cannot send again, including after a lost HTTP return or process
reconstruction. Passive AFC recovery reads only the retained nonce. An expired,
absent, erroneous or foreign receipt remains unresolved and owned.

The raw list response is bounded to 8 KiB and parsed with the existing strict
duplicate-key/NaN-rejecting decoder. Its exact schema, success, PID, nonce,
prefix, sorted unique controlled filenames, revisions, hashes, sizes, eight-file
limit and 256 MiB total bound are checked. An independent new native after-clock
joins the actual response timestamp to the original before-clock using
`NativeClockAcquisition`. No host timestamp replaces the native sample, and no
empty list is synthesized from an unavailable/error response.

The complete original query, response and native clock join are written to an
immutable private `OriginalFrameStore` file. Planned/opened/saved descriptors
are durable before the corresponding storage action. Reconstruction adopts a
lost saved-file return by revalidating that actual inode, bytes and hash, without
an AFC query, native clock read, file rewrite or new time claim. An incomplete
opened file remains owned and cannot be replaced or authorize a new query.
`history` constructs a file-only reader without a native SDK or transport.

`absent` proves only that this bounded historical manifest was empty for the
exact run and mode. `quietWindowRequired` remains true. A complete pending
cancellation must separately join the actual normal input owner, script/timer
and native worker originals, repeated fresh manifest absence and final quiet
ownership. Nonempty manifests remain visible; this owner neither acquires image
chunks nor deletes private files and does not advertise whole Snapshot support.

Nine explicit no-build host tests exercise actual private journals, HTTP/AFC
transport and fixture validation over modeled native filesystem/clock sources.
They cover lost HTTP and saved-file returns, incomplete writes, foreign and old
responses, strict manifest bounds, process changes, an expiring final send guard,
and file-only revalidation after SDK retirement. No compiler, simulator or
device was invoked; native implementation and physical acceptance remain
unexecuted.
