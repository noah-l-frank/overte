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
