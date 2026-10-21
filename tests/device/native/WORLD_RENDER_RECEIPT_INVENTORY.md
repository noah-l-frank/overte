# Role-scoped original Pico render receipt retirement

`world-render-ownership` v2 adds an explicit primary/actor role to the existing
private acquisition journal. Its default unqualified v1 reader/writer remains
explicit and cannot adopt a v2 record; neither role can adopt the other. There
is no automatic migration of an interrupted old capture. Whole role ownership
requires the concrete native batch receipt transport, without a shell-unlink or
single-ACK fallback. No complete Graphics capability is enabled by this packet.

The selected sources and hashes come from the frozen Phone reference listed in
[Pico's selection manifest](../adapters/pico4/GRAPHICS_CAPTURE_SELECTION.json).
No Phone worktree/file was changed. The actual Pico GPU stereo v4/frame/used-camera
implementation remains intact. The new native batch entrypoint is Pico-only
inside the existing dedicated E2E build/runtime gates. Shared legacy mono/storage
and singular receipt consumers keep their existing opt-in APIs and versions.

`pico-graphics-capture-binding` v1 uses the original verified Pico candidate,
process/start, OpenXR binding, package and private source transports. Its primary
and actor owner files occupy separate fixed paths in the private Graphics
namespace. A role capture requires the caller's explicit held source-lock
instance and actual stereo camera acquisition v4. The internal namespace binding
contains no complete operation triple, fixture activation, normal UI input,
session launch or repair.

All Pico world acquisitions and releases now serialize through the same stable
Graphics source-lock domain, including old component captures. Nested calls use
the same explicit instance. A different role or old component's unresolved owner
blocks a new acquisition before it can overwrite native evidence. Neither a
foreign owner nor a missing lock is silently discarded. Candidate loss preserves
the original journal and performs no file cleanup. Empty stable lock files are
coordination resources and are not unlinked while another waiter could exist.

`world-render-receipt-inventory` v1 requires the actual native GPU issuer to
account for the complete selector set for one retired, drained capture. It
refuses an omitted issued receipt, a foreign capture's nonce, live callbacks or
pixels, and bounded-history exhaustion. Issued status comes from the native
history, not the host's requested IDs. The new nonce-only result is saved through
the existing atomic owner-only path. Unknown/missing original sources remain
unavailable and cannot become successful cleanup.

The frozen reference assumed a listed but undelivered storage command could no
longer issue a file after retirement. The actual storage path still admitted
later release/inspect nonces. This implementation additionally retires each known
unissued selector against later storage issuance before publishing its absence.
The combined issued/declined nonce history stays bounded at the original 65,536
entries and is never evicted. A fresh explicit cleanup query still uses a new
journaled nonce; an old uncertain command cannot allocate a receipt afterward.
This changes only the dedicated evidence API's resource ownership, without
changing product rendering, scheduling or device behavior. Native inventory
command IDs also retain a bounded no-recapture history of 4,096 entries.

Before deleting any file, the native method validates the entire original set.
A present unissued file is refused. Original issued files require the native
content digest, same opened/path inode/device, owner UID, exactly mode 0600,
one hard link, bounded regular-file bytes, non-symlink/nonblocking reads and
unchanged final file identity. Each deletion is rechecked on the original GUI
thread, whose existing probe serializes legitimate receipt writes. Unsupported
native host platforms remain unavailable. This is not authorization for external
writers to replace app-private files during a bound cleanup operation.

After removal, the concrete Python reader independently acquires a second
original complete issuer/file inventory, with a new command/cursor and actual
absence for every receipt. It preserves per-capture issuer histories: a formerly
unissued intent cannot later become an issued one unnoticed. Guard loss, stale
or foreign data, changed/missing/duplicate rows, context/cursor replacement,
retained files and processing latency all retain the journal. Existing five-second
processing and 1,500 ms freshness limits remain unchanged. Only after both native
memory and complete file retirement does the capture owner discard its record.
The full Graphics owner must also enforce source-specific actor/frame/image
continuity, process restarts and its required quiet window.

Host cases use real private temporary files plus synthetic original issuer,
Qt/OpenXR/ADB boundaries and the actual Python Pico factory. They verify that a
successful ignored deletion ACK leaves files/journals present and that no shell
deletion fallback is used for role v2. No native code was compiled, no real GPU or
POSIX client helper was exercised, and no device was accessed or qualified.
