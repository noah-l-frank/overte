# Local build and integration continuation, 2026-10-22

The user explicitly authorized local builds, superseding the initial session
compiler/build prohibition. No device access, installation/dependency changes,
Jenkins runs, product functional changes or remote writes were performed.
The reviewed Pico doctor found the existing SDK36, NDK27, CMake, JDK21, Conan,
compiler and Gradle wrapper. This is tool availability, not an APK qualification.

## Executed native and production-surface checks

The real Qt5 tablet harness compiles the actual NavigationUi and NativeFieldInput
sources plus extracted original VR surface pointer bodies with Qt5 5.15.18 and
the existing read-only GLM headers. Both native programs pass: Navigation 31
internal checks; Snapshot 41 checks and ten ordinary pointers. Surface/window
service boundaries are explicit host fixtures; no application capture, Android
runtime, headset or stereo acceptance is implied. The first real compilation
exposed an omitted dependency: the harness selected `sendPointerClick` without
its actual `sendPointerAt` body. Including both original bodies fixes the
harness without changing product code.

The unchanged production `PhoneEmote.qml`, which the actual Pico bootstrap uses
through its separately loaded Emote engine, passes five real Qt5 QML checks
(including setup/teardown). The exact observed ten-button click trace then enters
the unchanged production JavaScript: all 29 Node cases pass. Actual animation
cache, avatar and timers remain explicit seams. The normal V8 native-call
harness also compiles the original method-dispatch body and passes all seven
execution modes with real V8/Qt meta dispatch; its single owning test passes.
This last harness uses the normal non-E2E dispatch build and does not compile
or qualify the new E2E caller instrumentation or the full ScriptManager.

The initial Qt5 invocation used a no-longer-existing historical GLM path. After
locating the existing actual headers, a separate attempt hit the workstation
`/tmp` quota and the missing pointer dependency above. Original sources were
preserved. Successful native runs use this session's own private 0700 build temp
area on `/home`; no shared cache, reference files or global storage were changed.
Original logs and source/action identities are retained privately.

## Parallel feature integration

Reviewed local selections are integrated only on the isolated Pico branch:

- Audio `8252deb881` -> `c7356df824`: immutable actual PCM/event history and
  genuine complete phase/draining requirements.
- Audio `1b121403d7` -> `55776065c6`: Status and PCM taps share the actual
  original Start instant. The real observer header compiles and executes with
  Qt6 Core and an explicit audio-format seam; AudioClient/QtMultimedia and
  actual acoustic playback remain unqualified.
- Chat `9ab61ccda3` -> `209076f762`: original Pico entity-keyboard inventory,
  ChatView v2 with legacy reads, candidate-bound VR source and counterexamples.
- Create `b9b2c3d312` -> `81aa42ffd9`: existing opt-in normal create-management
  routing, actual Home ray, independent entity observation and owned cleanup.

The combined 94-case component selection passes. The existing Pico groups
`normal-create`, `normal-chat`, `script-feature-engine`, `suite-runner` and
`coverage-matrix` all pass (5/52 selected groups, 138.68 seconds). The unchanged
complete Script engine remains exercised; no full catalog result is claimed.
Create, Audio and Chat agents continue their own remaining whole-feature work.
Only Scripts, Authentication and Graphics currently have complete source/host
feature triples. Application native compilation, a complete Pico APK and all
physical/device qualification remain unverified.

## Original Chat Erase digest

The selected original native history digest compiles and passes with real Qt5
models (one test, 1.084 seconds). Its page/model association is an explicit host
seam; the whole application is uncompiled. The combined 57 Chat component cases
pass, and `normal-chat`, `suite-runner`, `coverage-matrix` pass (3/53 catalog
groups, 28.48 seconds). Erase uses original version-2 controls and full ordered
row hashes, not row counts. These checks do not qualify independent whole-run
authorization, durable profile restoration, peer stimulus or complete Chat.

## Passive original animation registry

The actual registry observation method passes a Qt5 compile/execution test
(1 test, 1.745 seconds) with real weak maps and locks. Resource loading and
Animation row values remain explicit seams; full AnimationCache/application
compilation is unverified. The compile found and fixed a selected E2E counter
name colliding with Qt's `slots` macro. The complete 117-case Emote component
selection passes; `feature-observation`, `suite-runner`, `coverage-matrix` pass
(3/53 groups, 29.41 seconds). Standalone catalog execution also exposed a test
helper import that had been masked by a broader PYTHONPATH; fixed package/lazy
imports preserve the same tests. Full whole-feature/device qualification is open.

## Actual Pico Emote pointer route and Lifecycle source

The original Emote helper, visual ownership, actual native input branch and
extracted production surface/PointerEvent bodies compile and execute with real
Qt5: ten actual Button messages and two delivered Scroll events (1 test,
3.746 seconds). Explicit hosting seams remain. The shrunken window's original
contentY stays zero after Down: event delivery is explicitly not scrolling
qualification. Source-token geometry changes and a foreign higher-z overlay
are tested. The 88-case affected component selection and six actual Pico
wrapper cases pass; shared version-1 controls remain readable.

The integrated original Lifecycle source initially segfaulted in its native
harness. That cause was not conclusively reproduced. The harness no longer
manually destroys Qt-internal QML contexts or their engine before live pages.
The corrected real Qt5 run exits zero; context-only weak lifetime now uses
explicit application-owned objects. Original hidden/detached QML and surviving
context wrappers remain retained. The shared 93-case Lifecycle/Chat/Emote
selection passes. These narrow checks do not qualify complete Lifecycle,
whole original QML retirement or a native application/device.

## Private feature result admission

The entire original Test saveObject body compiles and executes with real Qt5
filesystem operations (1 test, 1.127 seconds). GPU receipt types are explicit
compile-only seams. New closed feature-result names now automatically enter
the existing private mode0600 writer; invalid names and links are refused,
without --testScript no private result appears, and ordinary result handling
is preserved. This closes the repeated omission found during parallel source
review; it is not full TSI/application compilation. See
[the private writer contract](../../native/PRIVATE_FEATURE_RESULTS.md).

## Integrated original Chat mixer and Lifecycle draft controls

Local commits c2a0d36181, 111db72ebc and 0d5f74d4de compose the original
fixture mixer with both native role journals and separate recovery when a
native journal is interrupted. The 24 affected mixer/transition/recovery
counterexamples pass (25.454 seconds). Recovery retains native journals and
reports unresolved native Chat; restoring a fixture process is not Chat cleanup.

Commit d984716b62 adds actual normal Create draft pointer/IME controls and
weak original field/page/context/window identities. The focused Qt5 test
compiles the original NativeFieldInput implementation and loads the actual
NativeCreate.qml; it passes both runtime-gated invocations. The full Pico
navigation translation unit remains uncompiled. Additive integration preserves
Emote version 2, Chat version 2 and original Create picker controls.

The combined 6/63 catalog selection passed coverage-matrix (0.061s),
lifecycle-input-owner (44.830s), create-file-ui (90.437s), normal-chat (38.903s)
and normal-emote (48.503s). The broad normal-scripts group reached its outer
150-second process limit; it is not reported as passing. This expanded factory
suite needs a larger outer execution budget or a targeted continuation; its
individual freshness and quiet-window limits are unchanged. Four project
checks pass (documentation, documentation-contracts, source-layout and
project-coverage; 5.04 seconds). No complete additional feature or device
qualification is claimed.

## Original loaded-avatar source and expanded factory regression

The shared original loaded-avatar getter and model/geometry/Rig identity
fragments compile and execute with Qt5 5.15.18 (1 case, 1.676s) and Qt6 6.11.2
(1 case, 2.158s). Actual cross-thread Qt delivery and runtime gates are covered;
AvatarManager, loaded model/geometry, Rig and camera implementations remain
explicit seams. Full original translation units and all GPU/device behavior
remain unqualified. See [the original source](EMOTE_AVATAR_SOURCE.md).

The actual Pico candidate-bound factory passes (1 case, 2.498s). All four
selected catalog groups pass (4/63, 670.11s): normal-scripts 89 cases/492.950s,
normal-emote 15/51.061s, emote-original-sources 107/126.032s and coverage-matrix
6/.061s. A 600-second outer process limit resolves the earlier broad Scripts
150-second timeout; semantic operation and freshness limits were not changed.
The subsequently added final post-copy candidate-loss/native-clock guard has
16 original reader/probe/fixture cases passing (.166s), including a countercase
that fails without that guard. Four final project checks pass (12.24s). No additional
whole-feature capability or application/APK/device qualification is claimed.

## Shared native-branch integration and normal input checks

Chat commits bd3becac18/e79fdee648/3abd9ac8fc and Lifecycle
b239273d85/846853d65b pass 108 affected component cases (89.386s),
four actual Pico Chat factory/recovery/teardown cases (13.144s) and one actual
Pico editor factory case (.829s). The normal editor's generation follows its
original current context, including when unfocused; final native clocks cover
result construction. Whole Chat/Lifecycle capabilities remain unavailable.

The actual Qt5 Emote pointer/scroll harness initially failed compilation after
Lifecycle was added between the Emote and Chat branches. Its extraction had
incorrectly used the following Chat branch as a delimiter. Extracting the
Emote branch by its own original braces fixes this harness without changing
native input behavior. The repeated actual Qt5 run passes (1 case, 4.056s),
including the ten-button trace and delivered Scroll events. Actual contentY
stays zero; this still does not qualify a real scroll effect or a device.

## Integrated physical Create and actual JSON Chat settings

Create 1488d98770/c0670a97c4/9c352313b6 preserves the existing Chat barrier,
worker and all Emote/Audio coverage mappings. The catalog is 65 after exactly
two added Create selectors. All six selected groups pass (6/65, 107.95s):
create-browse-setting 2.103s, its actual Qt5 native test 9.938s,
create-picker-owner 85.487s, create-entities-native 1.772s,
create-dialog-native 8.578s and coverage-matrix .073s. The real original
Manager/writer/Handle/JSON helpers and private physical INI/JSON acquisitions
are exercised. Blocked/late/dead workers stay unresolved; a final memory
value alone cannot establish persisted restoration. The actual non-string
Browse/Cancel failure remains retained; no functional product fix was made.
A further pre-restore physical ownership fence is under review, so this record
is not whole Create cleanup qualification.

Chat 0aa3a88c5d corrects the physical reader for the actual registered JSON
format and fences conditional restoration against a fresh original worker/file
snapshot. All six focused Qt5 cases pass (40.288s), compiling the entire actual
SettingManager.cpp with MOC, SettingHelpers.cpp and SharedLogging.cpp. Both
INI/JSON, raw empty types, parser aliases, original queue fences and physical
cache/file disagreement are covered. These original source checks do not
qualify the whole application, complete Chat or any device. Four project
checks pass (4.47s). Lifecycle 9abd6fccb9 adds the next ordinary Chat draft
component. Its 11 post-integration component cases pass (17.611s), and the
actual Pico factory/source-lock case passes (1.578s). All four final project
checks pass (4.52s). These are component checks; Lifecycle remains partial.


## Original per-draw stereo camera acquisition

The additive E2E backend API reads only the immediately preceding indexed draw
from its original working Batch, command index, executing backend and observed
stereo frame/execution. Its actual two camera bindings become readable after
that original draw call returns. The batch sequence is allocated when execution
begins, so per-draw and completed-batch rows share that original identity.
Missing eyes and changed original bytes in an aggregated camera slot fail closed.

The focused native test compiles complete original GLBackend::renderPassDraw,
GLESBackend::do_drawIndexed, setupStereoSide, camera acquisition/getter functions,
and original initialization/finalization fragments with real Qt/GLM. Both doubled
and instanced builds pass on Qt5 (2.793s) and Qt6 (3.382s). Batch/transform storage
and GL calls/context/query results are explicit seams; no GL context, full GPU
translation unit, application, image, OpenXR or device qualification is claimed.
Twenty-two existing stereo camera/trace/acquisition cases also pass (.044s).
The first harness compile failed because its placeholder replaced NUM_COMMANDS;
the corrected whole placeholder preserves the original enum and functions.
Model payload, submitted capture transport and host stereo model validation are
still pending, and Emotes remains partial.

Create c92ac6ba9b passes the twelve host cases (3.587s) and original native
INI/JSON case (9.455s). The first native invocation omitted the already available
GLM include and failed compilation; the repeated invocation supplied that explicit
existing path, without installation or product changes.


## Integrated bounded original Chat chunks and exact native types

b78264ceca compares the original cache/worker/file snapshot through exact
QDataStream bytes before conditional restoration. The original worker-only
Int-to-Double change with identical physical JSON tokens cannot borrow Qt's
conversion equality. All six original Qt5 Manager/worker/physical/profile cases
pass (39.791s) after integration, retaining the actual full Manager/MOC/helpers.
48f838a55c retains complete numbered original bundles and root SHA manifests
under the existing 512-frame/16MiB bounds, without truncation or old-journal
migration. All 24 focused sample/chunk cases pass (26.812s), including 355
original frames each with 256 changing joint poses, full query-free historical
reconstruction and late native-guard file mutation. Both components remain
partial Chat support; no whole-flow/device qualification is added.


## Original loaded model, used stereo cameras and submitted image

The expanded actual native harness passes on Qt5 (5.205s) and Qt6 (7.126s),
each compiling both doubled and instanced configurations. It now includes
entire original FeatureRenderTrace/FeatureWorldRender classes, the full original
TSI model getter, actual mesh metadata/render fragments and drawCall, plus the
original GLBackend/GLES functions. Qt PNG/QtCore/GLM are real. GL, Batch/transform,
loaded-geometry and surrounding application/context services are explicit seams.
No full native TU, real GPU/OpenXR, application/APK or device result is claimed.
Qt6 reports the existing storage QVariant::type deprecation; no check is skipped.

Thirty model/stereo source counterexamples pass (.153s), including both own eyes,
aggregate draw limits, foreign model/geometry/Rig/pose/view, mono rejection,
image/submission identity, missing native method, ignored query and a final
native-clock/candidate loss. The actual Pico factory passes (.599s). Its first
fixture used fixed epoch20000 against the real simulated candidate clock and
correctly failed freshness; the producer now constructs its synthetic original
capture at the candidate's clock. No acquired production evidence is retimed.
Current challenge pixels/independent actor and whole Emote cleanup remain open.

The three final Pico groups pass (3/65, 94.98s): coverage-matrix .061s,
normal-emote 34.414s and emote-original-sources 60.508s. All four final project
checks pass (3.65s); contract registry, Node probe syntax and whitespace pass.


## Integrated consumed peer continuation and native background history

8fb38cccbe and 5db4f50c4f allow only fully consumed/received original peer input
and delivery histories to reconstruct between RPCs. Complete original receipt
bytes, native owner/process/file identities and both independent original source
histories remain bound to each input. Uncertain/old journals remain retained;
input is never replayed. 9343feb3b4 adds the bounded original Qt/Chat/VR-keyboard
background history without weakening foreground guards or supplying OS input.

All 38 affected peer-input/send/distance/background cases pass (39.378s).
An earlier combined command named a nonexistent test_chat_distant module;
its 33 loaded cases passed, the selector error was preserved, and the corrected
whole selection above is green. The actual Qt5 Chat QML/native IME/history check
and original bridge-body compilation pass; OS/VR/service boundaries remain
explicit seams. Both integrated actual factory/parent-lock cases pass (2.348s).
All four project checks pass (3.17s), and registry/Node/whitespace checks pass.
Whole Chat and Lifecycle remain partial; no source/journal retirement or device
qualification is inferred from these components.


## Original per-eye Emote body and challenge measurements

Ten new stereo pixel cases and eight model provenance cases pass (18/18,
4.065s). Each eye decodes the current challenge and independently measures
original projected body versus quiet control pixels, retaining actual used-camera
changes. Both eyes must pass. Native source times, original PNG/pixel hashes,
loaded geometry/Rig and actual frame/submission cursors remain required.
A synthetic fixture initially put its subject top at15 while the actual
projection began at13; the check correctly refused it. Its producer policy and
painted body were corrected to cover the actual original projection. No
production bound or threshold was relaxed. Freshness tests include native time
advancing behind a frozen host and repeated PNG decode cost behind a frozen
native clock. Source logic only; scene/view setup, durable whole capture flow,
independent effects/actor and complete Emote retirement remain unfinished.

The final expanded Pico source group and coverage checks pass (2/65, 70.20s):
emote-original-sources 70.125s and coverage-matrix .080s. The source group now
contains 126 cases. All four project checks pass (3.32s); registry/whitespace
checks pass. No native files changed in this pixel-only packet.


## Original OS/native background evidence join

71634f8b5a and 1ffc7bb0ab join original process/foreground facts, native lifecycle
counts and actual Hidden/Suspended-to-Active Qt/editor/keyboard history. Root
review removed an unsupported fixed generation2 result: this component has no
preceding Create/X archive, so it reports no generation; the whole parent must
independently derive it. All 22 source/evidence cases pass (.127s), and all four
project checks pass (2.94s). This pure original join sends no OS input and proves
no current three-second quiet, source retirement or whole Lifecycle completion.


## Durable indexed Emote image ownership

PicoEmoteCapture v1 now binds exact parent source/phase/Rig, the original model's
executed stereo cameras and unchanged PNG, private inode-bound storage, and
independent native memory/callback/receipt-file retirement. Lost acquisition,
model, release and journal responses never authorize another acquisition.
Original historical replay retains source times after parent advancement.
Ten owner cases and ten existing pixel cases pass (20/20, 7.061s); two actual
Pico lock/candidate/foreign-owner/orphan-teardown cases pass (2.349s).
The first owner tests exposed a missing exclusive image directory and a synthetic
model producer bound to a different GPU frame; both were corrected. An initial
partial-write fixture failed before reserving a file, so its interruption was
moved to actual post-write verification. One factory test expected the wrong
exception type; its explicit Pico binding rejection is now covered. No production
validation threshold was relaxed.

All three final Pico groups pass (3/65, 120.74s): normal-emote36.659s,
emote-original-sources84.021s and coverage-matrix .060s. All four project checks
pass (3.36s); registry and whitespace pass. These are host/synthetic source tests;
no native sources changed, application build or devices were qualified. Normal
VR scene/avatar/view setup, joined effects/independent actor and complete Emote
resource/journal retirement remain open; no whole Emote capability is advertised.


## Integrated domain Model, independent Chat and Lifecycle owners

12a532a1ab integrates46707ea1e1 without the already present ScriptWork support
commit; all newer Chat/Emote/native declarations, safeguards and catalog entries
remain. An initial conflict-resolution script accidentally truncated six files;
the changed statistics/JSON check exposed it. The affected files were rebuilt
from8829794867 with exact selected additions, the local integration commit was
corrected, and JSON/AST/version/coverage checks passed before further work.
The final difference is the original25-file1191-addition/43-removal packet.
No reference or foreign worktree was changed.

e3d78288ef and846519f5a4 integrate original Chat HOME/Return and a third independent
witness source journal, closed original input admission and non-replayed publisher
intent. All28 selected component/actualPico factory/teardown cases pass29.257s.
Chat background v1 is intermediate; reviewed post-release quiet v2 follows.
a7a3779ff5 integrates339b8d501d with the existing lossless source container,
original hidden Qt checkpoints and3s quiet before/after actual timer release.
All seven integrated Pico groups pass191.78s (7/68): Lifecycle input49.594s,
Lifecycle background68.429s, Model owner24.396s, actual Model Qt5 UI5.168s,
picker42.156s, actual entity source/weak lifetime Qt5 native1.975s, coverage.057s.
Native services/entity tree/VM/renderer remain explicit harness seams; this is
not a full native translation-unit/application or device qualification.

A further Emote review found cold cleanup incorrectly requiring the original
parent source to remain its latest header. It now retains and validates the
original ready source prefix while binding current parent CAS independently.
Cleanup works after parent advancement or interruption, without another acquire;
historical source contexts cannot provide live authority. All12 owner cases
pass5.698s, including the new lost-acquire/advanced/interrupted-parent cases.


## Post-release Chat quiet and orphan Lifecycle originals

f55d9c32d5 integrates6455991a62, replacing intermediate Chat background v1 by
strict v2/reads[2]. A full3s independently advancing original window follows
actual native timer release, including delayed keyboard/chat counterexamples.
Recovery holds both exact source locks and does not overwrite unknown persisted
parent input phases after a lost write response. The old journal is retained.
Base Lifecycle cleanup now independently refuses orphan background original roots
and numbered children, including when the owner journal is absent. Both new
actual Pico teardown cases plus all28 current Chat background/witness cases pass
(30/30,46.621s). No native source, device or physical publisher process runs in
this selected host check. Whole Chat/Lifecycle and the total3/14 source-complete
count remain unchanged.


## Actual unclipped Qt hit order and normal Pico View menu

5c1beab00b anddd1564c04c integrate3f459cbc79/4a6543a26f while preserving the
newer Lifecycle/Chat/Emote surfaces. Original Qt software-rendered pixels and
the same actual QObject trees verify negative-z parent occlusion, higher foreign
children outside non-clipping parents, real clips and hidden/disabled overlays.
The actual NativeCreate Properties filter/textures/ApplyTyped input and two
private-header mutants pass; final Qt5 selector17.511s plus coverage.067s
(2/68,17.58s). Original Emote pointer/Scroll4.045s, actual Lifecycle field/IME/
Unicode program and7 actual Chat QML checks also pass. No product UI was changed.

The new gated normal View-menu path binds original VrMenu MenuUserData/QAction
identity, exclusive native group and actual QML checked/visibility/platform
facts. Only normal original pointer activation is dispatched. The complete
original native MenuUserData bodies, bindActionToQmlAction and new Pico apply
branch execute with actual TabletMenu/Stack/View/Item and WrappedMenu/MenuItem
under Qt5 andQt6. Original exclusive QAction toggles follow deferred actual QML
input. The host window/HMD/action registry/sound/pointer-callback boundaries are
explicit; the camera application slot, whole translation unit, app and HMD are
not qualified. No camera setter or selected expected camera state is returned.
Qt5 native selector9.369s plus coverage.080s pass (2/69,9.45s); Qt6 native owning
case passes13.422s. Initial native fixtures searched QObject ancestry rather than
actual visual children, then clicked before the menu transition settled; visual
traversal and real event/frame settling corrected the host fixture, without
invoking product input handlers. Eight host original-reference cases and one
actual Pico candidate/token/input factory case are covered by final groups.

The final expanded source/normal groups pass (3/69,176.91s), but the old single
source group needed135.836s under parallel load. Its146 existing cases were then
split without loss into original sources/Rig81, stereo54 and background11. The
new final four-group selection passes with the unchanged default timeout
(4/71,74.09s): source46.164s, stereo8.881s, background18.975s, coverage.070s.
Normal Emote separately passes40.996s. No native observation/input/quiet timeout
was enlarged. All four final project checks pass2.92s; registry and whitespace
pass. Source completeness remains3/14; durable view setup/restore, controlled
scene/avatar, independent actor and complete Emote retirement remain unfinished.


## Integrated original Model resources, Chat absence and bounded Audio sources

7d0acd3531 and b906323307 integrate normal texture property ownership v2 and
actual Entity QObject death. 6efa3d353c selects d33b969aff's original
Model/Geometry/material/texture associations and weak histories. Cached texture
QObjects remain alive after the old shared control block expires; the actual
original Resource::allReferencesCleared body is exercised. This is a sampled
observed-object inventory, not complete intermediate allocation history, GPU
bytes, rendering or whole Create completion.

f05d470700, f2a579a8d4 and c7574c1a55 select 5c45014080,1326264ea0 and
63fd562456. The dedicated Audio source reads actual native/script/input/mixer
properties without mutation or enumeration. Four bounded original queue
channels retain timed-out work until actual Qt functor destruction; late values
are discarded. The original full Audio.qml execution proves peak restoration
for both original values on actual component destruction, while an alive
QQmlContext remains explicitly unretired. No app/acoustic/device qualification.

The combined Qt5/default-timeout selection passes5/73 groups in68.85s:
Audio settings/page sources9.125s, Model resources4.952s, normal Model owner
52.502s, actual Entity source2.199s and coverage.067s. These compiler harnesses
execute original bodies with explicit actor/dependency boundaries, not full
Pico translation units or an APK.

49db8bd2ac selects8ecc68242a's passive initial/final Chat cache absence. It
requires actual absent native scopes and closed UI/keyboard, preserving the
separate v4 active history. All51 source/chunk/witness/domain counterexamples
pass22.317s; the actual Qt5 DomainHandler/MessagesClient body passes1.700s, and
the actual Pico absence factory passes8.196s. All4 repository suites pass3.58s.
The first combined CLI command rejected the unknown coverage selector before
running tests; the corrected coverage-matrix command above passes. Total
source-complete areas remain3/14; Create, Audio and Chat remain partial.


## Durable normal HMD view setup and original mode restoration

PicoEmoteView v1 owns ten bounded ordinary controller/menu/View/mode/close steps
with original native avatar/checked action and immutable fixture input anchors.
Original mode/model/Geometry/Rig/pose are captured before mutation. Cold lost
input replies are re-observed without another controller/pointer, including
every restore step. Unknown writes or absent effects retain ownership; a later
fixture cannot relabel a prior uncertain input. Final delivery includes original
native/host clocks, and an older independently published UI file is polled until
its actual timestamp advances. Foreign camera/geometry/pose or candidate changes
stop new input. The owner retains restored journals pending full Qt/menu/native
retirement; process teardown cannot erase them or qualify cleanup.

The first host invocation exposed a local method/attribute name collision,
corrected before the positive checks. The initial ten-case source selection
plus the existing complete normal Emote route, capture/model/pixels and coverage
pass3/73 groups65.48s (normal40.942s,stereo24.471s,coverage.064s). Both actual
Pico factory/orphan teardown cases pass1.894s. Subsequent review added exact
normal command increments, foreign live camera protection and actual delayed
UI publication; all final11 owner cases pass4.451s. The final complete
repository selection passes4/4,2.97s. Registry/coverage/whitespace pass. No native
C++ changed in this packet.

Only the committed Phone view file at abb7f6b60d97daf17752aadf94e2b5df099bb7ba
was inspected for the durable reserve/observe/restore design; its whole-file
hash is recorded in EMOTE_VIEW_MENU.md. Pico uses its own actual HMD native
menu/controller route. Full stereo/actor/scene/avatar/Qt-retirement composition
remains executable next work; source-complete areas remain3/14.


## Correct actual normal camera mode and original boom preservation

Further actual Application_Camera.cpp/Camera.cpp inspection found a concrete
error in the initial local Emote view packet: normal Third Person selects
CAMERA_MODE_LOOK_AT ("look at"), while "third person" names a different legacy
enum. The original fixture had mirrored the wrong string. PicoEmoteView v2
now uses the actual normal enum/string and rejects v1 journals without migration.
The native menu harness additionally compiles full original cameraMenuChanged,
Camera enum/getMode/setMode/getModeString/modeToString and actual Avatar zoom
constant definitions. The original normal pointer/deferred bridge now reaches
those original camera bodies; Qt5 passes8.501s. Native registry/window/Avatar
storage are explicit seams; full camera rendering/application/HMD remain open.

Review also found that restoring a custom first-person boom through the normal
menu would overwrite it. The optional original cameraStateVersion1 source now
measures actual HMD/boom/minimum/default. The owner rejects that unsupported
initial profile, requires actual expected boom transitions and keeps an original
look-at profile's custom boom. Foreign boom changes block new input; restored
boom is independently required. Base Avatar v1 remains readable without
implying this extension. All29 selected owner/Avatar reader cases pass10.341s,
and the full original getter/boom/constant Qt5 body harness passes2.087s.

Create b429bb4381 integrates b938bd9174's production original resource-bound
normal Model owner while preserving all newer Emote/Chat/Audio sources. The
three integrated groups pass89.65s (3/74): original normal owner59.803s, resource
join29.782s, coverage.061s. A property edit/Apply receipt without an actual bound
loaded texture cannot qualify this join; retained actual resources keep the
owners. Full GPU/current pixels/peer/21-step Create composition remains open.

Final original Qt6 normal-menu/camera owning case also passes11.388s. The
final67-case original stereo/reader/owner selection and coverage pass2/74
groups14.39s (stereo14.316s,coverage.072s); all4 repository suites pass3.48s.
Registry and whitespace pass. No complete feature count changes.


## Integrated original initial/active Chat and normal muted Audio segment

645817c457 selects234117b153's separate original cache-absent baseline and
active source v2 flow/witness. Global original query uniqueness and actual native
cache birth/activation fences remain required. Old v1 owners are retained. All41
background/witness/absence cases pass51.701s and5 actual Pico admission/birth/
absence/teardown cases pass21.467s. A complete positive quartet at the original
1.5s real-clock limit remains separately unresolved before a reviewed immutable
candidate-admission optimization; no timeout was enlarged or failure hidden.

61c9259de6 selects e58aaeed0c's normal Audio open/muted-start rejection/restore/
PCM-release/Home/closed segment. The actual native error start time, original
controller streams/neutral facts, input peaks and two independent3s nine-clock
quiet windows are composed; all original journals stay retained. An original30s
AudioClient callback and alive QML context are not retired by memory/PCM release.
Full acoustic/peer/whole Audio qualification remains missing. Integrated owner/
preview/coverage pass3/75 groups28.30s (owner16.398s,preview11.817s,coverage.083s).
All4 repository suites pass4.18s; registry/whitespace pass.


## Actual Home transition before closing Emote view preparation

Actual TabletProxy/TabletRoot inspection confirms physical hiding does not
reset a retained menu to Home. The initial host tablet fixture had incorrectly
reset that state on open. PicoEmoteView v3 now composes the existing original
Home entity observation and calibrated normal PicoTabletHome controller ray
before each close. Initial closed Home, actual Menu/not-Home phase, original
Home/tablet entity IDs, advancing source cursors/times and actual closed Home
are all required. Unknown Home delivery is only re-observed; ignored input
never closes or sends another gesture. Both original setup/restore routes
now have six steps; v1/v2 journals remain retained without inventing Home proof.

The fixture now keeps the underlying menu during physical hide/open. All13
ownership cases pass6.461s before the final foreign-Home/source tightening; the
final68-case stereo/owner/reader/capture group plus coverage pass2/75 groups
15.10s (stereo15.040s,coverage.061s). Both actual Pico view factory/teardown
cases pass1.851s, all4 final repository suites3.05s, registry/whitespace pass.
No new native C++ or product changes in this packet. Independent original menu
Timer/QQmlContext, controller envelope/neutral retirement, scene/avatar/actor
and whole public coordination remain open; source-complete count is3/14.


## Original menu Timer/context lifetime continuation

The optional original ViewMenuLifetimes source is wired into actual Pico
NavigationUi and the strict compatible reader. It retains original nested QML
page/StackView/delay Timer/component+Timer contexts, actual running/pending item
and real weak-object deaths. The view owner joins this original append-only
history and exposes separate fresh known-menu retirement without discarding
its journal or inferring complete controller/native cleanup.

Initial compilation rejected QQmlContext::objectForName under actual Qt5; the
source now uses actual visual child/id associations. Runtime inspection then
showed the nested root's outer creation context belongs to TabletMenu.qml,
so qualification follows the actual StackView child source context and both
original root/d IDs. A post-mouse Timer check was too late for the actual zero-
delay callback; the harness now observes the actual Timer's runningChanged
signal and measures real pending state without calling a product handler.
No product QML or timer behavior was changed. All20 focused owner/reader cases
pass7.338s and original Qt5 menu/Timer owning native case passes7.268s before
the final test-witness disconnect. Exact original C++ empty/live/dead-page
packets also pass the Python reader. Alive contexts remain explicitly retained.

Final Qt5 owning menu/lifetime selector7.553s and75-case stereo/owner selection
15.108s plus coverage.065s pass3/75 groups22.73s. Qt6 original menu/lifetime
owning case also passes10.196s. All4 repository suites pass3.07s; registry and
whitespace pass. Native application/whole translation unit/HMD remain unqualified.


## Immutable original candidate admission and actual native Chat mutations

d6ccd57e70/283851a65b/16dc65817f select9d7ac4ae01/bbe14c879b/51b7043c2e.
One original full verifier result is bound to held original hashed files, exact
arguments/types/environment/CWD, original policy/decoder/JVM/receipt inventory
and bounded original directory identities. Queries admit nothing new and do
not recursively scan tools. Kernel OFD identity with a retained duplicate
prevents closing a recycled foreign descriptor, including a new open of the
same file. Unsupported kernels retain the original full-verifier path. Every
PM path, installed double hash, process and OpenXR guard remains live. Changed
inputs permanently reject the original lifetime; no timeout or CI verifier was
weakened. This preserves original qualification, not new decoder qualification.

ccf6f9618a selects4ea6ad1bfe's native Chat v3 original opening/retirement command
identities. The actual first mutation records them under the original mutex;
later inspect/observe/retire cannot replace them. Existing v1/v2 component
histories remain readable, with no v3 downgrade or invented mutation provenance.

All54 original binding/OFD/CWD/actual positive quartet counterexamples pass
22.161s. The full integrated default-timeout selection passes4/75 groups119.94s:
normal Scripts105.585s, normal Chat3.953s, normal Emotes10.335s, coverage.070s.
No host or adapter budget changed. All83 native Chat/domain/absence/samples/
mixer/witness cases pass29.553s. The first command used a nonexistent mixer
module name and failed that import; the corrected complete command above passes.
The actual Qt5 DomainHandler/MessagesClient/header v3 source, with original C++
packets also validated by Python, passes1.677s. All4 repository suites pass3.31s.
Whole Chat activation/retirement/25-step/physical cleanup composition remains
open; source-complete feature count is3/14.


## Integrated actual Audio lifetime, private Create writer and Chat cache owner

c972512d7e/bfd8f185a1/b28b34842c/9ebfe3ff76 select Audio82154743ef/
0e3ae2add8/2daedbf74d/03cc940d0b. Actual original 30s functor invocation
and final lease destruction, polling QObject and retained byte/capacity values
are observed through bounded original worker queues and AudioSettings v2.
The normal page owner waits read-only for actual original callback completion
and independently measured baseline resources, then another real3s quiet
window. No due-time, empty PCM, stopped timer or process restart supplies release.
712d05d132 selects c2690edd33's actual full saveObject private Create result
write/replace/refusal checks. The generic root feature-result writer already
provides the required private path; redundant support7f5f4602b1 was not selected.

The integrated four native/host groups pass80.23s: Audio preview2.413s, normal
page30.054s, settings including actual30s native42.720s, Create actual original
resource/private-writer5.038s. Qt5 uses the existing5.15.18 prefix. Narrow
native harness seams remain documented; whole app/Pico/device unqualified.
b11226fdd6 selects3333e572cb's original nativev3 Chat mutation lifetime owner.
Both lost Observe/Retire are reconciled only with original first-mutation IDs;
two new passive retirement queries retain all journals. All42 CacheLifetime/
native observation/domain cases pass. Complete source count remains3/14.


## Original Emote View v4 controller envelopes and neutralization

All setup/restore controller grants are written before the actual canonical
session transport and independently require original owned neutral status.
Original calibrated Home geometry determines the actual ray. Locked callbacks
perform only host CAS/freshness checks; cold reconciliation never repeats input.
The separate final controller-retirement read preserves every original journal;
Qt/menu/native/scene/actor/whole common cleanup remains separate and unfinished.
The initial focused25 cases pass13.917s; final additional slow intent case is
included in the broader selector. The first broader invocation exposed a test
import-root omission and eager session construction in the empty factory.
The import root and lazy cached original session were corrected. No timeout
was enlarged. Final normal Emote21 cases11.209s and expanded stereo/owner
group22.286s pass2/75 catalog groups33.49s. Original session persistence is
real host code; native transport/HMD effects are explicit synthetic boundaries.

All4 final repository suites pass2.85s; contract registry, probe JavaScript
syntax and whitespace pass. No complete feature count change.


## Original Chat actor pending-publication recovery

1cfa873679 selects9d3c232a98. Only unchanged actual source/command/result
inodes, original bytes, nativev3 first-mutation IDs and the live original
PID/start/kernel-held FD can reconcile a pending IPC manifest. No command is
rewritten, resent or retimed. All47 original actor-file/cache-lifetime/Linux
process cases pass3.205s. The actual Qt5 C++ headers through Linux PID/FD and
Python cache owner pass1case2.325s; original Observe/Retire counters are1/1
and the unlinked original result FD is actually gone. The actual Pico cache
factory/retained cleanup case passes1.551s. The worker is an ephemeral owned
stdin fixture, not an Overte Agent, device lab or service. Network/NodeList/
assigned-script are explicit seams. Full Chat composition remains partial.

All4 final repository suites pass5.39s; registry and whitespace pass.


## Controlled original avatar resources in the normal Emote view route

The selected fixed Phone immutable resource helper supplies actual configured/
loaded URL hashes and bounded original qrc bytes through existing AvatarRender.
The full original getter compiles and its actual qrc-backed C++ output now passes
the strict Python reader and pinned-resource join. The first cross-language
execution detected the old native fixture's singular sentinel projection; a
second attempt still lacked the required perspective bottom-right zero. The
fixture now supplies an invertible perspective matrix while retaining distinct
original row/column sentinels. Product camera behavior was unchanged. Final
Qt5 getter/resource/reader case passes3.385s. All18 native-reader cases pass
.097s and25 actual normal view/controlled admission cases pass30.831s, with
explicit synthetic HMD/transport boundaries. Native full TU/app/GL/HMD remain
unqualified. All original v4 histories without resource proof remain owned
and cannot be qualified by a later query. Full stereo scene/actor still open.

Final Qt6 actual qrc/getter/strict-reader case passes3.678s. The integrated
normal Emote11.456s, expanded stereo/owner48.963s and coverage.074s pass
3/75 catalog groups60.49s. All4 final repository suites pass4.16s; registry
and whitespace pass. Source-complete feature count remains3/14.


## Integrated normal Create parent, Audio capture and original Chat stage joins

ce54cbe311 selects480a756dca's v3 flow/witness initial-to-active original
lifetime join. All45 witness/samples/absence cases pass15.180s and the actual
Pico witness factory case1.171s. The first factory command referenced a wrong
method name and failed before execution; the corrected actual case passes.

32da3eee7b selects adc7dd22ee's normal Audio capture and immutable PCM owner.
Four integrated groups pass84.31s: capture25.864s, normal page55.700s, preview
2.681s, coverage.065s. Both real catalog conflicts preserved every current root
selector and added only the new capture group (75 to76). No timeout changed.
2d7895667d selects78833fc346's normal mute interruption/unmute and original
termination source fences. Historical v1 stays v1; new authority requiresv2.
Its expanded integrated capture/factory group passes21.265s below.

4877a2af44 selects2b610f6de7's first-twelve-step normal Create parent. Existing
root Lifecycle source binding and actual shared channel lock were preserved;
the redundant older agent binding method was omitted. Additive catalog/version
resolution preserves all root Audio/Emote/Lifecycle safeguards, registers the
new owner only once, keeps native-script-workv2 once, and raises76 to77 groups.
Actual original Model export, both existing child factories/normal input routes,
private files and retained editor/context/resource proofs are exercised at the
documented synthetic native/domain/renderer boundaries.

The first six-group regression passes five: Create parent35.218s, Model47.774s,
picker60.938s, Audio capture21.265s, coverage.062s. The older normal-create
foundation case failed10.030s because it changed opt-in environment after the
candidate's immutable admission. The existing seal correctly refuses that
change. The fixture now explicitly tests refusal and cold-admits a new CLI
instance after opt-in, preserving the original guard. Final normal-create
37 cases pass8.887s. No product input or candidate policy was weakened.
All three complete source areas and all device/app qualification boundaries
remain unchanged; source-complete count remains3/14.

All4 final repository suites pass3.16s; registry, probe JavaScript syntax and
whitespace pass. The original candidate environment guard remains unchanged.


## Original Pico Emote scene and Create completion fences

Create phase/freshness follow-ups abdbf202e9 and7f164702d2 are integrated as
58bc6ddbe9 and1ccaeeaf07. Every input and completion rechecks the original
fixture phase; combined native/host age includes final Root CAS and candidate
guards. A private completion companion retains the exact original call through
a lost final pending-clear/rollback. No timeout or original capture clock is
changed. The integrated create-feature-owner group passes88.721s (1/77).

The full original new Pico scene header and complete native Scene/Avatar getter
bodies pass actual Qt5 (4.671s) and Qt6 (9.016s) native cases. Real qrc contains
the repository FST/FBX. EntityTree, Model/Rig/camera and dependency storage are
explicit seams. Original actual Web/Shape factory deleteLater lambdas prove
that absent IDs and shared-pointer expiry do not imply original QObject death.
A timed-out queued prepare is never dispatched later; actual pending functor
death is required before a subsequent request. No full native TU/app, browser,
GL, Pico/OpenXR or device qualification follows.

The first owner run had two test expectation errors: corruption correctly
failed via the shared phase ValueError, and a native clock jump correctly
failed contiguous-window validation. Expectations now require those refusals.
An imported TestCase also accidentally duplicated nine existing source tests;
module import now preserves the intended owning selection. The next14 owner
cases pass15.116s. Both actual Pico factory/cleanup cases pass2.075s. Further
phase-race and frozen-native quiet-window cases are included in final regression
below. No production behavior or evidence threshold was weakened.

Final integrated regression passes3/78 catalog groups86.77s: coverage.110s,
original scene native5.316s, expanded stereo/Emote owners81.346s (including
all16 new scene owner/source cases). All4 repository suites pass5.55s; registry,
probe JavaScript syntax and whitespace pass. The new scene native selector
is the only catalog addition (77 to78); no timeout increased. Actual factory
and common-cleanup cases separately pass2.075s. Originals/journals remain
retained, full Emote/public/actor composition stays open and complete source
feature count remains3/14.


## Bounded original normal Chat attempts

5298bca73c selects773bdb9811's ChatNormalInputv2. Completed exact original
attempts use existing immutable ChatSourceChunks; only the current attempt
remains packed in the root. Existing48KiB and raw-history limits are unchanged.
A durable reading intent precedes child archival; lost root/child ACKs, orphans,
replacement and oldv1 owners remain unknown without adoption or replay.
All15 integrated normal-input cases pass62.600s, actual Pico factory case
passes.879s. The complete dispatcher/actor and final resource/FD/process
retirement are still open; source-complete count stays3/14.


## Exact original Emote controller streams

PicoEmoteInputsv2 now owns the actual canonical OpenXR tablet envelopes and
separately queried original neutral packets before independent after-frames.
Immutable input archives preserve the original nonce/advancing sequences.
The callback is strictly host-only under the canonical sequence lock. Final
controller-retirement reads preserve all journals. Each Qt entry/scroll/play
now retains a fresh full original source barrier; phase/native/host bounds
include durable intent and guards. Oldv1 input histories cannot acquire
missing stream facts or v2 authority. No complete Emote capability is added.
The original9 cases pass10.316s after migration; all15 cases with new exact
stream, missing/foreign/active/future neutral, slow CAS, phase race, pure-host
callback, final original neutral and legacy refusal pass23.223s.

The first four-group regression passed coverage.063s, normal Emote10.942s
and background/effects42.169s, but the expanded source group hit120.037s.
The initial lifetime-only split passed its new group39.081s while the source
group still hit120.007s. Both original failed JUnit files are retained privately.
The final lossless split keeps original storage/source28 cases separately
from normal input/native effects28 and manager-work/lifetime32. Default120s
limits and every original assertion remain unchanged; the catalog grows78 to80
only to partition the owning checks. Final source96.987s/coverage.275s pass
2/80 groups; input/effects114.526s passes its1/80 selection. Earlier lifetime
39.081s remains the unchanged owning result. The added last-guard case also
passes.494s: native-clock advance after the last candidate guard with frozen
host time prevents input. No higher-level feature or device completion follows.

All4 final repository suites pass13.45s. Registry, probe syntax and whitespace
pass. The input registry correctly advertises only readablev2; oldv1 remains
retained/rejected, never silently promoted. Complete source/host areas stay3/14.


## Integrated Audio HOME/return and original cancellation

e24f554416 selects a14fb032be's normal HOME/Resume with actual original OS
PID/start/foreground, native same-cycle cancellation and post-return quiet.
db619a5ed6 selects02c9609b4c's independent exact original fixture phase fence
after durable HOME/Resume intent and before returned/quiet release. No Qt source
is queried while backgrounded. Native cancellation and cumulative Lifecycle
changes remain distinct from OS acknowledgements. Lost delivery is never resent.
Host/native final age includes retained copies, CAS and final guard. All original
journals remain until final whole Audio closure; no acoustic peer is invented.
Existing Emote scene/stream and all current Create/Chat guards were preserved
in the clean local selections. No new selector is added (catalog80).

Concurrent host regressions showed measured contention: an unchanged agent
Audio group rose39 to120 seconds while several broad selections ran. The team
now finishes already running selections, then staggers broad regressions while
all three agents continue feature work and targeted counterexamples. Timeouts
and observations are unchanged. The root's final integrated Audio and actual
Qt5 original pause/poll/deferred-callback checks are recorded below.

The actual Qt5 original AudioClient pause body, original250ms input-loss poll,
original natural30s callback/functor retirement and strict lifetime reader pass
(exit0). Audio-format/device/renegotiation hosting remain explicit seams; this
is not a full AudioClient TU/application or acoustic/device qualification.

The initial integrated catalog run passes coverage.136s but Capture122.108s
and Page120.035s hit their unchanged120s limits under concurrent load; its
original failed JUnit remains private. The48 Capture-group cases included22
new BG cases. Those22 now have their own audio-background-owner group; the
remaining21 capture and5 actual factory/orphan cases remain in Capture. Every
assertion and original source is retained; the catalog changes80 to81.
After broad runs were staggered, the complete final selection passes5/81
groups157.74s: Runner2.460s, coverage.217s, Capture52.201s, BG30.953s and
Page71.909s. All4 repository suites pass11.24s. No timeout is enlarged.

The runner previously discarded TimeoutExpired.stdout when Python returned
bytes despite text=True. It now decodes and retains the owning test's partial
diagnostics in the failed report. Its existing real one-second timeout/fail-fast
case also verifies a flushed original Unicode diagnostic, without changing
failure/timeout/pending semantics. Registry, probe syntax and whitespace pass.
Complete source/host areas remain3/14; whole Audio and physical qualification
remain open.

## Final original QML admission and normal Audio final-close integration

8544d36768 selects5bd12aa3ae's shared owned final QML transport callback. The
original Pico navigation/NativeIO route passes all five targeted host cases
(.876s): final guard ordering, original command-copy isolation, single writer,
refusal without retry, candidate change, owner retention and unchanged default.
The normal Emote catalog now owns these cases as well. Emote Inputs and View
reuse this boundary and retain their original pending intent when the actual
phase or native source age changes immediately before publication. Four focused
Emote cases pass5.974s, including the ordinary complete open/play/cancel/close
input sequence and original camera restore tested in the first narrow run.
The initial narrow run exposed a synthetic test-transport token mismatch:
it used the synthetic widget's internal token instead of the original Pico
projection's token. Only that explicit test seam was corrected. No product
input token or native validation was relaxed. Broader regression is pending.

b625e519f9 selects e11c42fb42's normal Audio final double-X owner. It retains
original PCM and source manifests, requires actual private tap absence, normal
Audio page destruction and original peak restoration, then closes the tablet
with original controller streams and fresh quiet. Deferred native functor
retirement and baseline resource equality remain separate observations. The
catalog gains exactly audio-final-close and audio-final-retirement (81 to83),
preserving the root background partition and all newer feature guards. Root
final-owner regression is pending. Audio/Emote remain partial; no application,
OpenXR, physical audio, stereo or device qualification is asserted here.

## Selected final-owner and PolyVox regression

At af20152d2d, the frozen root selection passes8/85 catalog groups264.53s:
coverage.084s, AudioFinalClose71.013s, AudioFinalRetirement42.831s, original
PolyVoxQt5UI7.562s, originalEntitiesQt5native7.247s, normalEmote11.538s,
EmoteInputEffects69.856s and stereo/View/scene owners54.393s. No timeout or
operation bound changed; every required case ran. Before that selection all
four repository suites pass3.09s. Those native harnesses retain explicit
model/renderer/SDK seams and do not establish full TUs/application or devices.

Subsequent root3cb3ad8f2c/2580202a4f/a9a9c0e3b2 select the generic controller
owner pair, its direct candidate-check review fix, and once-only OS transport.
The new controller path explicitly preserves original installation admission
before its final callback. a89b96b88c/8d73e9ce3d select Create's actual final
QML intent/current-UI/phase admission and narrow original generic Home/pager
compatibility fix. Agent focused results are recorded in their packets; root
combined followup verification is pending.

One new normal-input-transport selector owns the shared13 original transport
cases; the five QML cases move there from normal-emote without duplication.
This changes the catalog85 to86, retaining all previous feature assertions and
the same120s group timeout. No new complete feature capability is advertised.

Root followup selection is3/4 green89.33s: coverage.068s, all13 actual
transport-boundary cases2.370s, complete existing CreateFeatureOwner52.251s.
CreatePrimitiveOwner runs all8 cases34.053s with one unresolved cold recovery
error in test_lost_final_apply_reconciles_without_repeating_original_input;
the other7 pass. The selection is not green. Original pending Apply ownership
is retained; no input replay or bounds change is used. A targeted source fix
and rerun are required before that primitive packet is considered verified.
