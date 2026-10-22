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

PicoEmoteView v3 now journals the actual prior supported HMD mode and native
loaded Model/Geometry/Rig/pose before any mutation. It uses the original
controller tablet open, existing normal menu button, View pointer, Third Person
pointer ordinary original Home-ray return and tablet close. Restoration uses the same normal route and the actual
captured First Person or Third Person mode. A separately queried original
NativeAvatarRender cameraMode and original native checked QAction are required;
an input acknowledgement is never camera proof. Unsupported original modes,
unloaded avatars and a pre-existing open tablet fail before mutation.

Each of the twelve bounded setup/restore steps reserves a private record, then
retains the actual original token/menu/native phase before one input. Lost
controller/pointer results are re-observed after cold reconstruction without
another input. A missing effect retains the unresolved step; original setup
must be resolved before restoration. A reserved step without a known completed
intent cannot be replayed. Original fixture tickets, candidate/PID/bridge,
native cursors, original model identity and pose, monotonic/native/host clocks
and the 1.5s freshness budget remain bound through final delivery. Changed
fixtures or slow final copies cannot retime an original. The whole operation
stays within the existing 60s outer bound and each effect wait within5s.

The owner keeps its journal even after mode restoration. Closing the tablet
and unchanged camera state do not prove actual menu timer/context retirement.
Base cleanup independently refuses an unresolved view journal after stopping
the app. Thirteen explicit source/input/clock boundary cases cover the positive
normal route and ignored/lost/foreign/stale/cold recovery cases; two actual Pico
factory/teardown cases check the existing parent lock and candidate association.

The design was selected after inspecting only the fixed committed Phone
overte_phone_emote_view.py at abb7f6b60d97daf17752aadf94e2b5df099bb7ba
(SHA256 `5a6544d49e7068eddb34e426eae24622bb33bfd293571bbcf71632de3c1df531`).
The original durable reserve/observe/restore pattern is reused. All normal HMD
inputs and mode guards are Pico-specific; no Phone preferences, pinch gesture,
camera setters or mono evidence were copied. No reference tree was changed.

Next: join the setup owner to fresh model-specific original stereo pixels and
prove original Qt/menu timer/callback retirement. Original
avatar body bounds must actually project in both eyes; no fabricated ROI or
camera result is accepted. Controlled scene/avatar identity, independent actor
and whole Emote cleanup remain required before a complete capability.

The Pico catalog keeps emote-original-sources (81 cases),
emote-stereo-capture (75 cases) and emote-background-effects (11 cases)
separate, preserving every case under the existing default per-group timeout.
The native menu check is emote-view-native-ui. These selector counts are test
groups, not completed feature areas; no adapter operation budget was enlarged.


The actual menu label Third Person selects CAMERA_MODE_LOOK_AT, whose original
modeToString is "look at". The older "third person" name selects a different
legacy enum and is not an admitted original normal-menu mode. An initial local
owner/host fixture incorrectly used that legacy name; v2 rejects v1 journals
without rewriting or adopting them. The actual original cameraMenuChanged,
Camera enum/getMode/setMode/getModeString/modeToString and original Avatar zoom
constants now execute behind the original QML/QAction path in the native test.
The exact normal mode and boom changes are asserted independently of labels.

The optional native cameraStateVersion1 extension observes actual HMD mode and
original Avatar boom length/minimum/default without setters. V3 requires it.
A pre-existing first-person profile with a custom boom fails before input,
because normal first-person restoration would reset it. A pre-existing look-at
profile retains its exact original boom. Subsequent foreign boom changes stop
input, and actual mode transitions require their original expected native boom
effect. A restored mode alone cannot qualify restored view parameters. Old
Avatar v1 packets remain readable by existing clients without supplying this
missing observation. Full camera pose/render/Qt retirement remains separate.


V3 composes the existing actual PicoTabletHome input before both physical
tablet closes. Initial closed Home must be independently measured; an existing
hidden foreign app/menu is refused. Actual TabletProxy onHomeScreen reflects
State::Home; gotoMenuScreen changes it to State::Menu. Hiding a tablet is not
that state transition. The existing Home geometry source and normal calibrated
controller ray perform the transition, with its original packet and input
reservation persisted before the gesture. Original tablet/Home entity births,
new query nonces/cursors, PID and all clocks stay bound. The following closed
observation must still be original Home. Lost Home replies are only re-observed,
and ignored Home gestures cannot authorize close or another gesture.

The earlier host fixture incorrectly treated every physical tablet open as a
Home reset. It now retains the original underlying menu across close/open,
matching the product lifetime boundary. V1/v2 view owners remain retained and
are not relabeled with missing Home originals. Restored mode/boom/Home remains
an intermediate proof; original menu Timer/QQmlContext retirement and original
OpenXR controller stream retirement must still be joined by the full parent.


Original menu lifetime observation is now wired into NavigationUi as the
optional picoViewMenuLifetimeVersion1/picoViewMenuLifetimes extension. A
canonical actual nested TabletMenuStack source context must bind both original
root and StackView d; the root's outer TabletMenu creation context alone is
insufficient. Weak original page/stack/delay Timer/component and Timer contexts
are retained, with native running/pending-menu-item state. Hidden/detached pages
and invalid-but-alive contexts remain alive. Thirty-two original scopes and
4096 visual nodes are hard bounds; no getters mutate or destroy a product object.

The strict shared navigation reader validates the optional extension. The view
owner preserves it in every original frame and enforces append-only original
identities, births, clocks and irreversible actual object death. Its separate
menu_retirement method requires an original preinput inventory and fresh known
owned-object death after restoration. It keeps all journals, and cannot replace
full controller/callback/native resource retirement or the common quiet window.
Old view histories without that original inventory cannot use this method.

The owning native menu harness uses the actual original deferred Timer. An
observer of its actual runningChanged signal captures its real pending item
before the zero-delay callback; sampling after mouse dispatch can already be
too late. It also proves stopped/hidden/detached is not destroyed. The exact
original C++ empty/live/after-page-death packets are passed through the Python
reader. Any alive Timer/context remains unretired; the harness does not delete
internal contexts. Whole application and real Home-loader destruction remain
unqualified. The existing emote-view-native-ui selector owns this compilation.


## Original Emote controller streams and neutralization

PicoEmoteView v4 retains the exact original OpenXR envelopes for all six
setup/restoration controller gestures: normal tablet open, calibrated Home ray
and normal tablet close. The canonical existing PicoOpenXrAdapterSession is
reused with the same tablet hold and original Home geometry; normal Qt/menu
pointer actions remain on the original route. Each envelope is CAS-written
before transport while the original session sequence is locked. That callback
performs only host validation and storage; no session, guard or ADB reentry.
Host/native/phase freshness includes the complete original durable write.

Each controller step requires separate original same-process/session/sequence
neutral status before its independently measured GUI/camera/Home effect can
complete. Unknown grant/ACK/neutral delivery is read-only reconciled, never
resent. A pretransport lost durable response retains its envelope without
inventing native consumption. The separate controller_retirement read requires
all six originals plus fresh final owned-stream neutralization and restored
mode/boom/closed Home. It preserves every journal and does not qualify menu
contexts, other resources, common quiet windows or the complete Emote flow.
V1/v2/v3 view owners remain retained and cannot invent these missing originals.

Actual session/grant persistence is exercised with explicit synthetic native
transport/HMD boundaries. Physical controller, OpenXR and application/device
qualification remain absent; no complete feature capability is enabled.


## Actual bundled avatar identity during normal Emote view setup

The optional native-avatar-resources v1 extension of existing AvatarRender v1
records exact original configured skeleton and loaded HFM URL digests. Only the
known immutable qrc defaultAvatar_full.fst/mannequin.fbx may be read, bounded to
4MiB each; no URL is fetched or avatar loaded. Original qrc bytes, size and digest
are independently joined to the loaded Model/Geometry/Rig and existing pinned
repository resources. Unavailable/foreign resources remain measurable without
being admitted as controlled. Old AvatarRender packets remain readable.

PicoEmoteView.controlled() composes this admission before the first normal
controller input and on each original preparation/restoration observation.
All retained historical originals must already contain the real resource proof;
an older view journal cannot invent it from a newer query. The normal v4 partial
route remains available without claiming a controlled-avatar setup. Optional
resource identity, once present, cannot change or disappear inside that route.
No preference, avatar resource, pose or texture is set by this observer. This
does not qualify actual GPU materials, complete stereo scene, actor or whole
Emotes. All resource/model/render seams remain explicit in the native harness.

The immutable resource helper is selected from the fixed Phone commit
abb7f6b60d97daf17752aadf94e2b5df099bb7ba (PhoneAvatarConfiguration.h source
SHA2566dd05f674dac52f2d46f84011bd14084a29171ffb84c8ce7eba5dabfa4afc56a).
The shared helper removes the Phone-only compile gate and uses neutral names.
Phone pinch/Touch/selfie/scene behavior is excluded. The original full getter
compiles with actual Qt qrc registration of both original repository files;
its actual C++ packet passes the strict Python reader and pinned-byte join.

## Final menu publication fence

`PicoEmoteView` binds one retained callback to the shared original QML transport
for each normal menu pointer. The final actual command must match the durable
original control/token, bridge, generation and sequence. Its final fixture
prefix and original avatar/UI/Home ages are checked after navigation guards,
without another source guard after that phase check. A boundary phase or age
change refuses publication while preserving the pending original intent. The
separate canonical controller callback remains private host IO only.

## Actual controller publication admission

The normal Emote controller operations now pass a pure host `before_publish`
validator to the original canonical Session/Android transport. It compares the
already durable exact envelope and original host journals, then checks the saved
native/host anchor age after the original SDK guards and again before native
grant commit. It performs no second intent CAS, phase/native/SDK query, guard
or session reentry. Late SDK work cannot publish an expired input. An uncertain
original remains owned without resend. View's ordinary Home-ray uses the same
optional forwarding; the default shared Home/controller paths are preserved.
Five focused owner checks pass3.992s, including late transport refusal under a
frozen native clock, host-only callbacks, ordinary open/play/cancel/close and
all six setup/restoration streams with independent neutralization. Synthetic
transport boundaries remain explicit; original SDK serialization/publication
checks are separately covered by the real transport's device-free tests.


## Original Pico local render gate

`controlled()` now refuses setup before its first normal input when the
original AvatarRender source reports `localRenderingEnabled:false`. That gate
is independent of Third Person; changing the camera cannot enable it. Every
subsequent controlled setup read checks the same actual flag. Historical setup
with a disabled original cannot become eligible through later reconstruction.
Original normal View restoration remains allowed when the current gate is
disabled; cleanup neither changes it nor claims rendered avatar pixels.

The source audit found that `AvatarManager::init` disables shouldRenderLocally
under Q_OS_ANDROID, and `scripts/+android_picoInterface/defaultScripts.js` also
sets it false. `MyAvatar::render` returns before Avatar::render while that flag
is false. The reviewed Menu camera and MeshVisible paths do not assign the
separate flag. No ordinary enabling path was found in the reviewed sources.
Therefore the existing self-avatar stereo lane is presently unavailable for
normal Pico startup. Native Rig progress and remote joint traffic do not
establish local avatar pixels. Product changes and a test-only visibility
setter are outside this task. A future independent remote-avatar stereo lane
would need its own actual model/Rig/network/source binding and camera evidence;
the local-avatar getter cannot simply be relabeled as that lane.

Three focused View tests pass (1.473s), including refusal without input and
restoration preserving an actual disabled gate. The pre-existing original
hidden-avatar compiler harness also passes with Qt5: 33 cases, including all
16 hidden cases with zero local draws and the hide/show/hide case. It compiles
original simulation/render/override bodies using explicit model/Rig/network
endpoint seams, not a full application or GPU/device. Full Emotes stay partial.
