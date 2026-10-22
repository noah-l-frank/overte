# Android Phone source coverage

This source assessment is pinned to `8112c717643b76d3d4682057f29a0f485fd32efe`
(2026-10-22) and supersedes the earlier matrix assessment at
`4b6ad2974cc85549aafa30f8ef9530bba404f568`. The versioned
[JSON matrix](phone-source-coverage.v1.json) records
all 14 common v18 areas, their actual Phone Appium declarations/dispatch,
default-off flags, every catalog foundation and its required capabilities,
and existing test/handoff paths. It is documentation, not another runner or
acceptance result. The source review itself runs no target or build. The explicitly recorded parent
host checks use synthetic native/SDK boundaries and controlled loopback services.

“Implemented” below describes source composition. “Reported” means existing
handoffs report targeted host verification with explicit synthetic target
boundaries; it does not mean this audit repeated those tests or ran a complete
physical suite. Native component compilation is a separate dimension. **Every
row remains full-Android-build unverified and device untested.** Pico and iOS
are unknown here and belong to separate sessions.

| Area | Public facade source | Whole catalog source join | Host facade | Native qualification available | Handoff |
| --- | --- | --- | --- | --- | --- |
| World Navigation | Implemented | Implemented with prerequisites | Reported | Partial Qt components | [Navigation](WORLD_NAVIGATION_FEATURE.md) |
| Authentication | Implemented | Implemented with prerequisites | Reported | Area instrumentation uncompiled | [Authentication](AUTHENTICATION_FEATURE.md) |
| Avatar / People | Implemented | Implemented with prerequisites | Reported | Partial Qt components | [Avatar / People](AVATAR_PEOPLE.md) |
| Create | Implemented | Implemented with prerequisites | Reported | Partial Qt / filesystem components | [Create](CREATE_FEATURE.md) |
| Emotes | Implemented | Implemented with prerequisites | Reported | Partial Qt / QML components | [Emotes](EMOTE_FEATURE.md) |
| World Web | Implemented | Implemented with prerequisites | Reported | Partial Qt / JNI / Java / R8 | [World Web](WORLD_WEB_FEATURE.md) |
| Graphics | Implemented | Implemented with prerequisites | Reported | Area instrumentation uncompiled | [Graphics](GRAPHICS_FEATURE.md) |
| Audio | Implemented | Implemented with prerequisites | Reported | Partial Qt audio components | [Audio](AUDIO_FEATURE.md) |
| Chat | Implemented | Implemented with prerequisites | Reported | Partial Qt / QML / peer / Settings | [Chat](CHAT_FEATURE.md) |
| Snapshots | Implemented; full replay pending | **Pending whole SDK29+/SDK26–28 common qualification** | Targeted facade / actor / recovery / retirement | Partial Qt / Java / filesystem / HTTPS | [Snapshots](SNAPSHOT_FEATURE.md) |
| Scripts | Implemented | Implemented with prerequisites | Reported | Area instrumentation uncompiled | [Scripts](SCRIPT_FEATURE.md) |
| Assets | Implemented | Implemented with prerequisites | Reported | Partial Qt / QML / file / geometry / oven components | [Assets](ASSETS_FEATURE.md) |
| Lifecycle / Input | Implemented | Implemented with prerequisites | Reported | Partial original Qt / QML / IME / keyboard / timer | [Lifecycle / Input](LIFECYCLE_INPUT_FEATURE.md) |
| Tablet Web | Implemented | Implemented with prerequisites | Reported | Partial Qt / inline leases / JNI / Java / R8 | [Tablet Web](TABLET_WEB_FEATURE.md) |

All available public triples are in the existing [Phone Appium adapter](appium_adapter.py).
The complete flags alone do not supply every private target control or compiled
hook. The JSON lists the full capability union for each suite, including
`launch-smoke`, and expands every reused foundation's original catalog inputs.
The unchanged [common capability gate](../../modules/feature_capability_gate.py)
requires that union before an area can pass. Candidate/artifact/session/PID,
private credential/configuration, separate actor, freshness, ordinary input and
original file/byte/lifetime obligations remain necessary. An ACK supplies no
observed product effect.

## Concrete open joins at this revision

- **Create resolved:** The [original collaboration foundation](CREATE_COLLABORATION_FOUNDATION.md)
  now provides guarded Appium dispatch and runs the unchanged mandatory entity-sync
  module and Create gate from a serverless initial world. All 12 new parent
  source/host cases passed in 24.642 seconds. The original actor and independently
  received native properties must prove each edit; delivery acknowledgements,
  ignored domain entry and lost returns cannot produce a false success.
- **World Navigation resolved:** Exact HTTP scene/profile/provider admission
  through ordinary Go To inputs now runs unchanged `domain_roundtrip.py`,
  `places_navigation.py`, feature preparation and the mandatory gate. Actual
  advancing domain/scene arrivals prove effects. SDK session/generation/target,
  PID and installed bytes stay pinned around every input; lost returns are never
  replayed. Parent integration passed 71 combined Navigation/Create/OS-input
  cases in 55.364 seconds, with explicit synthetic target boundaries.
- **Snapshots in progress:** The public facade/default-off triple, independent
  original role/actor, v8 observer and original-bound retirement source are now
  integrated. Parent verification passed 67 targeted original/dispatch/Qt/TLS
  cases in 88.631 seconds. That union does not execute a complete common area.
  Targeted counterprobes now cover partial bootstrap and pre-export cleanup,
  constructor-to-lock foreground/OS authority changes, passive history floors,
  uncertain background/Save/Share delivery, and interrupted journal retirement.
  The full-retirement audit additionally passes five actual host composition
  cases (90.218 seconds): normal Capture/Save/upload and cleanup, separate actor
  quiet/exit, repeated public finalization, late-file/open-FD preservation,
  foreign child ownership and resume after an actual child unlink. These are
  scoped host results. Both whole MediaStore SDK29+ and SDK26–28 document-picker
  common replays and their integrated recovery qualification remain open;
  Snapshots stays outside the 13 qualified full catalog joins.

The [owned Snapshot marker refresh](SNAPSHOT_FEATURE.md#owned-marker-refresh-v3)
uses the original active local fixture rather than repeating `prepare`.
Initial marker source v2 remains unchanged; refreshed source v3 preserves
creation/view/entity identity and appends original edit inputs and times.
The Qt/reader/Probe/facade selection passed 51 checks in 29.488 seconds.
Lost replies recover only the archived request's actual native effect;
current object URL and fresh current-ticket rendered pixels remain separate
requirements. This closes the demonstrated second-prepare source mismatch,
not the pending whole-common qualification.

These are source findings, not skipped passing checkpoints. Missing abilities
stay red; this review changes no dispatch or gate to conceal them.

## Scope of evidence and updates

The current [observer](script_observer.py) uses closed grammar **v8**, with
historical v2–v7 grammars retained separately. Snapshot admission/configuration,
public facade, independent actor and strict finalizer are integrated; their
whole common backend/recovery qualification remains pending. Some older
handoffs still mention v17 or earlier observer versions. Current source imports
common `VERSION=18`; the matrix uses that source and preserves the historical
handoffs as qualified evidence. This document does not amend their old results.

Original C++/Java compiler-component checks do not build full Android application
translation units, exercise a real Android renderer/IME/OS, prove live
network/peer/AssetServer/oven behavior, or establish microphone/camera/device
acceptance. Assets additionally documents an unresolved product upload callback
lifetime risk and missing host GLM for a full HFM syntax check; those are not
resolved by its synthetic composition test. Fixed executable-source admission pins reproduce the current Probe and script
bytes at source `90f659091b92bcb1ee85aeb0053c737193d1fa9a`; they do not
qualify a compiled APK. Final full-composition/count reconciliation remains open.

The [dedicated debug build](../../../../android/phone/docs/BUILD.md#dedicated-feature-e2e-debug-build)
requires explicit `overteFeatureTests=ON` and the separate foundation hooks.
The option is default OFF and forced OFF for non-debug types. Seven actual
Gradle-loader/Groovy/CMake component checks and the existing release checks pass.
Own prepared dependency graphs, the verified 16 KiB sentinel, runtime/host tools
and AGP cache are absent; the SDK/NDK/JDK exist. No full Android build is claimed.

The matrix was checked directly against catalog/scenario membership, actual
operation sets and invoke branches, current default-off flags/observer grammar,
all repository-relative evidence paths and documentation links. The supplemental
review confirms the 14 declared triples, default-off admission, original catalog
foundations and v18 cleanup dispatch in source; it runs no tests or builds and
preserves the pending Snapshot aggregate qualification. After the pending joins integrate,
reassess affected rows and
record the new exact source revision; do not replace a historical assessment
with an unversioned claim of completion.
