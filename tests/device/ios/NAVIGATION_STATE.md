# Original iOS navigation state

This component observes actual native arrival prerequisites. It does not publish
Worlds/navigation capability or replace original rendered pixels, independent
actor/provider observations, restart or whole-run cleanup.

`feature-ios-navigation-state` accepts exactly schemaVersion 1, an iOS command
nonce, action and run ID. No target URL, wanted pose, selector, file path or
expected outcome enters the native query. The existing owned HTTP command,
probe dispatcher and fixed private `feature-ios-navigation-state.json` AFC
transport carry its original result. Duplicate command polling does not issue a
second native read. A missing hook stays unavailable.

The dedicated `OVERTE_E2E_FEATURE_TESTS` and iOS gate, explicit `--testScript`,
existing lifecycle/results configuration and GUI thread are mandatory. Missing
services fail without creating dependencies. The passive read obtains:

- actual AddressManager URL and scheme, actual DomainHandler serverless and
  connection state, and actual Qt application foreground state;
- actual MyAvatar feet, world orientation/velocity, model scale and physics
  in-air/flying values;
- actual camera position, orientation, mode, FOV, aspect and perspective;
- the five fixed controlled-scene marker IDs queried directly from the entity
  service, with original names, types, spatial properties, colors, visibility
  and collision state; absent slots remain explicit;
- an independently captured original scene-load snapshot including its own
  source birth, sequence, PID, native capture time, original resource hashes,
  generations, phases, results, callback leases and immutable request history.

A native source birth, bounded sequence, PID and native UTC/elapsed pair bracket
the entire read. Nested scene events keep their original clocks. The nested
scene query uses the same nonce/run and the existing scene observer action; it
neither reloads a scene nor changes an avatar or camera property.

`IOSNavigationState` uses the existing Places source acquisition boundary:
one send, original read retries only, distinct native clock reads before/after,
less than 1.5 seconds of host monotonic time and foreground process continuity.
Host UTC and AFC metadata are not native freshness. Historical validation leaves
original clocks unchanged and does not claim present-time freshness. Repeated
reads must preserve both source births and append-only scene history.

`pose_ready` validates actual necessary state against the versioned controlled
scene and matching A/B/C URL/viewpoint. It requires foreground, settled real
physics (feet within 0.75 m and speed at most 0.15 m/s), all five original marker
geometries, and the actual current committed scene generation with no traced
lease pending. Importantly, DomainHandler legitimately reports connected=true
for serverless scenes after `connectedToServerless`; that original fact is
preserved rather than projected as a network-domain connection.

A matching requested URL and loaded entities cannot establish that this scene
reached the renderer. The next owner must additionally bracket an original
completed Vulkan image with these state packets, join its recorded camera and
scene identity, verify visible scene effects, and retain/drain all image and
callback resources. This component does not provide that verdict, a three-second
quiet window, process restart or whole-area completion.

Host tests execute the actual Python factory/command validators and actual probe
JavaScript dispatcher with native Qt/SDK boundaries modeled. They reject ignored
motion, moving/falling/flying/background states, foreign domains, wrong/missing
markers, pending/failed/stale scene generations, changed clocks/PIDs/source
births, replay and wanted-value queries. Native code remains uncompiled and
devices untested under this session's explicit boundaries.
