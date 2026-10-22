# Android Phone source coverage

This review is pinned to `62bb0685d073981009cfead3619984d2d70c224f`
(2026-10-22). The versioned [JSON matrix](phone-source-coverage.v1.json) records
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
| World Navigation | Implemented | **Pending: scene-profile conflict** | Reported | Partial Qt components | [Navigation](WORLD_NAVIGATION_FEATURE.md) |
| Authentication | Implemented | Implemented with prerequisites | Reported | Area instrumentation uncompiled | [Authentication](AUTHENTICATION_FEATURE.md) |
| Avatar / People | Implemented | Implemented with prerequisites | Reported | Partial Qt components | [Avatar / People](AVATAR_PEOPLE.md) |
| Create | Implemented | Implemented with prerequisites | Reported | Partial Qt / filesystem components | [Create](CREATE_FEATURE.md) |
| Emotes | Implemented | Implemented with prerequisites | Reported | Partial Qt / QML components | [Emotes](EMOTE_FEATURE.md) |
| World Web | Implemented | Implemented with prerequisites | Reported | Partial Qt / JNI / Java / R8 | [World Web](WORLD_WEB_FEATURE.md) |
| Graphics | Implemented | Implemented with prerequisites | Reported | Area instrumentation uncompiled | [Graphics](GRAPHICS_FEATURE.md) |
| Audio | Implemented | Implemented with prerequisites | Reported | Partial Qt audio components | [Audio](AUDIO_FEATURE.md) |
| Chat | Implemented | Implemented with prerequisites | Reported | Partial Qt / QML / peer / Settings | [Chat](CHAT_FEATURE.md) |
| Snapshots | **Pending public composition** | **Pending parent integration** | Components only | Partial Qt / Java / filesystem / HTTPS | [Snapshots](SNAPSHOT_FEATURE.md) |
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
- **World Navigation:** `domain-roundtrip` calls normal `scene.load` for
  `OVERTE_E2E_SCENE_URL`; the Android debug Appium route accepts only the embedded
  `overte-e2e://fixture/scene` URI. Mandatory `places-navigation`, normal navigation
  profile and provider instead require an HTTP(S) `/scene.json`. No single suite
  URL currently satisfies both. The full facade's initial scene must additionally
  match the independently configured HTTP provider. Integration owns an exact
  controlled scene/profile join through normal inputs and original arrival.
- **Snapshots:** capture/VM/review/normal controls, Save/Share consumer originals,
  exact owned files and HTTPS upload sources are present and have component
  evidence. The assessed adapter still declares no `feature.snapshots.*` triple,
  complete feature flag/factory or observer area. Root must update this row only
  after full public facade, mandatory foundations and closed retirement integrate.

These are source findings, not skipped passing checkpoints. Missing abilities
stay red; this review changes no dispatch or gate to conceal them.

## Scope of evidence and updates

The current [observer](script_observer.py) uses closed grammar **v7**, with
historical v2–v6 grammars retained separately; snapshots is absent. Some older
handoffs still mention v17 or earlier observer versions. Current source imports
common `VERSION=18`; the matrix uses that source and preserves the historical
handoffs as qualified evidence. This document does not amend their old results.

Original C++/Java compiler-component checks do not build full Android application
translation units, exercise a real Android renderer/IME/OS, prove live
network/peer/AssetServer/oven behavior, or establish microphone/camera/device
acceptance. Assets additionally documents an unresolved product upload callback
lifetime risk and missing host GLM for a full HFM syntax check; those are not
resolved by its synthetic composition test. Central source/admission pins and
global count/profile reconciliation remain integration-owned.

The matrix was checked directly against catalog/scenario membership, actual
operation sets and invoke branches, current default-off flags/observer grammar,
all repository-relative evidence paths and documentation links. Only these two
files are changed. After the pending joins integrate, reassess affected rows and
record the new exact source revision; do not replace a historical assessment
with an unversioned claim of completion.
