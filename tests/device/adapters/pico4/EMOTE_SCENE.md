# Pico Emote stimulus scene and original object ownership

`PicoEmoteScene` owns only a local gray background and one challenge Web entity.
It supplies stimulus setup and original entity lifetime evidence. It supplies
no animation, stereo pixel, peer/actor, browser/GPU, callback or complete feature
verdict. No new full capability is advertised. The existing View owner first
selects normal third-person `look at` in actual HMD mode. The independently
observed avatar must use the actual pinned bundled FST/FBX resources.

The source was selected from fixed Phone commit
`abb7f6b60d97daf17752aadf94e2b5df099bb7ba`; the exact source hashes and exclusions
are in `PHONE_SHARED_EMOTE_SCENE_20261022.json`. Only central-camera fixture
geometry and owned deletion principles are reused. No Phone touch, view setter,
mono pixels, per-eye policy or success measurement is copied. `imageExtent` and
`markerRoi` author a stimulus using the actual central view inverse projection.
The existing original model-specific stereo draw/camera, PNG and challenge
validators must independently qualify both submitted headset views later.

## Original native interface

All mutations are gated by `OVERTE_E2E_FEATURE_TESTS`,
`ANDROID_APP_PICO_INTERFACE` and `--testScript` with an actual active Lifecycle
observer and private output root. Commands use strict v1 shapes:

- `feature-pico-emote-scene-input`: `prepare` adds `runId`, `ticket`,
  `fixtureUrl`, `imageExtent`, `markerRoi`; `release` adds `runId` and the actual
  original `fixtureInstance`.
- `feature-pico-emote-scene-observe` adds only `runId`. It reports original
  instance/process/cursor/clocks, original input/view, both original IDs,
  independently fetched properties, tree absence and retained original objects.

The actual TestScriptingInterface getter uses the existing bounded original
dispatcher with its own queue. A timed-out queued functor cannot later prepare
the scene. The original pending functor must actually retire before another
request is admitted. This reuses dispatch mechanics, never Audio state.
The native getter caches exact original command/results without retiming.
Changed commands with reused IDs refuse. Bounds are 4096 requests and 256 seen
runs per native process; exhaustion refuses rather than evicts uncertainty.

Release preflights both actual entities under the same EntityTree write lock as
deletion. Exact original shared pointer and QPointer identity, local host,
unlocked state, no parent/children and no clone relationship are required.
A foreign same-UUID replacement prevents all deletion. `drained` requires both
IDs absent and both original weak references **and** QObject guards dead.
Original Shape/Web factories use `deleteLater`; weak shared ownership expiry
alone cannot establish this death. Browser/renderer ownership remains separate.

## Durable host owner

The actual Pico factory shares the existing Script source lock, immutable
candidate/process binding and private feature channel. The v1 scene journal
retains original phase/native/avatar packets using bounded existing compressed
history. Exact prepare/release responsibilities are durable before transport.
Final phase, candidate, native-clock and elapsed host-clock checks include the
CAS; a frozen device clock cannot hide a slow intent writer. Input receipts
remain distinct from effect observations.

Prepare requires the original baseline ticket; release requires the original
cleanup phase. A changed/retired phase, missing avatar resources, foreign
process/source, moved authored scene, missing objects or ignored input refuses.
After lost responses, `reconcile()` only queries original sources. A cold
cleanup with a recorded release never dispatches it again, even if delivery
remains unknown. A stored but undelivered prepare is unresolved; no new prepare
is permitted. Failed writes retain the original responsibility.

Cleanup requires independently observed `drained` plus a contiguous three-second
quiet window in actual host monotonic time and both original native source
clocks. Frozen time and clock jumps cannot substitute for that window. Up to
41 reads/40 waits of 100ms are allowed per cleanup invocation; source reads keep
their own original bounded timeout. Native originals are bounded to 256,
combined frames to 128. Exhaustion retains ownership. The final journal remains
for the future parent join. Common cleanup refuses while it exists; it does
not infer object death from journal existence, remove it or restart a process.

`proof()` returns retained historical object-retirement originals, never a new
fresh feature result. A later parent must freshly join its independent sources,
stereo/actor evidence and all other resource/callback retirement before final
journal release. Interrupted ready-state samples retain their actual evidence
without rewriting the original qualifying ready frame.

## Verification boundary

The full original scene header, complete scene and AvatarRender getter bodies,
original Shape/Web deleter lambdas and original bounded dispatcher compile and
execute with real Qt5 5.15.18 and Qt6 6.11.2. Actual repository avatar resources
are registered with the real Qt resource compiler. EntityTree, entity payloads,
dependencies, Model/Rig and camera storage are explicit host seams. This is not
a full native translation-unit, application, GL/browser, OpenXR or device build.

The real owner/reader tests exercise durable ordering, original packet joins,
lost prepare/release responses, lost CAS ACK, phase races, foreign identity,
retained objects, slow intent writes, actual quiet time and corrupt histories.
The actual Pico factory/candidate and common-cleanup retention have separate
tests. `emote-scene-native` owns native compilation; `emote-stereo-capture`
includes the owner counterexamples. Complete Emotes remain partial.
