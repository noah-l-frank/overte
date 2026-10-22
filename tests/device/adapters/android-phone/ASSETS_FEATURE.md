# Phone Assets source handoff

The complete common v17 Assets adapter is being composed in this worktree.
There is no public `feature.assets.act|observe|cleanup` advertisement yet.
The inherited controlled debug `asset.load` foundation remains separate from
normal Asset Browser mutations. Physical acceptance is untested.

## Original backend reads

`phone-assets-observe` obtains a new actual AssetClient GetAllMappingsRequest.
The source retains original mapping paths, SHA-256 hashes, all six native bake
statuses and original errors, including hidden bake mappings. Native domain, session and actual Asset Server node UUID identities and actual Asset Server write permission accompany the
reply. All three identities are rechecked on completion and final delivery;
a server replacement inside the same domain invalidates an old reply. No expected mappings or current action enters the source. Full server
inventory allows the eventual owner to preserve outside mappings independently.

`phone-assets-download` obtains bytes from an actual hash-addressed AssetRequest,
checks its real finished/error state, and records its original hash, byte count,
canonical Base64 and actual cache-origin flag. The native reducer recomputes the
SHA-256 of the bytes. Domain/session/server identities also accompany downloads. A matching requested hash alone cannot supply content.

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

`phone-assets-resolve` performs a separate real GetMappingRequest for only this
run's fixed public fixture paths. Its owner-thread callback reads the actual
request path, resulting hash, redirect flag and redirect path. Domain/session/
server binding, cancellation and actual QObject retirement use the same bounded
read job. No expected path/hash/bake outcome is accepted as source input. The
requested path is query identity; only the actual reply supplies its resolution.

## Immutable original GeometryReader input

OBJ's serializer leaves `HFM.originalURL` empty, and server-baked FBX loads its
actual redirected path. Neither is rewritten for the test. After the normal
baker finishes, GeometryReader seals one immutable E2E-only record of its actual
input URL digest, original body SHA-256/length, generation and creation epoch
before publishing the processed HFM. It retains no body buffer. The render-thread
model copy includes that original. Original mesh draw traces use its actual
loaded URL digest only when the serializer has no original URL. Existing
serializer/trace semantics (including compression normalization) remain unchanged.

The public reducer still needs to join original server mappings/resolution,
actual reader content, entity/model/geometry identity, original draw commands
and a fresh owned PNG. Static immutable metadata is not retimed or rejected for
being older than 1.5 seconds. A fresh capture alone cannot qualify an old reader
from a different URL/hash/generation. Missing reader originals remain red for
Assets, even though existing Create readers can still read their legacy schema.

## Passive normal upload originals

The normal `uploadBundle` path now retains bounded E2E-only receipts of the
actual file list, destination, bundle UUID and original Domain/session/Asset
Server identity. Actual AssetUpload and SetMappingRequest finished signals copy
body digest/length, filename digest, returned hash, path and error on their
network owner thread through a DirectConnection. A mutex protects complete
snapshots. Separate actual QObject-destroyed signals supply request retirement;
missing, null, replaced or destroyed-without-finished requests fail closed.

These receipts establish no mapping effect by themselves. Ownership still needs
fresh independent GetAll/GetMapping effects and original private file identity.
Exact instance/bundle IDs can retire only terminal, actually destroyed receipts.
A bounded retired-run fence prevents reopening; late events invalidate it.

The existing product upload callbacks connect `deleteLater` before a queued GUI
callback dereferences the network-owned request. This potential lifetime/thread
issue is deliberately unchanged. The host contract compiles actual passive
hooks and runs real Qt threads, but substitutes network endpoints and does not
execute or qualify those normal callbacks. Neither a live upload nor a product
PASS follows from this contract test.

## Original backend workers and stored blobs

With the existing Assets fixture option, only its actual type-3 AssetServer
assignment receives an exclusive private receipt directory. Dedicated Unix E2E
builds retain passive bounded worker instances, actual queue/run start/exit,
QProcess started PID and actual exit arguments, normal completion/failure/abort,
and actual QObject destruction. Worker callbacks copy their measurement closure
before running; receipts retain no worker pointer. The actual assignment thread
publishes current mappings, pending count and SHA-256/length of actual stored
blobs every 100 ms. Input/read limits fail closed; no output is synthesized.

The existing Domain control serves `/v1/assets-originals` through two separate
readonly role tokens. Those tokens cannot change Settings; the permission token
cannot read originals. Secrets remain in the private ready file and are omitted
from stdout. The reader pins the actual fixture-owned type-3 PID/start, native
server/Domain IDs, source instance, sequence, immutable worker history and exact
0700/0600 directory/file inode. Locks, no-follow reads and same-inode comparisons
reject partial/replaced/symlink/hardlink/FIFO sources. Native publication cannot
adopt or truncate another lifetime's file. An old worker, omitted live job, failed
oven, absent exit or stale heartbeat cannot establish a new successful bake.

Host checks compile actual BakeAssetTask with real Qt threads/QProcess and an
explicit synthetic oven executable, plus the actual server snapshot method with
explicit NodeList endpoints. They exercise actual files and exclusive receipt
creation. This is no real oven output, complete AssetServer/Android build or
product lifetime qualification. The normal task/request lifetimes are unchanged.
The public reducer must still join current meta/download/redirect originals and
new worker identities to its action barrier, then to current renderer originals.

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
intent. The complete recipe uses at most six explicitly numbered generations,
each recorded before input with its own private owner header, original ticket,
namespace and independent retirement. A retired generation can never restage.
Cancellation releases actual files before another generation is reserved; an
uncertain generation remains in the complete run inventory until reconciled.
The legacy single-stage source remains closed and unchanged. Lost stage replies are reconciled from current native files, never by
replaying stage. Main-file retirement removes only the original staged glTF
primary, keeps companions, and reconciles a lost reply without another unlink.

Cleanup validates the complete closed directory inventory before removing any
known inode. Unknown children, symlinks, FIFOs, hardlinks, changed bytes/modes,
replaced directories and same-name copies stay red and keep their journals.
Native release is fenced and idempotent; host journal retirement requires a new
actual native absence and exact retained final transcript. An unknown preexisting
root cannot be adopted by a different native lifetime, even for the same run.

## Process-owned write permission fixture

`fixture/domain.py --feature-assets-permissions` is off by default. It exposes
only the separately token-bound `/v1/assets-permissions` control for its actual
owned ephemeral Domain Server process and Domain UUID. It reuses Create's exact
Settings readback, private original journal, pending-intent recovery and restore
fence. The Assets subtype changes only `id_can_write_to_asset_server` in the four
original standard permission rows. All rez, connection and unrelated fields
remain actual originals. Missing write fields, overrides, changed outside
Settings, process/domain changes and foreign run/token journals fail closed.

Both optional controls can exist in the same fixture, but their calls share the
existing transition lock and reject any other controller's active durable
Settings lease. They never capture each other's temporary state as an original.
The first owner must restore exact Settings and retire its actual journal before
the other can bind. An HTTP success acknowledgement does not establish an
Interface permission or a disabled Asset Browser control; the public composition
must independently read those actual effects.

## Original normal browser controls

Surface 9 reads the actual `TabletAssetServer`, `NativeModelTree`, standard Qt
Dialogs and bundle-mode `NativeFileBrowser`. Composite roots and popup controls
are tied to their actual QML component contexts and object identities. Row
references retain original path/status/selection data; replacements invalidate
their tokens. Standard dialog buttons are resolved by their actual native role.
No QML action handler, file-helper method or Asset service mutation supplies an
input shortcut. Normal pointer/key events enter the actual rendered Qt window.

`TokenAssetsUI` and `PhoneAssetsIO` reuse the existing token clock/wait/transport
engines. They persist original-reference intent before delivery, require actual
consumed native input sequence and read back widget transitions. Closed common
bundle inputs keep their relative companion paths and main choice. Ordinary
folder-field submission navigates without discarding selected companions.
Actual native filesystem ownership remains independent of these widget buffers.
The normal Create Tools asset button supplies the existing browser entry.

Assets shares the existing Avatar/People z-sorted input-recipient algorithm
through `NormalInputHitTest.h`; Avatar retains its original source guard. Foreign
mouse/touch/pointer-handler overlays still block input. A ComboBox keyboard
choice is qualified by its own original field or live popup focus, even when
its popup covers the original center. Input receipts supply no mapping/model
verdict. The parent integration must retain Snapshot Surface 10 and merge the
native dispatch range to 0 through 10; this isolated base has only 0 through 9.

## Host verification and remaining composition

```sh
python3 android/phone/tests/device/test_assets_bake_originals.py
python3 tests/device/self_tests/test_assets_originals.py
python3 android/phone/tests/device/test_assets_upload_originals.py
python3 android/phone/tests/device/test_assets_uploads.py
python3 android/phone/tests/device/test_assets_geometry_input.py
python3 android/phone/tests/device/test_assets_native_ui.py
python3 android/phone/tests/device/test_assets_controls.py
python3 tests/device/self_tests/test_assets_permissions.py
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

The UI compiler check additionally loads unchanged product QML and compiles the
unchanged actual `FileDialogHelper.cpp` and `NativeFieldInput.cpp`. It selects
actual main/mesh/texture files, preserves their bundle manifest, delivers normal
Import/Rename/Delete dialog events, rejects disabled Delete and foreign overlays,
and observes the actual unavailable-file error after a real main-file unlink.
Every native UI snapshot is also checked by the Python metadata validator.
Its Asset Server/entity service endpoints are explicit synthetic seams.
An explicit Assets-only `probe-disabled` operation delivers real pointer events
to the actual disabled Delete button. Normal `activate` remains rejected. The
probe neither enables the button nor marks it input-ready or calls its handler;
the existing stacking/overlay checks still guard that exact original point.
Enabled Delete, a different control and a foreign overlay reject this operation.
Only subsequent unchanged original mappings/content prove denial.

The geometry contract compiles the actual reader-publication, render-copy and
mesh-trace source blocks with the real immutable Qt metadata class and explicit
synthetic model/geometry/baker endpoints. It checks empty OBJ serializer URLs,
new reader generations, byte identities, non-retiming and concurrent complete
renderer snapshots. It is not a full HFM/renderer build. A direct actual HFM
header syntax attempt is currently blocked by missing host `glm/glm.hpp`; no
installation/fetch was attempted and no complete Android/client PASS is claimed.

Next are independent role/actor observations, actual model/render joins and the complete 29-action journey with
its mandatory asset-load foundation, ownership, interruption and retirement.
