# Create source and adapter boundary, common journey v8

The reviewed Phone/Pico/iOS product sources distinguish ordinary model creation
from importing an entity-JSON document. Twenty-one common checkpoints exercise
those actual paths, original texture/export effects, voxels and rez recovery.
This corrects shared test logic; complete product adapters are still missing.

## Ordinary controls and controlled input

NativeCreate.qml NEW Model reads NativeCreateResourceUrl and sends a Model
creation with modelURL through the existing Create bridge. Use the owned
`gltf-bundle/main.gltf` or `obj-bundle/main.obj` URL under the current model-create
ticket. Preserve the original complete relative mesh/material/texture bundle.
Select Domain in NativeCreateHost, create normally, then use ordinary Properties
to set this run's owned model name and unit dimensions. The real selected UUID,
creator/context and independent domain observation must establish ownership;
a newly matching basename alone cannot be adopted or deleted.

The different IMPORT Browse button, NativeCreateBrowse, calls the existing
Window.browseAsync("Select .json to Import", "", "*.json"). It imports a real
entity-JSON file through Clipboard.importEntities/pasteEntities, updates the
actual selection and participates in ordinary undo history. It cannot serve as
a raw glTF/OBJ picker. import-picker-open stages only owned entity-import.json
input, selects Domain in NativeCreateImportHost, clicks that Browse button and
observes the actual caption/filter/mode/root identity. import-picker-cancel
uses the real Cancel control, then independently observes picker absence and no
new entity/selection for the full three-second quiet window. Accept selects the
original owned JSON file through normal file-picker inputs and must result in
an independently observed actual model/selection, never an ACK-only import.

`fixtures.import_document(run,ticket,fixtureUrl)` builds controlled INPUT bytes
with explicit validated actual owned fixture origin, DataVersion 3, unit geometry
and the pinned glTF model URL. It carries no future texture override. Persist
staging intent and original bytes/hash/inode before presenting it to the product;
retain that input's original resource ticket across later acceptance. Remove
only this run's staged originals after the picker is observed closed. The
existing Script file picker/storage components have different caption/filter/
file vocabularies and do not implement this JSON role automatically. Extend the
existing native file mechanism with an explicitly versioned source role; never
relax Script-root admission or use a direct Clipboard call as adapter input.

The separately exposed IMPORT URL button is not this local-picker test. Existing
create-management foundations keep ownership of their JSON parent/child URL
walk and Cube edit/history/delete tests. No parallel runner is introduced.

## Original texture and export assertions

The pinned glTF image URI is textures/checker.png. GLTFSerializer::getHFMTexture
sets hfmTex.name to the original URI's filename, checker.png. Geometry::getTextures
uses the original network texture name as its map key; the renderer's original
textureNames observation must agree before editing. Apply the generated texture
from the separate apply-texture ticket through ordinary Properties, assigning
exactly the checker.png slot. A different map key cannot establish a remap even
when its value equals the requested URL. Require original native resolved slot/
texture bytes plus actual changed visible model pixels and independent peer
appearance. A property string alone is insufficient.

Export selection uses the ordinary NativeCreateTool_export control and the real
Save dialog. Independently enumerate/read the resulting original product file;
never save/download an assertion reference and claim it was exported. The
unused public export.json reference route has been removed. A private reference
function only supplies byte assertions in the common test, not observations.

Application::exportEntities constructs a new EntityTree. Its Octree persistence
version initializes to 0, and EntityTree::writeToMap serializes it unchanged.
Thus real exported DataVersion is 0, distinct from the input fixture's version 3.
Retain the exact one owned Model, name, source URL from the model-create ticket,
unit dimensions and checker.png texture override from its own ticket. Allow the
actual string-encoded JSON texture map or object form; reject duplicate/nonfinite
JSON, wrong keys, empty/null/foreign entities and rewritten geometry/source.
Do not rewrite original export bytes to match the fixture. Native packet Version,
IDs and unrelated real serialized fields are preserved, not guessed into output.

## Permission recovery, observations and cleanup

Use the controlled domain, not avatar/local entities, for these extension flows.
The fixture authority changes actual effective rez permissions: NativeCreate
accepts either canRez or canRezTmp, so deny both before the ordinary create-denied
Cube action. Independently observe no new entity and the actual UI permission
error. Restore the original rights and perform an ordinary new Cube create,
observe its real owned UUID/selection/pixels remotely, then delete it normally.
A permission-setting ACK without a successful create cannot pass recovery.

The independent Create witness now measures every state field, including actual
editor/picker/error state, objects/selection, effective permission, resolved
texture effect and settled voxel change. It acquires original UI/domain sources
separately from the primary adapter. The actual PolyVox cube/remove 0.5-metre
stroke and saved-byte semantics remain in the existing handoff. A successful
input, primary error echo or generated expected file is no measurement.

Before each input persist selected source/profile/process/session/domain and
partial entity/picker/file/export ownership. Keep initial permissions, editor
settings and original focus/held routes. Cleanup closes only owned dialogs,
deletes only owned model/Cube/voxel entities through existing normal controls,
restores original rights/settings, removes original staged/exported files and
requires independent empty domain/UI/file inventories before journal retirement.
Ignored cancel/create/delete or unresolved picker/source/file ownership fails.

Existing Script picker identities cannot be relabeled as Create dialogs. Phone's
narrow Cube/JSON foundation does not implement the new full Model/JSON/voxel/
export joins. Pico/iOS require corresponding real source-bound normal controls;
iOS installed-code association stays blocked. Source-only/JS boundary checks
confirm test logic, never native compilation, product behavior or devices.

Restoring domain rez rights does not clear the existing native status label.
Keep the observed permission error through the passive permission/selection
refresh; only the subsequent real successful create response clears it. The
common retry and independent UI facts now enforce that source behavior.
