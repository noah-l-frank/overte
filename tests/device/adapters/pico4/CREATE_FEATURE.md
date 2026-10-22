# Pico Create continuation: ordinary management foundation

Feature 4/14 remains **partial**. This change completes the source composition
of the existing `create-management-parity` foundation on Pico. It adds no
`feature.create.act`, `feature.create.observe` or `feature.create.cleanup`
capability. The twenty-one-checkpoint full feature contract still needs the
domain Model/texture/export/JSON-picker/PolyVox/rez-permission joins below.
The isolated Qt5 file-storage and original picker/input harnesses compile and
pass. Complete native application compilation and physical Pico behavior remain
unverified.

## Implemented normal vertical flow

The existing catalog module calls `OverteSession` for the controlled scene and
the existing versioned `create.*` operations for ordinary input. The bound Pico
router now supplies those operations through
[`PicoCreateManagement`](create_management.py), the shared
[`NormalCreate`](../normal_create.py) owner and
[`TokenCreateUI`](../token_create_ui.py). The actual candidate-bound
`PicoNavigation` transport continues to deliver native pointer/keyboard input
in the real VR tablet. No Entities mutation, direct Clipboard call, private
QML signal or expected-state producer provides input.

Enable `OVERTE_PICO_NORMAL_CREATE=1` alongside the existing
`OVERTE_PICO_NORMAL_SCRIPTS=1`, debug/OpenXR-input configuration and owned
`OVERTE_E2E_SCENE_URL`. The normal installed candidate, PID/start, OpenXR nonce
and UI-token checks remain mandatory. Advertisement defaults off. The existing
Create fixture credentials belong to the runner; the adapter does not need or
receive the fixture control token.

The source sequence opens Running Scripts normally, loads only the owned
read-only observer, reaches Create through the actual observed VR Home Gizmo,
creates an avatar Cube, names/edits it, uses normal history/delete controls,
imports the parent/child JSON URL, and submits the separate owned `missing.json`
404 input. Reopening Running Scripts for cleanup uses that same original Home
ray. A QML `tablet.home` control is not assumed to exist in the 3D tablet.

The existing fixture's original observer supplies actual type/shape, dimensions,
RGB, host and parent effects, independently of the input journal. The common
journey requires fresh complete frames, source delivery and actual HTTP 404
delivery. Its original JSON report retains all samples and explicitly limits
qualification to Cube/edit/history/JSON. Input acknowledgements do not establish
an edit or import effect. No stereo/image or remote domain actor evidence is
claimed by this foundation.

## Ownership, failure and retirement

Private 0600 journals live in the already configured canonical 0700 input-state
directory. Filenames hash the target; no selector enters public evidence.
Separate records retain actual candidate/process/session binding, the shared
partial entity/import/history owner, Script-service ownership, one bounded
original Create/Home input record and the current operation attempt. A stable
owned lock serializes this flow. A regular Script-manager reservation blocks
Create rather than being adopted.

An attempt is persisted before input. After a lost input result, only measured
delete/close cleanup is admitted; create, edit, import, history and open are not
reissued. Pending creation retains its original before-ID set; pending import
cannot retire on an empty read. Foreign replacement IDs, failed intent writes,
incomplete reads, ignored delete/Stop and candidate changes retain ownership.
An unused initial reader can retire after a rejected baseline without opening
the tablet or touching the pre-existing entities.

Cleanup deletes only measured owned IDs through normal controls. It requires
three seconds of complete empty owned-entity observations, normal observer Stop,
another three seconds of complete empty entities and actual Script-service
absence, then actual tablet absence/release. Journals retire only afterward.
If interruption leaves a terminal journal without the main owner, cleanup fails
closed and preserves that record; no missing record is interpreted as release.
The bound adapter still reaches its existing application teardown after a
cleanup failure and reports failure instead of erasing unresolved Create state.

The existing normal control wait is ten seconds, the common effect wait twenty
seconds, and this owner adds the two bounded three-second retirement windows.
All clocks/cursors and native identities retain their original producer values.

## Remaining full-feature boundary

The full feature uses **domain** entities. The implemented foundation uses the
existing serverless scene's avatar-entity rights and cannot stand in for it.
The next executable source work is:

- The [explicit Create JSON storage role](CREATE_FILES_SOURCE.md) now stages and
  independently reads original input/output bytes, and the
  [actual Import/Save control source](CREATE_FILE_UI.md) now binds normal input
  and original weak Qt roots. The separate
  [original native Script callback source](CREATE_CALLBACK_SOURCE.md) observes
  actual connections and in-flight dispatches. Compose these with the full
  feature, actual domain effects and native ModalDialog delivery sources. Script
  file roots and picker identities must remain distinct. Observe cancel and
  accept through their original retained callbacks and a quiet absence window.
- Compose normal Domain/New Model/Properties input with actual selected UUID,
  creator/context and a separately acquired domain/peer original. Resolve the
  original `checker.png` texture slot and bytes, actual model drawing and both
  eye captures before claiming the texture effect.
- Drive the actual Export selection Save dialog. Independently enumerate/read
  the original product-exported DataVersion 0 file, retaining its exact model
  and separate texture ticket. A generated reference file is not an export.
- Bind the actual Tools controls `NativeCreateEditMode`, `NativeCreateVoxelShape`,
  `NativeCreateVoxelRemove`, `NativeCreateVoxelDynamics`,
  `NativeCreateVoxelPointer`, `NativeCreateVoxelDiameter`,
  `NativeCreateVoxelReach` and `NativeCreateVoxelApply`, then the actual unlocked
  PolyVox world trigger stroke. The current native Create token inventory does
  not expose those controls or an independently observed settled voxel change.
- Supply the independently owned domain authority for both effective `canRez`
  and `canRezTmp`, retain the actual denied UI error, restore original rights,
  prove a real normal recovery Cube and delete it. Add the independent full
  feature publisher, original artifacts, permission/settings restoration and
  complete role/resource retirement before enabling the full capability triple.

These are concrete missing source/backend joins. Host tests cannot qualify the
native implementation, headset rendering or a device. A separately authorized
native build and later Proxmox device qualification remain necessary.

## Integration and selected verification

The binding changes add only the existing `create.*` routing, opt-in capability
advertisement, Create cleanup before base teardown and the private factory.
`_create_controls` now uses the original UI runtime directly: passive control
reads no longer reserve the unrelated regular Script-manager journal. The shared
TokenCreateUI fix admits the already contracted owned `missing.json` error URL;
wire format, source controls and all other platforms remain unchanged.

The registry adds `pico-create-management` v1. The existing Pico `normal-create`
suite imports the new owner cases, so no new catalog case or coverage-count
adjustment is necessary. Aggregate feature coverage should retain `partial`
and an empty `completeOperations` list, add this module/document as sources and
record the now-wired `create-management-parity` foundation. Complete area count
remains three of fourteen.

Selected host commands use `PYTHONDONTWRITEBYTECODE=1` and a private owned TMPDIR.
Run `test_normal_create` plus the shared NormalCreate, TokenCreateUI, original
Create journey/source and Pico Home suites. The latter include only inspected
Python/Node logic and short-lived owned loopback fixtures; no device, build,
compiler, installation, dependency or service provisioning is needed. Also run
the contract-version, generated feature inventory, documentation and whitespace
checks. Exact results are recorded in the local commit handoff.
