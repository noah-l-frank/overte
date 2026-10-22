# Original Chat settings writer barrier v2

This internal native component is not a complete Chat profile owner or a public
feature operation. It does not export private setting values through a script
hook. Full Chat stays partial and devices have not run.

The actual Setting::Manager updates its cache under a lock but emits normal
valueChanged/keyRemoved signals after releasing that lock. A new queued sync
alone could overtake a started mutation that has not yet emitted its write.
The dedicated E2E code therefore tracks actual in-flight fixed Chat-key cache
mutation paths through their original signal emission, including Handle saves,
loadSetting's possible insertion, removal, clear-all and writer termination.
Ordinary builds and E2E launches without `--testScript` retain their existing
behavior. Native counters record actual method lifetimes, not requested writes.

`ChatSettingsBarrier` rejects a read while any original mutation is active.
Its mutex protects only short counter snapshots before and after acquisition;
it never spans cache locking, worker waiting or physical I/O. Any mutation
started or completed during acquisition invalidates the result through actual
pending/attempt counters and completed mutation sequence. Native birth,
wall-clock capture and actual monotonic elapsed time stay original. Clock
regression and acquisitions above 1.5 seconds are unavailable. This bounds
admission, not filesystem I/O cancellation.

The manager tries its existing cache read lock without waiting, reading original
key presence and QVariant values only if available. It then posts exactly one
queued job to its actual original WriteWorker QObject/thread. A semaphore wait
is bounded to 1.5 seconds; no mutex is held while waiting. A timed-out job remains
owned and prevents another enqueue until actual completion. A subsequent query
always discards a finished old result and requests new original work. Queued
callbacks own their result storage, hold only the original weak worker pointer
and never capture the Manager or caller stack. A real worker-to-UI synchronous
callback therefore cannot indefinitely block this source. Earlier completed
Chat mutations have already enqueued their original worker events. The job
executes the real worker's sync, checks its real QSettings status and separately
reads that worker's actual live key presence/variants. No other QSettings reader
is created. Raw values remain internal to the future native profile owner;
they must be reduced to bounded private hashes before any script publication.

After the original sync, `chatSettingsFile` opens the actual worker-selected
file and reads physical bytes through its own OS descriptor. It admits a
canonical same-user hierarchy inside an actual owned 0700 ancestor, with no
publicly writable descendants, and a regular single-link same-user readable/
writable file without public write, execute or special permission bits. Qt5
normally creates a 0644 INI inside private app data; this read does not change
product permissions. The actual file identity, full nanosecond timestamps,
size, mode and original path are checked across the bounded read; symlinks,
replacement and nonprivate roots fail. The descriptor closes before return.

Only the two literal root Chat key rows are retained as presence and SHA-256
of actual serialized bytes, bounded to a 1-MiB INI. Version 2 also reports
whether the actual history row is absent or has a literal empty/`@Invalid()`
encoding; no cached live value supplies this physical admission. Duplicate/ambiguous aliases,
unsupported continuations and malformed syntax refuse acquisition. Other rows
and raw file content never enter this source result. These physical row hashes
remain distinct from both manager and worker QVariant types: Qt5 serializes an
empty QVariantList and a null QVariant into identical `@Invalid()` bytes even
while the current live types differ. A shared-cache QSettings read cannot prove
that physical boundary.

Three real Qt5 compiler/run checks pass. One compiles the complete original
SettingManager.cpp translation unit and real generated QObject metadata, then
executes its original worker thread, Manager set/remove/clear paths, native
snapshot, an actual still-active signal emission, contended cache lock, worker-
thread mutation and real worker-to-UI wait cycle with owned late-job recovery.
The second executes the
original worker setValue/sync/snapshot bodies with the original barrier and
physical file reader, exercising pre-enqueue delay, mutations started and completed during
snapshot, actual null/list/string differences, file modes, duplicate rows and
symlink refusal. Its manager cache is an explicit seam. These checks qualify
this host component only; full application/Android linking and devices remain
unqualified. The third compiles the entire original Manager and new
[private profile owner](CHAT_PROFILE_OWNER.md), exercising saved native types,
actual file boundaries, conditional restore and late original worker ownership.

The profile owner must capture exact original live presence/type/value and
these distinct physical row hashes before mutation, forbid unowned history,
use normal Erase and independently reconstructed Script history, restore only
its saved original keys, acquire fresh matching cache/worker/file originals and
verify final callback/file/resource quiet before retiring any ownership journal.
A successful sync or empty model alone cannot supply those facts.

The independent physical reader now selects INI or the registered JSON format
from the actual original worker, retaining original immediate-parent and file
identity through parsing. JSON requires exact original Qt-indented object bytes,
rejects ambiguous fixed-key aliases and hashes raw literal tokens. Empty history
admits only fixed empty encodings, including the empty QStringList generated by
the original writeJSONFile implementation; file-supplied @Variant streams are
never deserialized by this observer. Six real Qt5 checks now compile the entire
original SettingHelpers.cpp and SharedLogging.cpp alongside Manager/MOC. Both
formats and original JSON read/write semantics are exercised. The original
worker sync may reload an externally changed file while the Manager cache stays
unchanged; that actual disagreement refuses restoration.

Before conditional restoration the Manager obtains another bounded original
snapshot without holding its locks over worker waits. Barrier owner/sequence and
serialized cache/worker/physical values must still match. QDataStream preserves
original native types: QVariantMap equality alone can hide an actual worker
Int-to-Double change behind the same JSON number tokens. The real original
worker counterexample now exercises that refusal without changing Manager cache
or mutation sequence. The existing short locked admission still checks the
original cache exactly before its one normal signal/write path.
