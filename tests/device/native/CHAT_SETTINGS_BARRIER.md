# Original Chat settings writer barrier v1

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
During acquisition its short gate prevents new Chat mutations from changing
the cache before the actual writer is read. An atomic attempt count also
detects a newly blocked mutator that entered during that gate. The callback
cannot turn a still-pending write into a zero-pending source. Native birth,
completed mutation sequence, wall-clock capture and actual monotonic elapsed
time stay original. Clock regression and acquisitions above 1.5 seconds are
unavailable. This bounds admission, not filesystem I/O cancellation.

The manager reads original key presence and QVariant values under its existing
cache lock. It then posts a blocking callback to its actual original WriteWorker
QObject/thread, held by the manager's original weak pointer; original shutdown
is covered by the same in-flight gate. Earlier completed Chat mutations have
already enqueued their original worker events. The callback executes the real
worker's sync, checks its real QSettings status and separately reads that
worker's actual live key presence/variants. No other QSettings reader is created.
Raw cache/worker values remain internal to the future native profile owner;
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
of actual serialized bytes, bounded to a 1-MiB INI. Duplicate/ambiguous aliases,
unsupported continuations and malformed syntax refuse acquisition. Other rows
and raw file content never enter this source result. These physical row hashes
remain distinct from both manager and worker QVariant types: Qt5 serializes an
empty QVariantList and a null QVariant into identical `@Invalid()` bytes even
while the current live types differ. A shared-cache QSettings read cannot prove
that physical boundary.

Two real Qt5 compiler/run checks pass. One compiles the complete original
SettingManager.cpp translation unit and real generated QObject metadata, then
executes its original worker thread, Manager set/remove/clear paths, native
snapshot and an actual still-active signal emission. The second executes the
original worker setValue/sync/snapshot bodies with the original barrier and
physical file reader, exercising pre-enqueue delay, a mutation blocked during
snapshot, actual null/list/string differences, file modes, duplicate rows and
symlink refusal. Its manager cache is an explicit seam. These checks qualify
this host component only; full application/Android linking and devices remain
unqualified.

The next profile owner must capture exact original live presence/type/value and
these distinct physical row hashes before mutation, forbid unowned history,
use normal Erase and independently reconstructed Script history, restore only
its saved original keys, acquire fresh matching cache/worker/file originals and
verify final callback/file/resource quiet before retiring any ownership journal.
A successful sync or empty model alone cannot supply those facts.
