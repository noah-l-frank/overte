# Original Pico location bookmark storage

`native-location-bookmarks` v1 is a passive component of the unfinished
Worlds/navigation adapter. It enables no feature capability and supplies no
page, cancellation, arrival, restart, image, peer or cleanup verdict.

The private Pico `_location_bookmarks(target)` factory retains the existing
candidate/process guard, native command transport, bound device clock and fixed
private artifact reader. Commands contain exactly `schemaVersion: 1`, a fresh
32-hex `commandId`, action `feature-location-bookmarks`, and 32-hex `runId`.
Names, addresses, filesystem selectors, setters and expected results are
forbidden. This initial reader is Pico-only and accepts no iOS nonce alias.

The original probe calls `Test.featureLocationBookmarks` and publishes its
nonce-bound original to `feature-location-bookmarks.json`. Absent hooks or
failed sources are unavailable, never empty successful inventories. The API
requires both `OVERTE_E2E_FEATURE_TESTS` and `ANDROID_APP_PICO_INTERFACE`, test
launch, the existing private results directory and active lifecycle source.
It rejects reused nonces and stops after 4096 queries per native process.

On its owning GUI thread, `LocationBookmarks` reads its actual protected map,
error state and configured backing file. It neither invokes the script API nor
reloads, writes or repairs storage. Product permission checks are unchanged.
Bounds are 4096 string entries and a 4 MiB map/file. The actual regular file
must belong to the process UID, have one hard link and open without following a
final symlink. Descriptor/path identity, size, link count and nanosecond
modification/change timestamps must stay stable around the bounded read.
Failed access, malformed JSON, original load errors or uncertain replacement
cannot establish persistence.

Packets retain count/SHA-256 of the full native map, separate count/digest of
all unowned entries, and only `e2e-<run>` / `renamed-<run>` with address digests.
Original file-byte and revision hashes remain separate. Nanosecond values are
hashed before JSON serialization to preserve precision. Paths, unowned names
and URLs, inode and UID remain native. A missing file is null and requires an
empty native map. The host rejects a parsed disk/map mismatch. An unchanged
map with changed file bytes or revision stays visibly changed storage.

The host sends once and requires actual nonce/run/PID/native instance,
advancing sequence and fresh timestamps within five seconds and 51 reads.
Guards run before/after acquisition. Time reversal, late replies and source
replay fail; caller mutation cannot alter the retained cursor.

Next join actual Pico Places controls/model and these independent storage reads
in the shared fifteen-step journey. Cancellation must preserve original storage
for three seconds; mutation/restart/cleanup must preserve every unowned entry.
Selected origin, account, maturity/federation settings, named-lookup modal,
stereo arrivals and peer lifetime still need their whole-area coordinator.
The normal directory-server field can log out an account when switching servers;
preflight must refuse an account that cannot be restored without changing
private credentials.

Host verification executes the original probe, actual Pico factory with mock
package/transport boundaries, and synthetic native packets for ignored, stale,
foreign, unpersisted, replayed or rewritten storage and privacy/time
counterexamples. The Qt/POSIX implementation is uncompiled. Native filesystem,
product, headset, device and rendering behavior remain unqualified.
