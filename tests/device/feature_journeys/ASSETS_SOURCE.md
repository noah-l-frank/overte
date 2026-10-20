# Assets source contract introduced in v13

This specifies shared assertions and actual input/backend prerequisites. The
three platform branches still lack a complete Assets adapter/independent actor.
No native code, asset server, oven, device or installation is run in this phase.
Host simulations prove test logic and source assumptions only.

## Input bundles and normal control recipes

`asset_fixture.bundle` supplies registered `asset-input-bundle` version 1.
Its exact fields are `assetBundleVersion`, `runId`, `ticket`, `primaryPath`,
`destination`, `files`. Each file has exactly `relativePath`, `resourceUrl`,
`bytes`, `sha256`. These are controlled original INPUT bytes and paths, never
upload receipts or measured state. Each resource uses the exact owned HTTP(S)
run/ticket path. Validate the closed feature action before accessing resources.

| Resource input | Original primary and required relative companions |
| --- | --- |
| `gltf-bundle/main.gltf` | `main.gltf`, `mesh/triangle.bin`, `textures/checker.png` |
| `obj-bundle/main.obj` | `main.obj`, `materials/palette.mtl`, `textures/checker.png` |
| `asset-stand.fbx` | `stand.fbx`, the hash-pinned original repository `interface/resources/serverless/Models/standAngle.fbx` |

The glTF/OBJ bytes retain the existing parity companion manifest. The small
self-contained shipped FBX retains its existing license and is served without
copying or rewriting it. Its actual oven/render acceptance remains unqualified.
Do not rename a glTF file to FBX or produce baked bytes in Python.

An `upload` action is a bounded composite ordinary recipe: create the private
owned staged input bundle, open Upload with companions, select actual files or
their folder, confirm the real main-file review, enter `/<expanded name>/` in
the actual destination dialog, confirm, wait for original upload completion,
refresh actual mapping rows, then select the primary. Release the original
staged files before the checkpoint only after their actual native consumers
finish. Do not invoke `Assets.uploadBundle` or UI handlers directly as input.

`browse` selects the actual owned primary row. `rename-folder` selects its
actual parent folder, uses normal Rename/confirmation to rename that folder to
`<expanded renamed>`, refreshes and reselects its primary. Extensions and all
companion-relative references remain intact. The following `import-selected`
uses Add to World, fills the real model dialog through ordinary controls,
confirms and records the original returned entity ID. Use a settled unit-size
model two metres in front of the controlled avatar and the normal non-dynamic
model choice. Do not equate a dialog dismissal/ID with loaded or drawn geometry.
`remove-owned-model` deletes only that actual recorded entity normally.

`delete-owned` selects the actual run-owned root folder, uses normal Delete and
its confirmation, refreshes and proves all owned mappings disappeared. Do not
delete just the selected primary and hide surviving companions from the reader.
Do not rename or delete pre-existing namespaces; the qualified isolated fixture
must reject initial ownership/hash collisions rather than adopting other data.

## Actual baking, permission and unavailable-file behavior

`assignment-client/src/assets/AssetServer.cpp` defines FBX as its only bakeable
model extension. The selected glTF primary therefore has original status
Irrelevant (`--`) and a disabled baking control. `inspect-baking-unavailable`
performs no bake API call and observes this stable fact for three seconds.

For FBX, first wait for the original automatic upload bake to finish. This
prevents treating Use baked version as a cancellation control: the actual
`AssetServer::setBakingEnabled(false)` does not promise to cancel a pending oven.
`set-baking(false)` uses the normal checkbox, then requires no active/queued
worker for this original hash and the actual NotBaked redirect to the original
asset. `set-baking(true)` uses the checkbox normally and requires a new original
worker/completion after this action's barrier, successful current-version meta,
readable original oven output and an actual baked mapping to that output.
`BakeAssetTask` runs an existing qualified oven; a callback, checkbox state,
file extension or requested hash cannot supply ready state. Do not start any
server/oven/build now, install one or replace this with a simulated backend.

`set-write-permission` belongs to the independently owned actual domain fixture,
not a client property setter. After actual permission propagation, independently
read `Entities.canWriteAssets` and the normal `assetDelete.enabled` value.
`delete-denied` delivers one ordinary click to the actual disabled Delete
control's observed bounds. Its handler cannot dispatch; no confirmation/error
is invented. Retain unchanged server mappings and visible error `none` for three
seconds. Restoring actual permission must re-enable Delete before real deletion.

`upload-picker-open` stages the real complete glTF bundle and opens the normal
file browser, retaining an original source-bound staging lease. The first use
cancels the observed open picker and releases those actual staged bytes without
upload. The second use selects the actual `main.gltf` row in bundle/multi-select
mode (`chosen` contains its original URL); it does not confirm yet.
`retire-staged-primary` removes only that lease's actual selected primary via
the private owner, preserves its original manifest/path/hash/ticket and leaves
the selected URL in the actual browser. Independent file inspection proves the
original is now absent; an adapter flag alone cannot report retirement.
`upload-picker-accept-unavailable` presses normal Select. The original
`NativeFileBrowser.accept` rechecks `helper.urlIsFile` and shows
`A selected file is no longer available.` while retaining the picker. Require
that actual original error, no destination dialog and no server upload/mapping
for three seconds. Cancel then releases the remaining staged companions/lease.
A host HTTP 404 before opening the picker is infrastructure failure, not this
product error. Never delete an arbitrary path or call the handler directly.

## Fourteen primary and independent observations

`mappings` is the lexically sorted, slash-normalized actual owned server mapping
inventory, including primary and companions, with the leading slash omitted.
`selected` is the actual selected primary row (same normalization), or empty.
`companions` is the sorted relative companion inventory verified through actual
server hashes/downloads and original model/texture consumers, not copied from
the fixture manifest. Inspect hidden baked/meta mappings separately; they are
not disguised as user-facing companion rows.

`baking` means an actual queued/active worker for the selected original hash.
`bakeState` is `none` without a selection, `unsupported` for an irrelevant
primary, `disabled` for the original NotBaked redirect, `baking` for a real
queued/active job or `ready` for a successful original current bake. Failure,
unknown state, unavailable output and stale completion cannot become ready.
`bakeAvailable` is the independently read actual checkbox availability for that
selected supported primary, also reconciled with the original server type.
`canWrite`, `deleteEnabled`, `open`, `picker`, `pickerFile`, `error` describe
actual current original permission/UI, not desired input. `pickerFile` is the
owned public basename `main.gltf` only after actual selection. `error` is `none`
or the original current picker unavailable-file error, never a staging error.
`stagedAvailable` requires a fresh actual file-owner read of this picker lease;
it is false after cancellation/retirement and outside the picker workflow.
`sceneModel` requires the actual recorded owned entity, loaded geometry/texture
and independent remote peer rendering. All fourteen fields require original
independent facts through the existing separate publisher role.

Use current challenge-bearing original PNGs and actual changed model pixels.
The glTF `file` evidence is the original asset-server download consumed for the
selected mapping, compared byte-for-byte with the pinned input. Add to World
produces no imaginary export file. OBJ/FBX additionally require actual original
geometry/texture sources and independently rendered peer effects; a UI row or
the input fixture HTTP GET does not prove these effects.

## Limits, ownership and cleanup

Use the existing twenty-second checkpoint deadline, actual native clock,
PID/source continuity, fresh run/ticket barriers and original source sequences.
The small FBX's initial automatic and later explicit enabled bake must each
complete within that bounded window. Fail unavailable/slow qualified backends
explicitly; never extend timeouts silently or turn missing required capability
into a green run. Preserve the existing three-second negative/cleanup windows.

Cleanup is idempotent but independently verified: close owned model/destination/
file dialogs, settle or retire original native upload consumers, restore actual
domain write permission, remove only original owned entities and namespaces,
observe no queued/active original bake and no owned original/hidden baked/meta
mappings or unshared stored blobs, and release actual private staged files and
leases. `deleteMappings` removes unreferenced originals and their baked paths;
inspect that outcome rather than relying on its success callback. Preserve
unresolved IDs/paths/leases after partial failure; never clear an inventory to
claim cleanup. Do not delete shared product caches or unowned content. The
independently owned ephemeral domain/server teardown remains mandatory at its
existing session boundary.

The complete adapter still needs source-bound ordinary Assets/picker controls,
original staging retirement, current mapping/selection/model readers, real
server/oven worker/output receipts, independent peer/publisher and observed
cleanup on each platform. These are implementation gaps, not accepted device
results. Functional product changes are outside this instrumentation phase.

The v13 packet passes 787 explicit common host checks, including six original
QML/fixture checks and new ignored-bake, broken-bundle, disabled-Delete,
file-retirement/error and unintended-upload counterexamples. No compiler,
backend, installation or device was launched.
