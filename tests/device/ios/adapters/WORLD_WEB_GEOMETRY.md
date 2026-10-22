# Passive Web Entity geometry and normal touch projection

`IOSWorldWebGeometryObservation` is compiled only with
`OVERTE_E2E_FEATURE_TESTS && Q_OS_IOS` and its native read bracket additionally
requires the actual `--testScript` launch. It reads actual EntityTree inventories
before and after the existing property getters and refuses any changed or
incomplete inventory. It retains no Entity or renderer ownership. The source
contains actual Web position/rotation/dimensions/registration point/DPI/input
mode/billboard mode/parent/visibility/lock/source URL/user data/edit time and
actual camera frustum/Qt dimensions. No requested UUID or position is accepted.

The closed command is `{schemaVersion:1,commandId,action,runId}`, with action
`feature-ios-world-web-geometry`; output file uses that action plus `.json`.
`Test.featureIOSWorldWebGeometry` must invoke the member's
`read(commandId,runId,actualEntityScriptingInterface)` on the native main thread.
`FeatureObservation.world_web_geometry(clock_source)` constructs
`IOSWorldWebGeometry` with the unchanged actual native clock. The output limit
is 262144 bytes. Registry contract: `ios-world-web-geometry`, writer/read 1.

`world_web_geometry.point` joins the actual complete tree to the original
Domain/world packet, actual owned Web UUID and WK source identity. Only an
unparented local non-billboard touch Web is supported. It projects the actual
fully visible DOM element centre through the actual registration point and
Entity plane, then the actual perspective camera and current native safe UI
viewport. Actual DPI/dimensions must agree with the actual current DOM viewport
using the existing renderer's 4096 surface/2048 WK caps. The current keyboard
may remain present if the measured target lies safely above its original inset;
occluded targets refuse input. This mathematical point proves no delivered input
or product effect. Whole ownership still needs actual Qt and native Web dispatch
originals plus independent subsequent state.

Four host tests exercise actual projection math and modeled native producers,
including changed registration, original keyboard occlusion, foreign/parented/
billboard/hidden/stale/mismatched sources and a closed read command. Native code
is source-only and uncompiled.

The native read is connected through the existing gated Test interface, secure
result-file allowlist, consumed-nonce probe ledger and closed fixture command
grammar. Host transport tests exercise the actual probe branches and existing
POST/AFC codecs, including unavailable nonce deduplication and rejected extra
input fields. The Work reader uses the same route with its independent original
VM event transcript; JavaScript never supplies native caller identity. Native
code remains uncompiled.
