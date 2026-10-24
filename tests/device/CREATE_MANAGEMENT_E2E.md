# Normal Create editing and JSON import

`create-management-parity` uses ordinary Create controls in the existing
controlled serverless scene. It creates an owned avatar Cube, changes its color
and dimensions, undoes/redoes the edit, deletes and restores it, and exercises
parent-child JSON import with undo/redo and an actual HTTP 404 import. These are
locally implemented assertions; native adapters and device acceptance remain
pending. No native adapter advertises the new operations yet.

## Native input contract

- `create.reference.open`: load only the owned read-only observer through normal
  Running Scripts and consent, then open the actual Create panel.
- `create.cube`: choose My avatar, choose Cube and activate
  `NativeCreateNew_Shape`; use the actual Name, RGB and dimensions fields and
  Apply. Keep the new selection's native UI identity for partial-failure cleanup.
- `create.update`: select the uniquely named owned object and apply the supplied
  RGB and dimensions through those normal fields.
- `create.undo`, `create.redo`: activate the actual history controls.
- `create.delete`: select/delete only the supplied unique owned names; be
  idempotent when absent. Never use a blanket world cleanup.
- `create.import`: select My avatar in the Import tab, enter the exact owned
  fixture URL and activate the normal Import URL control.
- `create.reference.close`: stop only the owned observer through Running Scripts
  and dismiss the owned panels/dialogs. Partial entry must also be cleaned up.

Every action returns only `performed: true`. No direct Entities mutation,
Clipboard call, QML bridge injection or probe command substitutes for input.
Adapters must clean up their own transient unnamed selection if naming failed;
an unrelated user selection/history entry is never an authorized cleanup target.

## Independent observation

The ordinary `fixture/create_management/observer.js` calls only native entity
read APIs. It filters unpredictable per-run names, bounds the query/output and
reports actual color, dimensions, type, host and parent relationships. Own-avatar
identity follows the product's session-UUID or SELF_ID semantics; the identities
themselves and unrelated parent/name data are omitted from transport.

ShapeEntityItem serializes Cube using its legacy Box alias. Both exact Cube
representations qualify; a Sphere, foreign host or unowned object does not.
Each expected state needs three fresh complete native frames spanning at least
half a second. New controller polls of one frozen frame cannot prove progress
or absence. Failed reads, budget exhaustion, changed old frames, process or
observer replacement, stale fixture source and cleanup failures fail.

Import checks the actual two named objects and their parent-child relationship.
Undo/redo may legitimately assign new entity IDs; the assertion checks the
resulting names/properties/relationship instead of echoing expected IDs. The
failed-import case requires an actual HTTP 404 request and live empty observations.
Cleanup of named objects is enabled only after an empty live baseline; a
pre-existing matching object disables destructive cleanup.

## Owned host fixtures

Start `python3 tests/device/fixture/create_management.py --bind 0.0.0.0
--public-host <reachable-lab-host> --ready-file <private-create-environment.json>`.
Its mode `0600` environment file contains only the owned fixture URL and private
control token. Import those values into the pipeline process environment using
the existing private environment-file mechanism; never print the token or put
it in a command argument. The normal scene fixture may be owned by provider
`auto`, or supplied alongside the Create values in an external environment file.
The execution profile requires both Create keys before discovering a target.

The module loads the existing controlled serverless scene before beginning.
Application's ordinary successfully parsed serverless-scene path grants the
needed avatar-entity permissions. The diagnostic never changes permissions.
An arbitrary public domain with different rights is not the test precondition.

The control token is excluded from adapter discovery, verification, diagnostics
and input subprocesses. The existing bounded, redirect-refusing control client
reads source-bound observations. The observer's retried event body remains
immutable until acknowledged, preventing mutable world data from being relabeled
as an earlier native frame. Private native samples stay in runner artifacts.

This journey covers the named Cube/history/JSON operations. It does not qualify
visual geometry, voxel tools, model/texture companion imports, local file import,
exports, permission-denial UX or the entire Create feature. Exact application
source/artifact/installed-code identity and actual platform observations are
required before any device acceptance.
