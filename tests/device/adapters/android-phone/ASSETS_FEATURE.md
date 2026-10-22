# Phone Assets source handoff

The complete common v17 Assets adapter is being composed in this worktree.
There is no public `feature.assets.act|observe|cleanup` advertisement yet.
The inherited controlled debug `asset.load` foundation remains separate from
normal Asset Browser mutations. Physical acceptance is untested.

## Original backend reads

`phone-assets-observe` obtains a new actual AssetClient GetAllMappingsRequest.
The source retains original mapping paths, SHA-256 hashes, all six native bake
statuses and original errors, including hidden bake mappings. Native domain and
session identities and actual Asset Server write permission accompany the
reply. No expected mappings or current action enters the source. Full server
inventory allows the eventual owner to preserve outside mappings independently.

`phone-assets-download` obtains bytes from an actual hash-addressed AssetRequest,
checks its real finished/error state, and records its original hash, byte count,
canonical Base64 and actual cache-origin flag. The native reducer recomputes the
SHA-256 of the bytes. A matching requested hash alone cannot supply content.

AssetClient creates these QObjects on its network thread. The actual request
callback copies original data on that thread and queues an immutable value to
the GUI source owner. GUI code never dereferences a request-owned field. The
packet becomes observable only after the actual QObject destruction signal has
reached the GUI owner. Its read result is then consumed; active native requests
and retained result buffers are both actually zero. A different command cannot
replace a live/unconsumed read, and an already consumed ID cannot restart it.
A fixed 4096-ID process history fails closed on overflow; it never rotates a
new namespace or retains completed result buffers.

A bounded source failure cancels only its own readonly request lease. A GUI-owned
cancellation QObject queues deleteLater to the actual request owner; no cross
thread raw pointer is dereferenced. Cancellation does not supply a successful
source. Later reads can resume only after actual destruction. Mapping bytes are
never retimed while polling. Native reply duration/freshness remains below
1.5 seconds and host calls retain their real five-second monotonic deadline.

The existing private command path and read-only admission now carry these two
closed queries. Missing/partial sources, ACKs, still-live requests, retained
buffers, replayed cursors, stale epochs and mismatched bytes stay red.

## Actual private inputs

`phone-assets-files` exclusively stages the seven original glTF/OBJ/FBX bundle
inputs under one `feature-assets-<run>` private directory. Relative filenames
and companion subdirectories remain unchanged. The fixture uses the existing
common `asset_fixture` inventory and pinned bytes, never source-derived expected
state. Native directory/file operations reuse Create's exact private inode,
no-follow, regular-file, hardlink and bounded read primitives through a narrow
friend class. There is no generic local path or upload/mapping input API.

Each current file read computes SHA-256 from its actual bytes and preserves
original inode, size and timestamp identity. Only these fixed INPUT files omit
repeated Base64 bodies; original backend downloads retain their bytes. This
keeps all existing private journal/raw/packed limits unchanged. The Assets owner
reuses Create's journal writes, input receipts, namespace reservation, historical
validation and actual-absence retirement. New preparation has one durable stage
intent. Lost stage replies are reconciled from current native files, never by
replaying stage. Main-file retirement removes only the original staged glTF
primary, keeps companions, and reconciles a lost reply without another unlink.

Cleanup validates the complete closed directory inventory before removing any
known inode. Unknown children, symlinks, FIFOs, hardlinks, changed bytes/modes,
replaced directories and same-name copies stay red and keep their journals.
Native release is fenced and idempotent; host journal retirement requires a new
actual native absence and exact retained final transcript. An unknown preexisting
root cannot be adopted by a different native lifetime, even for the same run.

## Host verification and remaining composition

```sh
python3 android/phone/tests/device/test_assets_files.py
python3 android/phone/tests/device/test_assets_source.py
python3 android/phone/tests/device/test_assets_native_reads.py
node --check tests/device/probe/overte_e2e_probe.js
```

The native check compiles the actual unchanged TestScriptingInterface Assets
methods and actual job/reducer headers against Qt 6.11.2 in a fresh own folder
below `build/assets-native-contract`. Only explicit AssetClient and NodeList
endpoints are synthetic. It executes real Qt network/GUI thread delivery,
QObject destruction, cancellation, error recovery and content hashing. This is
not an Android build or a live Asset Server/renderer test. The source check is
registered under Common and the compiler check under Prepared in the existing
Phone runtime regression inventory. Central Emote source-pin regeneration stays
with the integration owner after all probe merges.

Next are owned domain write-permission control,
original-token normal browser/file/dialog inputs, independent role/actor
observations, actual model/render joins and the complete 29-action journey with
its mandatory asset-load foundation, ownership, interruption and retirement.
