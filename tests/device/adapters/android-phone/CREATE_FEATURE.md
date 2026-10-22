# Phone Create common v17 adapter

The source implementation now composes the complete default-off
`feature.create.act|observe|cleanup` triple through the existing Phone adapter
and unchanged common v17 journey. Host verification uses explicit synthetic
native/SDK/render endpoints, real private host artifacts and loopback HTTP. It
is not an Android application build, real rendering/latency proof or physical
device acceptance. Global feature counts and final source-pin regeneration stay
with the integration owner.

## Public configuration and ordinary inputs

Enable `OVERTE_PHONE_FEATURE_CREATE=1` only with a bound debug Phone candidate,
the existing private fixture access configuration and a private mode-0600 JSON
file named by `OVERTE_PHONE_CREATE_CONFIGURATION`. Its exact fields are
`createFeatureVersion: 1`, `artifactRoot`, `imageExtent`, `markerRoi`,
`imagePolicy`, `domainId`, `permissionsControlUrl` and `permissionsControlToken`.
The artifact parent must be absolute/private. The permission URL must be the
owned loopback `/v1/create-permissions` endpoint of a domain fixture launched
with `--feature-create-permissions`. Its domain process/start identity, `/id`,
Settings identity, original standard permission rows and outside-settings hash
remain separately guarded by `fixture/create_permissions.py`.

`imagePolicy` contains `source: "world-render-target"`, `marker` and `subject`.
The marker rectangle must cover the encoded 128 cells inside the requested
160-by-40 card, scaled from its original four-pixel border. The subject must
contain the actual projected controlled model/voxel body without exceeding twice
its bounding rectangle. For a 1000-by-750 target and marker ROI
`[20,20,180,60]`, the encoded marker is `[24,24,152,56]`; the tested controlled
body policy is `[280,155,720,595]`. These are fixture input/layout parameters,
never supplied product facts.

Inputs use existing SDK tablet/View-menu controls and actual token-qualified
Qt widgets. Model URL/Domain/New, naming/unit transforms, actual texture fields,
JSON Browse/Cancel/Select, Export/Save, voxel preferences and the world pointer
all retain intent before delivery. An ACK does not become an observation.
New UUID ownership requires a pre-input inventory, actual selected UUID,
original native lifetime, creation timestamp, native editor session, domain,
host/root/unlocked checks, and an immutable responsibility record before normal
property edits. Reconstructed owners revalidate that record before any input.
The actual native name/position/unit dimensions are read back after editing.
The passive QML settings-receipt bit prevents placeholder widget defaults from
becoming original tool preferences; normal Apply settings are read back before
the world pointer.

NativeCreate's existing New PolyVox button creates an **empty 32-cubed** volume.
The agreed common fixture requires an 8-cubed volume with a central 4-cubed
occupied cube. Therefore public `voxel-create` uses the real normal JSON picker
to import the fixed, exclusively staged Entity JSON, then normal Properties.
`voxel-edit` configures ordinary Voxels/Cube/One click/Ray/Remove/0.5-metre
controls, closes the tablet, sends a normal W3C world pointer at the actual
projected object, checks actual touch release, and reopens the actual Create
page. There is no hidden `Entities.setVoxels`, Clipboard setter or QML-handler
shortcut. This composite preserves the closed public action/effect and requires
no common version change.

## Independent original observations

The separately credentialed existing `script_observer.py` entry point supports
`featureObserverVersion: 4, area: "create"`. Its exact usual fields are target,
candidate arguments, fixture URL, actor token and duration. It has neither the
primary reader token nor the permission-control token. It reads the original
public configuration/digest from the run header and must run in a different
actual host process; PID/start identity cannot be adopted by another process.
It waits for the same ticket's completed input barrier, then acquires its own
new originals. It never calls primary observe or borrows primary frames.

Each role joins fresh native lifecycle, entity/permission, original UI and avatar
sources with the actual scoped Web/Java authorities. Visible fixture captures
retain their own native acquisition, PNG, main-mono model draw and separate
memory/receipt retirement originals. The E2E-only fixture owns exactly three
original local objects: a gray backdrop, fixed contrasting half-backdrop and
marker. The contrast keeps the empty subject nonuniform after deletion. Exact
geometry, local host, weak object lifetime and Web retirement are checked;
foreign children, same-UUID replacements and revived runs are refused.

Model evidence binds the actual entity lifetime and current model URL to the
loaded HFM source, Model/Geometry instances and that capture's original geometry
draw commands. The actual draw bounds/center and projected body qualify the
normal transform and configured subject. Static immutable render metadata is
not arbitrarily retimed or subjected to a 1.5-second metadata age rule. Texture
facts require the actual editable assignment, matching URL digest, consumed
original PNG digest/length and 16-by-16 GPU extent. The render-thread model copy
and QObject-owner-thread texture observations retain mutex-protected snapshots;
refresh/decoder overlap or foreign-thread state cannot complete a mixed copy.

Voxel readiness, 8-cubed extent, saved-byte digest, actual 512-cell digest and
occupied count are separate originals. Each role's initial actual central-cube
baseline is recovered from its immutable frame history. Loading supplies no
default fact. Removal requires changed actual cells, a lower occupied count and
changed saved data. The common verifier independently checks fresh original
challenge pixels and changed subject bytes.

## Files, interruption and cleanup

The actual native `PrivateCreateFiles.h` exclusively creates the two fixed input
files under one private `feature-create-<run>` directory. It never writes the
product's `selection.json`. Export uses ordinary Save; the owner independently
reads/seals the actual inode/bytes and retains an exclusive host artifact.
Symlinks, hard links, FIFOs, foreign children, roots, output replacements and
changed ownership remain red. The permission fixture changes actual owned-domain
Settings and restores the exact original rows; Interface's native permission
source independently supplies observed `canRez`.

Immutable role/input originals and bounded manifests preserve source cursors,
input intent and native receipt retirement. Interrupted originals, manifests,
owned PNG prefixes and export prefixes resume only exact owned bytes. Native PNG
memory is read before its actual release when needed for recovery. Unknown
files are never adopted or overwritten. A reconstructed action cannot replay an
uncertain ordinary input. Pending product objects retain exact responsibility;
cleanup cancels an owned picker, restores owned permissions/preferences/camera,
deletes only original owned entities, drains original marker/Web/touch sources
and retires the actual private file lease. Repeated cleanup obtains new actual
restoration/absence reads and validates the original export artifact.

The actor completes its own fresh three-second cleanup window and an actual
backend publication. Fixture closure is a separate original. Only after actual
actor process exit can whole-run retirement archive every exact child header,
original reference and fresh restored-world proof before pruning child journals
and the run owner. Ignored child unlinks and lost final unlink replies keep the
parent recoverable. Immutable result artifacts stay retained; the shared source
lock inode stays stable. Missing actor/source/receipt capabilities remain red.

## Host verification and remaining device boundary

Focused checks, without device, installation, Jenkins, fetch or GitHub writes:

```sh
python3 android/phone/tests/device/test_create_source.py
python3 android/phone/tests/device/test_create_workflows.py
python3 android/phone/tests/device/test_create_marker.py
python3 android/phone/tests/device/test_create_measurements.py
python3 android/phone/tests/device/test_create_registration.py
python3 tests/device/self_tests/test_create_permissions.py
python3 android/phone/tests/device/test_create_files.py
python3 android/phone/tests/device/test_create_native_ui.py
python3 android/phone/tests/device/test_create_native_measurements.py
python3 android/phone/tests/device/test_create_texture_state.py
python3 android/phone/tests/device/test_create_native_fixture.py
python3 android/phone/tests/device/test_create_feature.py
```

All are registered in `android/phone/tests/phone-e2e-runtime-regressions.py` with
Qt/compiler-dependent checks in Prepared and dependency-light checks in Common.
The complete Create composition gets the same 240-second aggregate host budget
as the full Graphics composition. Real per-call monotonic deadlines, source
freshness and common checkpoint/three-second absence windows are unchanged.
Do not run the entire mixed runner as an unreviewed device/build fallback.

The complete host module executes all 21 unchanged common v17 steps using a
separate actual actor process, real token-separated loopback coordinator,
actual compiled native private-file header and loopback Settings API. Its
explicit synthetic native/fixture transport shares a deterministic query epoch,
as other host source fixtures do; ordinary monotonic deadlines and absence
windows still use real time. An actor measurement gap over 1.5 seconds restarts
the entire real three-second cleanup window; consistently slow originals never
complete it. Old-source and actual 5.1-second blocked-source
counterexamples remain red even under this synthetic epoch. This is protocol,
byte/ownership and composition verification, **not a real latency proof**.

Prepared Qt 6.11.2 checks use only fresh private folders below this worktree's
`build/create-native-contract`. They compile/execute the actual controls,
private-file, observation, texture-state and fixture headers. The UI check loads
actual NativeCreate and NativeFileBrowser QML offscreen; observation and
fixture checks use explicitly synthetic Entity/Model/Domain/Frustum endpoints.
They do not compile the concrete Android/Test integration or full Android
application, execute real model/voxel rendering or qualify hardware. Physical
end-to-end acceptance remains untested. Probe source edits require the central
integration owner's single final Emote source-pin regeneration/check.
