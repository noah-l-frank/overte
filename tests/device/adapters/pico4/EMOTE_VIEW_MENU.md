# Original normal Pico VR View-menu input

Feature 5/14 remains partial. The normal View menu supplies First Person and
Third Person actions in the actual Menu.cpp camera QAction group. In HMD mode,
Application_Plugins.cpp hides Selfie; Application_Camera.cpp still implements
the ordinary third-person HMD boom path. The adapter must use that actual menu
path and independent original camera/model observations. Phone camera buttons,
arbitrary Camera setters and mono/selfie evidence are not reused.

NormalViewMenuControls v1 identifies the real TabletMenuItem delegates against
the actual native View/FirstPersonLookAt/LookAtCamera actions. VrMenu's original
MenuUserData QObject association must be the same original object on both the
QML source and QAction, with the same pointer metatype. A copied label or checked
bit cannot bind another native action. Original QML source UUID, native checked
state, enabled/visible/platform state and exclusive native group are retained.
This path requires the actual HMD context and existing --testScript gate.

The separately gated Pico NavigationUi extension publishes viewMenuControlsVersion
v1 and exactly view-menu.view, view-menu.first and view-menu.third. Its existing
source-token/cursor handling stays unchanged. The source string includes actual
native menu UUID and checked/readiness facts, so original source changes replace
the token. The actual new apply branch permits only a normal pointer activation
on the original visible unoccluded delegate. It calls no QAction, Camera or QML
handler directly. The original deferred TabletMenuStack timer and VrMenu action
bridge perform the ordinary product dispatch.

PicoViewMenu reuses PicoScriptIO/PicoNavigation and the existing candidate-bound
VR transport. Every call compares the original bridge/generation/process/cursor,
token, native menu identity and checked state; it calls the supplied durable
parent intent writer before one pointer. Reading/waiting never retries input.
The internal factory supplies the actual original runtime and its clocks. This
helper has no independent journal or recovery authority: its whole parent must
retain the input reservation, then reconcile only original observations after
uncertain delivery. Returned acknowledgement and native checked bits are not
camera, avatar, stereo, pixel or Emote effect verdicts.

The optional extension remains compatible with old snapshots. Closed host
validation rejects coerced versions, unexpected fields, foreign menu identities,
stale token/generation/cursor, unavailable controls and unsupported Selfie IDs.
Eight source/reference counterexamples and the actual Pico factory case cover
intent-before-dispatch, failed storage, lost delivery without automatic replay,
original checked state and changed installed candidate.

The native test compiles the complete original MenuUserData declaration and
method bodies, unchanged bindActionToQmlAction and the actual new Pico apply
branch. Actual TabletMenu.qml/Stack/View/Item, WrappedMenu/MenuItem, native
QActionGroup, QTimer and Qt mouse events execute under real Qt5 and Qt6. Normal
View then Third Person and First Person pointer inputs reach the original
deferred bridge and independently advance the real exclusive QAction states.
Foreign original association, disabled/hidden actions, wrong checked source,
nonexclusive group, non-HMD context and unsupported input do not dispatch.

Host window, native action registry/HMD context, sound service and pointer
callback hosting are explicit seams. Camera application slot, actual HMD,
OpenXR rendering, full Pico translation units and application build are not
qualified by this harness. The existing original surface pointer route has its
separate compiled checks. Qt source fixtures wait for real menu transition/frame
settling; they do not bypass input by invoking selection handlers.

Next: the whole durable setup/restore owner must capture the actual prior mode,
open/leave the normal menu/tablet, join fresh NativeAvatarRender and model-specific
stereo pixels, and prove original Qt/menu timer/callback retirement. Original
avatar body bounds must actually project in both eyes; no fabricated ROI or
camera result is accepted. Controlled scene/avatar identity, independent actor
and whole Emote cleanup remain required before a complete capability.

The Pico catalog keeps emote-original-sources (81 cases),
emote-stereo-capture (54 cases) and emote-background-effects (11 cases)
separate, preserving every case under the existing default per-group timeout.
The native menu check is emote-view-native-ui. These selector counts are test
groups, not completed feature areas; no adapter operation budget was enlarged.
