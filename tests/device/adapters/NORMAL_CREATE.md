# Normal Create adapter packet

`normal_create.py` implements the existing eight `create.*` foundation operations.
the Phone-owned `android-phone/overte_phone_create_ui.py` binds the Phone's normal `NativeCreate.qml` controls.
The existing independent `create_journey.py`/fixture observer judges actual
entity properties, avatar hosting/ownership, parent-child imports and history.
This packet does not advertise the larger `feature.create.*` v1 contract.

The normal script-manager flow loads **only** the owned `/create/<nonce>/observer.js`
through its ordinary From URL dialog. Its separate private source-kind ownership
is `create-observer`. The script is the already existing read-only entity
observer. Native actions never invoke `Entities.addEntity`, `editEntity`,
`deleteEntity`, or any Create bridge message or hidden service call.

For input ownership, request the probe diagnostic with `includeAvatarEntities:true`.
The original diagnostic adds `entitiesComplete` and `avatarEntities`, projected
from fresh `Entities.findEntities(MyAvatar.position,64)` and actual properties.
Only entities whose native `entityHostType` is `avatar` and whose nonzero
`owningAvatarID` equals the current avatar's actual session/SELF identity are
included. Each row is `{id:<original native UUID>,name:<actual name>,type:<actual type>}`.
The query fails closed above 4096 queried/256 owned entities or on any read
error. Complete false is never an empty-world observation. This diagnostic
provides native input-row identity; the independent HTTP observer still verifies
all properties and actual source delivery. Neither consumes expected results.

Refuse pre-existing matching names before acquiring the unpredictable fixture
namespace. Save the real pre-create native ID set and owned intended name before
clicking Shape. Recover exactly one new native avatar Shape/Box, select its real
List row, name it through the real property field and apply. Multiple new entities
are ambiguous and retain unresolved intent. An ignored creation must time out;
cleanup observes another three-second fresh window before retiring an absent
creation. An uncertain creation is never replayed. Store actual observed IDs
alongside owned names; a foreign replacement cannot inherit a historical name.
Cleanup can delete the actual measured unnamed UUID directly; it must not
require an ignored or broken Name edit to start functioning before removing
that owned partial effect. Name/Color/Dimensions input uses ordinary W3C key
events to deliver Qt `textEdited`, with native field readback and modifier release.

Create uses NEW/My avatar/Cube/Shape, then ordinary Name, Color and Dimensions
fields/Apply. LIST/Refresh and the actual UUID identify each selected entity.
Undo/Redo remain normal buttons and are allowed only after owned history input.
Fresh post-history identity samples allow real recreated IDs to be retained.
IMPORT uses its own My avatar host, source field and Import URL button; only the
same exact owned fixture origin and nonce are allowed. Deletion selects and
deletes each actual owned row, then independently waits for native disappearance.

The stock host ComboBox has no option objectNames. The binding resolves its
actual `My avatar` option through accessibility, checks package, native class,
visibility, enabled state and excludes the current ComboBox's own resource ID.
Ambiguous options fail. There is no coordinate or product-service fallback.
The existing unlabelled shape chooser must actually expose Cube. Off-screen or
unexported fields fail within the bounded native wait; real-device qualification
must establish their accessibility and normal scrolling on the selected layout.

A positive JSON import has no exposed native cancellation/completion token.
If it times out or returns an uncertain response, its pre-input ownership intent
is retained. Cleanup can recover its complete actual parent+child result; it
cannot turn a still-outstanding or partial import into successful empty cleanup.
An unresolved import keeps the diagnostic source and private sidecar for later
recovery. App process termination alone does not prove that persisted avatar
entities or the observer's script were removed.

Cleanup deletes the known native entities before stopping the read-only observer,
measures an actual empty owned scope, restores normal Script Manager navigation,
stops only the exact owned source and closes owned panels. Repeated cleanup is
idempotent; foreign panels, sources, processes, UUIDs and fixture namespaces are
refused. The original common journey additionally requires advancing empty
entity frames. Host counterexamples cover ignored input, anonymous partial
creation, duplicate effects, failed queries, foreign IDs and unresolved imports.
These checks prove adapter control logic only; no device acceptance is claimed.
