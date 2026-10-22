# Phone Create input and original-source implementation

The full `feature.create.act|observe|cleanup` adapter is **not complete or
registered**. This packet extends the real normal input and original native
measurement seams needed by that adapter. It does not change the completed-area
count, common v17 contract, product functionality or physical acceptance.

| Layer | Implemented here | Still required for the complete area |
| --- | --- | --- |
| Ordinary input | Model URL/Domain creation, unit-size/position properties, actual texture field, real JSON Browse/Cancel/Select and Export/Save dialogs, existing Voxel mode/shape/remove/size controls | Run-owned input coordinator, original UI/settings restoration, original world click targeting and effect joins |
| Original entity source | Fresh private native entity/permission packets, bounded complete nearby ID inventory, direct tracked-UUID reads, saved PolyVox bytes SHA-256/size, actual native ready state and volume | Durable role histories, original object identity/ownership, resolved loaded model/texture/render facts, permission-controller composition |
| Controlled input | Exact owned model import document, separately serialized 8³ central-cube PolyVox input, exclusive app-private native staging, independent export-byte reads and durable file retirement | Public action/effect and actual export joins |
| Public adapter | Internal source and read-only original UI factories only | Public triple, separately credentialed actor, full common journey, whole resource/host journal retirement |
| Native verification | `NormalCreateControls.h` compiled against Qt 6.11.2 and run against unchanged `NativeCreate.qml` and `NativeFileBrowser.qml` | `PhoneCreateObservation.h` and Test/Android integration remain uncompiled; every device path remains untested |

## Actual ordinary paths

The existing native controls are extended; no second runner or direct Entity,
Clipboard, QML-handler or Script-message mutation is introduced. Token admission
and consumed-input sequences remain the existing source of input causality.
The owner must retain intent before every callback. An input result or selection
is never returned as an entity/file/geometry/permission verdict.

`TokenCreateUI.new_entity` uses the real resource field, host choice and actual
New button. Its return is only the original selected UI UUID; an outer owner
must compare an independently measured pre-input inventory, establish the actual
new object, and keep responsibility across uncertain delivery. The ordinary
texture recipe first filters the original type-specific property list for
`textures`, replaces that actual field with the `checker.png` assignment, then
clicks the real Apply property changes button. Loaded texture identity/bytes and
visible model pixels still need their separate independent joins.

The native JSON/file source admits only the original `NativeFileBrowser.qml`
context with exactly the existing `Select .json to Import` or `Select Where to
Save` caption, `*.json`, the matching save mode, and no bundle/directory/multiple
selection. The original filename, directory, error, closing and pending native
Document-provider request participate in the token source. A pending system
request or closing browser refuses input. Folder helpers, selected-file signals,
model contents and handlers are never called or assigned by instrumentation.
The input recipe uses the actual filename and Select/Save/Cancel buttons.
Only direct files beneath a fixed `feature-create-<run>` root can be passed by
these recipes. Ownership/staging/export facts must be established separately.

The Voxel recipe selects the existing Voxels mode, Cube brush, one click, Ray,
Remove checkbox and 0.5-metre diameter, then applies the actual controls.
It supplies no world click or saved-voxel verdict. These remain required for
public `voxel-edit`; UI preferences and an ACK cannot prove the edit.

## Original native entity source

`phone-create-observe` accepts only version 1, a new command nonce, the run ID
and at most 32 sorted unique tracked UUIDs. It accepts no expected state, URL,
brush value, texture result or mutation. Both the native endpoint and its
private probe transport are Phone/E2E-only. The internal adapter factory uses
the already bound candidate/process/session with read-only admission by default;
it does not start, repair or install anything.

The native source independently reads actual DomainHandler identity/connection,
`Entities.canRez`, `canRezTmp` and `canRezAvatarEntities`. The complete bounded
128-metre scan is centred at the actual avatar feet and capped at 1,024 entities.
Its original ID/type/host/name-digest inventory permits a later owner to detect
unnamed partial creations without disclosing unrelated names. This spatial scan
is not a whole-domain absence or foreign-world preservation claim.

Run-named model/voxel/Cube discoveries and every tracked UUID are queried for
actual type, host, parent, transform, visibility, lock, model URL and texture
property. Tracked IDs are queried even when moved or renamed; the explicit
present/absent partition must cover all of them. A matching name grants no
cleanup authority. Saved voxel SHA-256/byte size are read from the actual
PolyVox object, together with `isVoxelDataReady()` and its actual volume size.
Neither a property string nor these fields establishes rendered geometry.

The Python reader rejects missing/partial/over-limit inventory, malformed or
duplicate IDs/JSON keys, unavailable sources, mismatched request/run/PID,
instance/cursor/clock regression, old samples, late final delivery and changed
candidate guards. It requires a new request and advancing original sequence.
It preserves a copy of the actual packet; it cannot re-date an earlier packet
or replace absent measurements with defaults.

## PolyVox product-source finding and controlled input

The existing New PolyVox button in `NativeCreate.qml` passes only
`{type:"PolyVox"}` through the ordinary create path. `edit.js:createNewEntity`
does not add the older detailed dialog's central shape. Native defaults are an
empty 32³ volume (`PolyVoxEntityItem.cpp.in`). The older
`handleNewPolyVoxDialogResult` does create a central cube, but NativeCreate has
no visible ordinary control opening that dialog. Instrumentation does not
invoke its hidden handler or use `Entities.setVoxels*` as a substitute input.

The regular JSON import path supports the required controlled initial shape.
`overte_phone_create_fixture.documents` supplies version-3 entity JSON with the
fixed run-owned PolyVox name, 8³ volume and exactly the central 4³ occupied cells
from the existing detailed-dialog algorithm. It uses the existing QDataStream
big-endian volume header and qCompress/zlib saved-data format. A future public
`voxel-create` must compose ordinary JSON picker input, ordinary unit dimensions
and position two metres in front of the actual controlled avatar, followed by
independent acquisition of the created native saved-data baseline. Its edit
must acquire a different settled original saved-data digest and real geometry
pixels after the normal world click. Input fixture bytes must never be returned
as measured product state or exported bytes.

## Verification and continuation

`PrivateCreateFiles.h` implements a Phone/E2E-only app-private file lease.
The durable host owner persists its random token and issuing intent before
exclusive staging; an uncertain response is reconciled through a fresh native
read, without resending stage. The native source cannot write `selection.json`.
It independently opens the output after ordinary Save input, returns actual
bytes/digest/inode, and requires sealing that exact original before removal.
Inputs are immutable, private regular files. Foreign children, symlinks,
hardlinks, FIFOs, directories, replaced roots and changed sealed output fail
closed. Cleanup confirms actual root absence and transfers the exact transcript
to its parent before discarding its host journal. These file facts alone do not
prove product export semantics or the complete public Create journey.

Focused commands (no device, install, Jenkins or network access):

```sh
python3 android/phone/tests/device/test_create_source.py
python3 android/phone/tests/device/test_create_workflows.py
python3 android/phone/tests/device/test_create_files.py
python3 android/phone/tests/device/test_create_native_ui.py
python3 -m unittest discover -s tests/device/self_tests -p test_token_create_ui.py
python3 -m unittest discover -s tests/device/self_tests -p test_normal_create_adapter.py
python3 -m unittest discover -s android/phone/tests/device -p test_feature_adapters.py -k create
node --check tests/device/probe/overte_e2e_probe.js
```

The Qt check uses this worktree's own `build/create-native-contract/check-*`
folders and the prepared `pkg-config Qt6Core Qt6Gui Qt6Quick Qt6Qml` dependencies.
It substitutes native file services, keyboard/IME host and unused touch-style
service only; the loaded Create/FileBrowser QML and compiled passive source are
unchanged. It verifies real widget identities/metadata and rejects wrong
captions/modes and pending/closing native requests. It does not compile the
entity source or Android application, deliver actual product inputs, prove
file export or qualify hardware.

The separate file check compiles the actual `PrivateCreateFiles.h` with Qt
6.11.2 into this worktree's own temporary build folder and drives its persistent
native instance against real host files. Twelve cases cover exact input bytes,
independent output reads, negative filesystem nodes, foreign ownership,
interrupted stage, sealing, retirement and host-journal changes. The prepared
Test/Android source compiler check was green before this packet; the full
application and physical path remain untested. Probe changes require the root
integration's single final regeneration/check of source-bound Emote catalogs.

Next work must complete the public vertical through existing `OverteSession`
operations: versioned durable ownership and original role histories, exclusive
native Create file staging/export/retirement, actual controlled-domain rez
mutation/restoration, resolved Model/texture/GPU and owned original PNG joins,
normal world targeting, independent actor publication and verified whole-run
cleanup. Missing mandatory capability stays red. No configurable provider or
synthetic boundary may stand in for those real native/product implementations.
