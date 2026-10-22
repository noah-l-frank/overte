# Original host binding transfer v1

`PicoOpenXrAdapterSession.original_binding_transfer()` captures the existing
private host cursor through `OriginalBindingTransfer`. This additive primitive
executes no SDK/ADB/target input, process discovery/launch/stop, neutral command
or journal cleanup. Existing default stage/cleanup/discard behavior is unchanged.
It is a host compare-and-replace operation, not process-retirement evidence.

Before using it, the enclosing feature must separately own all consumed input
transactions and prove the actual old PID/start has ended, the original installed
candidate remains, and a separately observed new process/native birth is valid.
A stop ACK, empty process list, caller-provided expected result or this host
cursor itself cannot supply that proof. The intended Chat parent additionally
requires its actual cleanup phase, retained source histories and independent
post-restart current profile checks. This primitive grants no feature capability.

Construction holds original Linux open-file-description pairs for the private
parent directory, unchanged session lock and original cursor file. It requires
actual private modes/UID, single-link regular state/lock files, zero-byte lock,
closed original state schema and exact original bytes/full stamps. Duplicate
JSON keys, root/lock/file replacement, hardlinks and lost/recycled handles fail
closed. A same-inode replacement descriptor is foreign and is not closed.
The nonblocking canonical flock serializes with the existing session methods.
A missing or busy original source is not adopted or recreated.

`capture()` returns a detached original state/hash/full-stamp receipt. It does
not bind a process or read the target. The caller persists this private original
before its process transition. Private nonce/cursor data must not be published
as ordinary logs or external artifacts.

`replace(successor, intent=callback, before_publish=callback)` requires an exact
closed successor with a different process identity and 64-hex nonce and initial
sequence 1. The original cursor must still match the captured original exactly.
It creates one private prepared file, fsyncs it and holds its actual original OFD.
`intent` receives detached original/prepared source receipts before publication;
caller mutation cannot change either actual file or internal receipt. The caller
must durably retain that exact admission before returning from the callback.
An exception or expired pre-publication guard leaves the old cursor and prepared
original retained. Unknown intents are never called or published again.

Both callbacks execute inside the session lock. They must be pure host
CAS/fsync/elapsed-age checks: no SDK, ADB, session reentry, HTTP/phase-source read
or target guard. The caller qualifies independent current sources and phase
outside this lock, then uses its saved native/host anchor in the callback.
`before_publish` runs after the durable intent, after final file guards directly
before the single original `os.replace`, and after final receipt copies/guards.
It cannot reset the original source freshness deadline. The successor publication
and directory are fsynced; no foreign old file is unlinked as cleanup.

A lost rename receipt permits `reconcile()` to read only the exact original held
prepared OFD now at the canonical cursor path. Exact state/hash/device/inode/
size/mtime must match the original prepared receipt; rename ctime may advance.
A copied byte-identical file, unchanged original path after an unapplied rename,
foreign cursor advancement or lost original descriptor remains unresolved. No
second replace, callback intent, nonce rotation or target input is performed.
Repeated `replace` may reconcile only with the exact same saved callback objects
and successor; callback ownership is never silently replaced. `close_host()`
closes only proven original handles and leaves all state/temp/journal paths.

This is one warm ownership scope. A fresh transfer cannot adopt a prior unknown
transfer or reconstruct its lost original OFDs. The enclosing feature retains
its original issued journal for that boundary. No cold uncertainty is converted
into a new binding or a complete cleanup claim.

The host checks exercise actual private files, locks, atomic rename and Linux
OFD identity. They cover original/prepared receipt ordering and immutable copies,
foreign file/advanced cursor, closed successor/duplicate/hardlink rejection,
lost intent, applied/unapplied lost publication, byte copies, callback ownership,
slow admission/final guards and recycled same-inode FDs. The original session
regressions run alongside them. No Android process or physical device is run.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/device python3 -m unittest self_tests.test_pico_binding_transfer self_tests.test_pico_openxr_adapter_session -v
```
