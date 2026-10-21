# Original Phone Emote fixture input and inventory, version 1

This adds guarded fixture setup and a separate original observation source for
the Phone Emote run. It creates only one local gray backdrop Box and one local
challenge Web entity inside the existing domain. It never navigates to a
serverless scene or invokes Emote/animation/camera/preference setters. Ordinary
Emote user inputs, actual animation effects, PNG evidence, independent actor and
whole-run ownership remain separate. No complete feature capability is enabled.
Native additions are uncompiled and no devices have been tested.

## Input contract and admission

`Test.phoneEmoteFixtureInput` requires `OVERTE_E2E_FEATURE_TESTS`, the Phone
interface, `--testScript`, an active private results/lifecycle scope and owning
GUI thread. Its exact commands are:

* Prepare: `{schemaVersion:1,commandId,action:"phone-emote-fixture-input",
  operation:"prepare",runId,fixtureUrl,ticket,imageExtent,markerRoi}`.
* Release: `{schemaVersion:1,commandId,action:"phone-emote-fixture-input",
  operation:"release",runId,fixtureInstance}`.

All IDs are 32 lowercase hex. The HTTP(S) root is the exact credential-free,
query-free `/feature-fixture/v1/runs/<runId>/` URL, using existing Web-fixture
admission. `imageExtent:[width,height]` has integral 240..16384 dimensions;
`markerRoi:[x0,y0,x1,y1]` is inside it, at least 160x40 and at most 10% of image
area. These are construction INPUTS, never measured render dimensions or pixels.
The eventual owner must separately require actual capture extent/policy matching.

The original native camera must be perspective Selfie with actual boom 3..12,
finite valid frustum, pose and scale, and extent aspect within 0.005 of actual
native frustum aspect. The existing normal [view owner](../adapters/android-phone/EMOTE_VIEW.md)
prepares that view first. Inverse original projection places the Web at
`max(0.25,2*nearClip)` exactly within the requested pixel rectangle. Its source
is the existing owned `tickets/<prepare-ticket>/graphics-marker.v1.html`, which
polls actual current challenge bytes. The backdrop lies behind the original
avatar feet at camera-space depth `dot(feet-camera,forward)+4*modelScale`, covers
110% of the original frustum and is gray [128,128,128]. Both objects use actual
camera rotation, 0.01-meter thickness, local host, collisionless, unlocked,
visible, no cast shadow; the Web uses DPI 100. Geometry is fixture stimulus.

Creation uses the regular local EntityScriptingInterface add path and retains
its actual returned random UUIDs. Native metadata is reserved before creation;
partial/failed creation remains visible as failed, with nullable actual IDs.
There is no arbitrary entity JSON, requested UUID, desired result, general
setting mutation or deletion-by-name-prefix route. A same-command duplicate
returns only its original receipt; same-ID changed input is refused. A second
prepare for the same run is refused. Another run is admitted only after actual
old object drainage; the parent must additionally finish Browser/host retirement.

Receipt is exactly `phoneEmoteFixtureInputVersion:1`, `commandId`, `runId`,
`fixtureInstance`, `operation`, `recorded:true`. This means native input was
recorded, including a failed creation attempt. It proves no ready scene, visible
marker, product feature effect, pointer release or cleanup. Missing hooks save
an unavailable/false receipt, never guessed actual objects.

The internal Phone `_emote_fixture_input` requires a held existing source lock,
existing pinned SDK session and callback that durably records the exact command
and candidate/process binding BEFORE private dispatch. Request copies prevent
callback mutation; current candidate/SDK/process checks run again before sending.
No session creation, launch or install is admitted. Input is absent from the
read-only command allowlist and from advertised feature capabilities. The full
caller still needs its own durable one-send state machine and cleanup owner.

## Separate original observation

Exact request: `{schemaVersion:1,commandId,action:"phone-emote-fixture-observe",
runId}`. No expected IDs/geometry/absence/phase is accepted. The probe forwards
original native data once to `phone-emote-fixture.json`. No current matching
native fixture means unavailable, including a never-prepared run.

Envelope is the original avatar-render schema: `schemaVersion:1`, `requestId`,
shared native process-birth `instance`, independent advancing `sequence`,
`processId`, `requestedEpochMs`, `capturedEpochMs`, `source`. Source is exactly
`phoneEmoteFixtureVersion:1`, `fixtureInstance`, `runId`, `phase`, `createdEpochMs`,
`originalInput`, `originalView`, `objects`, `entities`, `absentIds`,
`retainedObjects`. `phase` is native creating/active/failed/releasing/drained
metadata; active alone is not entity or pixel readiness.

`originalInput` preserves the exact original prepare command, without retiming.
`originalView` preserves actual setup `position`, `rotation`, `projection`,
`fieldOfViewDegrees`, `aspectRatio`, `nearClip`, `farClip`, `perspective`,
`feetPosition`, `modelScale`, `boomLength`, `mode`. The same original data/IDs/
recipe must survive every read and historical replay. No scope replacement or
revival after release/drainage is allowed.

`objects` is the original attempted role prefix backdrop/marker, at most two
`{role,id}` records. ID is actual UUID or null for failed add. Each current
`entities` row is exactly `id`, `role`, `originalObject`, `name`, `type`,
`parentId`, `hostType`, `position`, `rotation`, `dimensions`, `color`, `visible`,
`sourceUrl`, `locked`, `collisionless`, `canCastShadow`, `dpi`,
`lastEditedEpochUs`. Properties come from the actual object under one tree read
lock. `originalObject` compares that object against the original weak identity,
not its name/UUID alone. UUID replacements remain visible and fail readiness.
`absentIds` and current rows must account exactly for every actual original ID;
unknown/duplicate/missing/over-limit rows fail without truncation.

`ready(fixture,avatar)` is a separate pure historical join. It requires the same
native birth/PID, actual matching Selfie view/feet/scale, both actual original
local unparented unlocked objects and full expected geometry/properties derived
from original setup projection. Its host inverse-projection checks have an
independent simple-FOV test reference. It is not a pixel, unobstructed-avatar,
loaded-resource, HTTP-response, current-phase or product-effect verdict. The
parent must join the other original sources and actual current PNG challenge.

## Removal and lifetime

Release only accepts the exact original run/fixture instance. Under one EntityTree
write lock it checks the WHOLE original set for pointer identity, local host,
unlocked state, no parent, no children, and no clone origin/clones, before
using the underlying local `deleteEntitiesByPointer` path on that exact set.
The lock prevents same-UUID replacement races. It neither collects/deletes foreign
children nor mutates foreign clone links; refusal preserves responsibility.
Absent original nodes do not authorize deletion of replacements.

Read-only observation separately counts live original weak references, current
objects and actual absence. Only releasing plus no current nodes AND no retained
original object can become drained. An input receipt, stopped process, missing
UUID or changed name cannot supply those facts. `retired` validates complete
actual inventory and requires drained/no objects/no references. It proves only
this fixture's node lifetime: the parent must independently require the existing
native/Java Web runtime to have no owned surface, create/retry/DOM callbacks or
replies; preserve unrelated domain/world state; and retire every host/input/
source/image/actor scope. These remaining joins are not implemented by this source.

`NativePhoneEmoteFixture` reuses existing private read-only admission, bounded
51 reads/5 seconds, original 1.5-second freshness and monotonic final guard/copy
age floor. Historical replay is limited to 256 originals, without transport or
retiming; it cannot replace IDs/recipe/view or resurrect a drained fixture.
Fifteen common and four Phone host cases exercise real reader/probe/guard logic
against explicit synthetic boundaries. Their scope is test logic only.
