# Exact original Create Browse setting ownership

Feature 4/14 remains partial. The durable picker owner captures the actual raw
`LastBrowseLocation` setting before normal picker input and retains that original
through Import/Save/Delete and cleanup. This fixed-key native test seam accepts
no requested replacement value and cannot access a second key.

Under the existing dedicated E2E/Pico, `--testScript`, original process/lifecycle,
GUI thread, private output and candidate guards, it reads the actual original
`Setting::Manager` map under its real read lock. A `Setting::Handle` read would
insert or remove some absent defaults, so the dedicated friend performs a
passive raw capture instead. Presence, QVariant type ID/name and exact Qt 5.15
QDataStream bytes/hash are preserved, including an absent key, empty QString and
non-string values. Strings and paths remain in private 0600 host/native evidence;
no public selector or requested value enters the source. Originals exceeding
8192 serialized bytes fail closed. There are four append-only native leases,
four original read claims and four response claims per lease and 512 immutable native nonce results.
No lease is evicted or replaced, including after release.

A claim requires an actual returned original native dialog from after lease
birth, identical root/listener/context/window/role, its original result digest,
an authenticated native Create file manifest/token and the actual setting's
QString equal to that original owned directory. Both Import and Save must
match their distinct owned filename hash. The owner cannot adopt a foreign
path, desired callback result or file-transport acknowledgement as the effect.

Restoration executes once under the original Manager write lock. It compares
current presence/type/serialized bytes to the last independently acquired owned
value, refuses live cached Handles and foreign changes, then restores only the
natively captured original QVariant or removes the key if originally absent.
It emits the original Manager valueChanged/keyRemoved signal so the existing
writer persists the change. Failed/uncertain restoration remains owned. Neither
a successful reply nor an input acknowledgement establishes final restoration:
the host re-observes the actual raw original, holds it through the joint final
three-second native/UI/entity quiet interval, then requires actual original
claimed dialog/listener/root/context retirement before native release.

The original empty-directory Window call also records raw before/after values
around its actual temporary `Setting::Handle<QString>` read. Source version 3
joins that immutable read to the original native dialog. `claim-read` authenticates
that exact pointer/ticket and requires the actual before value to equal the last
owned original, then records the real after value. This handles a read that
coerces or removes an existing non-string QVariant before any Select. A late
native read observation is polled without consuming a mutation attempt.

The native owner also observes the actual original writer on its own live
thread after earlier queued Manager signals. A test-only weak pointer/birth
identifies that existing worker; no replacement worker is created. Its existing
lazy `init()` loads its real QSettings for a fixed-key read. After a successful
CAS, the existing Manager forceSave signal drains through the original writer;
manager memory and actual writer raw value must both match the original through
final quiet and release. Missing/stopped/replaced writers or unavailable storage
retain ownership. This is original QSettings worker state, not a requested value
or an acknowledgement.

Source version 3 additionally captures the physical original before normal
picker input. The path and actual format come from that same original worker;
format identity is compared against `QSettings::IniFormat` or the actual
registered `JSON_FORMAT`, never inferred from a suffix. A separate read-only
file descriptor reads physical bytes without constructing a QSettings object.
It preserves file existence, device/inode, mode, byte count, nanosecond original
mtime/ctime, whole-file SHA-256, path digest and the fixed raw row's bytes/hash.
Descriptor/path identities, the immediate parent and the nearest owned private
ancestor must remain stable during acquisition. Missing files are checked again
at the end. Symlinks, hardlinks, foreign ownership, non-0600 files, unsafe parent
permissions, oversized files/rows and unsupported encodings fail closed.

The INI reader refuses duplicate or escaped aliases of LastBrowseLocation. The
JSON reader requires exact original Qt indented serialization, which refuses
duplicate keys and alternate key escapes, then acquires the literal top-level
value token from the original bytes, including nested values and escaped quotes.
Final quiet, restoration, native release and host journal retirement require the
same original fixed physical row and format/path, independently of the Manager
and worker cache. Original atomic QSettings rewrites may replace the inode and
unrelated keys may change; every acquisition preserves its own actual identity.
No replacement config value or physical-file write is accepted by this seam.
Version 2 remains passively readable, but lacks original physical evidence and
cannot qualify a new input operation or exact cleanup.

The original writer observation posts one shared, weak-receiver job and waits
at most 250 ms. It captures no Manager, stack reference or owner pointer in the
queued job. A timed-out job remains tracked; further reads refuse while pending,
and a late original result is discarded before a fresh barrier is queued. A
stopped/dead worker cannot satisfy the barrier. Native Qt5 counterexamples block
the actual original worker, complete an older read ahead of a newer actual
write, and destroy an owned original receiver before queued work executes.
Another counterexample changes the physical fixed row while both actual caches
still equal the original and proves that native and host retirement refuse.

Each original mutation command/nonce is persisted before send. Interrupted
reserve/claim/restore/release is reconciled through fresh observations; a lost
command is never resent, even if it might not have reached native code. Host
settings history survives adapter reconstruction. The settings journal remains
until authenticated file release completes, and orphaned settings records block
base cleanup. A missing main owner does not waive original-source quiet proof.

`create-browse-setting` checks closed probe forwarding, original raw/hash/source
continuity, candidate replacement, foreign CAS refusal, and lost operations
before/after actual effect with one-send recovery. `create-browse-setting-native`
compiles the original TSI getter, original getPreviousBrowseLocation and original
Setting::Interface methods, actual Setting::Handle and real product SettingManager.cpp with actual
moc, worker, locks and signals. It compiles the actual registered JSON format in SettingHelpers.cpp as well.
It validates missing gates/dependencies, stopped
foreign threads, immutable nonce/budget behavior, exact absent and QByteArray
restoration in independently read owned INI and JSON physical files, unrelated-key
preservation, authenticated Create manifests, foreign-CAS and cached-Handle
refusal. Its actual native packets pass the real Python parser. The application
dependency-registry lifetime and dialog metadata are supplied boundaries in this
QtCore fixture; the separate original Qt5 Window/Tablet dialog pipeline verifies
the real result hashes. No workstation user settings are read or written; all
QSettings persistence belongs to the fixture's private temporary directory.


## Proven retained Cancel boundary

Qt5 original-source evidence exposes a real failure when an existing QByteArray
contains `raw\0original` and ordinary Browse reads it through QString, then the
user cancels. The original Manager can restore all 12 original bytes/type 12 by
CAS, but the actual original writer retains QString/type 10 with 3 bytes; the
independently read owned persisted INI file agrees with that writer. The existing
WriteWorker comparison uses QVariant inequality, whose conversion equality can
skip the typed original write. The native release refuses and the durable owner
keeps the original lease, bytes and read identity. The test verifies this retained
failure rather than changing product behavior, forcing a replacement write or
reporting restored memory as complete cleanup. Import/Save with a different
owned path successfully restores and independently persists the original absent
or QByteArray value. The actual original JSON format now runs in this QtCore fixture and reproduces
the same retained Cancel failure. The full application and physical Pico
behavior have not run in this host fixture.

Use existing `OVERTE_TEST_GLM_INCLUDE` when real GLM headers are not installed
systemwide; the native check compiles the actual SettingHandle header without
substituting GLM or downloading dependencies.


## Follow-up host validation

The bounded/physical follow-up passed 34 targeted tests in 81.273 seconds:
`python3 -m unittest test_create_browse_setting test_create_browse_setting_native test_create_picker_owner`
with the existing Qt5 host root, actual GLM include and an owned 0700 TMPDIR.
The native check compiles original SettingManager, SettingHelpers, SharedLogging,
original Handle/Interface/Window-read bodies and real moc; it runs independent
owned INI and registered JSON processes. The two observed Cancel failures remain
expected retained failures. No original writer was repaired.

The documentation suite, contract-version validator, unchanged generated common
v16 inventory comparison, twelve Pico suite CLI tests, six coverage tests and
whitespace check also passed. The 250 ms barrier is a bounded observation wait,
not a guarantee that a filesystem itself completes within that time; an original
blocked worker or unsupported physical file leaves its owned lease unresolved.
There were no application, headset, device, domain-server or peer runs. Feature
4/14 remains partial, including the original retained Context/Cancel boundaries
and the remaining full Model/render/peer/PolyVox/rez-authority contract.


Reservation queues the original Manager forceSave signal before the bounded
writer barrier, so an actual dirty worker cache is flushed through the original
sync implementation before physical baseline admission. A deterministic Qt
counterexample gates the original worker, proves its shared QSettings cache has
the new original while direct physical bytes still have the old row, then
requires the reserve source to capture the newly persisted original. Ordinary
observations do not sync or replace a foreign physical row; the independent
cache-agrees/file-differs refusal remains in both original formats.

The dirty-start follow-up passed ten focused Python/Qt5 cases in 8.144 seconds,
including both original formats. A separate owned negative fixture omitted
only the reserve sync: both INI and JSON failed exactly at the new physical
baseline assertion, as expected. That proves this counterexample detects the
missing original barrier instead of passing through Qt autosync. This negative
fixture changed only private temporary header bytes and never the product
worktree. The documentation and whitespace checks passed again. The existing
SettingsTests friend gains one declaration inside both dedicated native test
gates to read the actual worker cache without constructing a second QSettings
object, whose own construction can itself flush shared dirty state.


## Physical ownership before restoration

The one native restore now requires a fresh bounded original writer observation
before taking the Manager write lock. Its raw value and the independent physical
row must both still represent the last actual claimed owned value. A foreign
physical edit after Select is preserved even when Manager and worker caches
still contain the owned directory; no restore signal or sync is issued. The
failed native attempt remains recorded and owned. The host polls only read-only
sources for up to three seconds before consuming its sole restore command, so
normal pending persistence can settle without replaying input or overwriting a
foreign file. A measured foreign Manager change is refused before sending.

Physical owned QString admission uses the original JSON writer's closed string
encoding, including doubled leading `@`. It never deserializes a foreign
`@Variant` or custom type. INI owned-value admission accepts unambiguous plain
ASCII directories/values (letters, digits, `/._:-`) and empty strings; ambiguous
escaped/quoted legacy INI owned values remain retained. Original raw values and
original physical rows are still captured without this restriction. Current
Android owned directories and the actual fixture paths use this admitted form.
A later external disk writer can race the original product sync; this seam
adds observed pre-write ownership fencing and does not claim cross-process
atomicity that the original Settings writer does not provide.

The pre-write fence follow-up passed thirteen focused Python/actual Qt5 tests in
19.500 seconds, including the actual foreign-row preservation case in both
original formats, pending-persistence polling, original retained Cancel failure,
closed JSON `@`/variant and ambiguous INI negatives. Source schema and catalog
selectors remain unchanged. This adds no config setter or product correction.
