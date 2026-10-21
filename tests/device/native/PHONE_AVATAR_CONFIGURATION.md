# Original Phone avatar configuration, version 1

`Test.phoneAvatarConfigurationObservation` is read-only E2E instrumentation,
inside `OVERTE_E2E_FEATURE_TESTS`, available only for the Phone interface, active
private results/lifecycle scope and `--testScript`, on the owning GUI thread.
No avatar, camera or preference setter is exposed. Native code is uncompiled.

The exact request is `{schemaVersion:1,commandId:<32 lowercase hex>,action:
"phone-avatar-configuration-observe"}`. No URL, expected value or iOS alias is
accepted. The probe deduplicates and forwards the original packet to
`phone-avatar-configuration.json`. Missing hooks remain unavailable.

The exact response is `schemaVersion:1`, `requestId`, shared native process-birth
`instance`, its own advancing `sequence`, `processId`, `requestedEpochMs`,
`capturedEpochMs`, `source`. Source is exactly:

* `phoneAvatarConfigurationVersion:1`, actual `modelInstance` and `rigId`;
* `configured`: current `getSkeletonModelURL()` source, without disclosing URL;
* `loadedGeometry`: null or actual loaded HFM `{instance,source}`;
* actual `boomLength` in [0.5,25] and saved `pinchZoomEnabled` boolean.

Each URL source is exactly `{present,urlSha256,bundledResource}`. SHA-256 hashes
the exact original loaded HFM QString UTF-8 bytes before any QUrl parsing,
including empty or invalid strings. The configured value is already a native
QUrl, so its actual API serialization is measured. The optional resource
is exactly `{resourcePath,bytes,sha256}`, measured by opening actual APK bytes,
never echoing repository expectations. Only a `qrc` URL without authority/query/
fragment whose cleaned path is `meshes/defaultAvatar_full.fst` (configured) or
`meshes/mannequin/mannequin.fbx` (loaded) may be opened. The latter is actual HFM
`originalURL`, never the requested FST. Reads are complete, bounded to 4 MiB, or
unavailable. Other/failed resources stay null. Repeated slashes normalize lookup
only. No network or arbitrary filesystem resource is opened; absent resource
bytes are never guessed.

`NativePhoneAvatarConfiguration` reuses bounded original transport: at most
51 reads/5 seconds, private candidate/process continuity and original cursors,
1.5-second freshness including final copies/guards and monotonic age floor.
Failed reads do not advance accepted state. `restore` accepts at most 256 original
historical packets, with no transport or retiming. The Phone factory requires an
existing read-only session: no launch, install, repair or capability promotion.

`controlled(config,avatarRender)` joins independent original native birth/PID/
Model/Rig/Geometry and exact loaded URL digest. Both measured APK byte counts and
hashes must match existing independently verified repository fixture pins. This
historical join does not establish current phase, rendering, immutable live mesh/
material bytes, unobstructed pixels, ordinary input effects or cleanup; the full
owner must bracket and verify those. External/custom/unloaded avatars fail the
controlled-content prerequisite.

Fourteen registered common host tests plus two Phone factory/grammar tests use
real Python/probe code with synthetic native boundaries. Ignored/foreign/missing/
stale/late results, failed delivery, changed bytes, mixed identities, replay and
missing native hooks fail. These prove test logic only; devices remain untested.
