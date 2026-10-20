# Original Graphics subject observations, version 1

This is a passive E2E source prerequisite. It does not load a scene, set a camera,
change entities/preferences, classify pixels or activate a full feature capability.
The native hook requires the existing default-off `OVERTE_E2E_FEATURE_TESTS`,
`--testScript`, private results root and original live lifecycle context. Native
source is uncompiled and all physical clients remain untested.

The closed existing probe command is `{schemaVersion:1,commandId:<32hex>,
action:"feature-graphics-subject-observe",runId:<32hex>}`. The existing iOS
fixture grammar also recognizes its `ios-<32hex>` form; no iOS adapter is
implemented by this Phone package. No entity list, file path, target value or
expected state is accepted. Native execution marshals to the application thread.
The probe deduplicates the current command, calls the native getter once and
saves its original object as `feature-graphics-subject.json` through the existing
atomic private writer. Missing hooks/results remain explicitly unavailable.

The original envelope has `schemaVersion:1`, `requestId`, `runId`, native Test
`instance`, advancing source `sequence`, actual `processId`, original
`requestedEpochMs/capturedEpochMs` and `source`. Source has `subjectVersion:1`,
actual AddressManager `sceneUrl`, actual Camera frustum `view`, `entities`,
`absentIds` and `scan`. View includes native world `position:[x,y,z]`,
`rotation:[x,y,z,w]`, actual camera mode string, `fieldOfViewDegrees`, `aspectRatio`
and `perspective:boolean`. This is the current native camera, not a declaration
that a particular queued GPU image used that pose. Full coordination must hold
and independently verify the scene/view around original image acquisition.

Native code derives exactly seven UUIDv5 selectors from the original run bytes,
using the same namespace and `graphics-subject-v1/<name>` names as the controlled
scene generator. Each UUID is directly queried through EntityScriptingInterface,
including after movement beyond the scan, renaming or hiding. Only actual Unknown
entity type produces an absence row. Present rows preserve actual name/type,
host type, position/rotation/dimensions/color/visibility, mirror mode, haze mode,
Web source URL, edit epoch and original Zone haze range/color/altitude/glare/
background blend. Selectors identify queries; requested values are never returned
as measured feature state. Every UUID must appear exactly once in present or
absent inventory. Missing/overlapping/duplicate/foreign rows fail closed.

The additional scan explicitly covers only entities intersecting the sphere
centered at `[0,0,0]` with radius 128 meters, across local/domain/avatar host
types. At most 1024 returned IDs are allowed. `scan` has that center/radius,
`propertyScope:"graphics-spatial-v1"`, `scannedEntities` and `unowned` rows of
original UUID/SHA-256. Each hash covers the same spatial/visual property fields
described above, excluding edit timestamps. This is **not** a global entity
inventory or a hash of every product property (for example scripts/model URLs).
It cannot alone prove complete foreign-entity preservation. A full owner must
establish an isolated controlled scene and separately verify any additional
original state it changes. Owned UUID absence is always queried directly and
does not rely on this limited scan. Individual native reads span the original
request/capture interval; no atomic whole-world snapshot is claimed.

The original source JSON is capped at 200000 bytes; the transport/reader cap is
262144 bytes including its envelope. Source sampling must finish within 1500 ms.
The Phone reader keeps the existing five-second/51-read command budget, actual
device clock, target/candidate/process guards and original context/cursor floors.
Decode, validation and final freshness/guard checks count toward the budget.
Only file reads retry; native delivery is not replayed. iOS component parsing
uses the existing 1.5-second unpredictable-nonce bound without equating wall clocks.
Neither parser supplies defaults for missing inventory, projection or native state.

The internal Phone `_graphics_subject_observer(...,read_only=True)` uses the
existing bound session without bootstrap or input. Its closed read admission
rejects preparation/input/expected-value commands. A future full owner must
persist each role's original source cursors and historical context before returning
a feature result; rebuilding a reader is not permission to reset provenance.
Original metadata is private evidence, not an owned live entity or image buffer.

Nineteen synthetic reader/probe cases cover direct observed properties, explicit
absence, moved/renamed/hidden UUIDs, incomplete/conflicting inventories, foreign
objects, malformed camera/entity/haze fields, restricted scan scope, stale or
replaced originals, ignored delivery, bounded read retries/decode and final
freshness/guard budgets. Three Phone factory checks cover original transport,
changed candidate/process refusal and closed independent read admission. These
verify test logic only; they do not qualify native behavior, scene loading or
rendering on a device.
