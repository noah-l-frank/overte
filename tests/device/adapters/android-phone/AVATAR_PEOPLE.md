# Android Phone Avatar and People adapter

`PhoneAvatarPeopleFeature` implements the closed common `act`, `observe` and
`cleanup` triple through normal Avatar/People Qt controls, normal login fields,
the normal camera menu and normal logout menu. An input acknowledgment never
supplies an observed result. The existing common journey and its mandatory
`multi-user` foundation remain the runner; there is no parallel feature runner.

The adapter is default off. Explicit configuration requires:

- `OVERTE_PHONE_FEATURE_AVATAR_PEOPLE=1` and a verified Android debug candidate.
- `OVERTE_PHONE_ACCOUNT_FIXTURE=1`, the existing cold-launch HTTPS account-origin
  configuration, and `OVERTE_E2E_FEATURE_FIXTURE_URL`.
- `OVERTE_PHONE_FEATURE_FIXTURE_CONFIG`, the private adapter-reader credential
  file. Its credential can read only the primary account credentials and original
  status; it cannot publish peer facts, activate phases or obtain peer credentials.
- `OVERTE_DEVICE_ARTIFACT_DIR`, an existing private directory, and
  `OVERTE_PHONE_AVATAR_PEOPLE_IMAGE_POLICY`, a private JSON file with exactly
  `imageExtent`, `markerRoi` and `imagePolicy`. The last object has exactly
  `source: "world-render-target"`, `marker` and `subject` rectangles.

The existing observer entry point accepts Avatar configuration version 4 with
`area: "avatar-people"`. Its usual `target`, `candidateArguments`, `fixtureUrl`,
`actorToken` and `durationSeconds` fields are joined by mandatory `peerTarget`
and `peerImagePolicy`. The latter uses the same closed image-policy shape.
`target` is read only to that observer. `peerTarget` is a distinct, already
running, candidate-bound second Phone session: its own normal input, account,
AvatarManager, camera, GPU traces and original PNG supply the remote evidence.
The actor can obtain only peer credentials. The primary never controls that
Phone or obtains its credential. Source revision/artifact hashes must agree;
session and target fingerprints must differ. Neither role repairs or launches
sessions during a feature operation.

Admission requires a controlled domain with avatar-entity permission, settled
loaded original avatars, an initially anonymous account at the exact fixture
origin, a closed tablet/dialog state, existing bookmark files and existing Pal
preferences, no original attachments and an empty original avatar model-name
preference. The original preferred URL must equal the actual requested URL.
Unsupported original profiles fail before normal setup input. The current image
qualifier requires an actually loaded original or fallback Model. A genuinely
unavailable Model remains a bounded failure rather than an invented image result.

Observations join original advertised and loaded Model/HFM geometry, current
failure generation, textures, settled actual scale, backing bookmark bytes,
normal consent/model state, original native XHR completions and completed HTTPS
wire responses. Repository and companion manifests pin actual resources. Both
principals must send genuine reciprocal authenticated requests in the current
ticket before a relationship can qualify. Actual remote geometry and independent
PNG/draw sources are required; a primary result is never copied into a peer fact.
Original projected geometry bounds constrain changed pixels. Frozen bodies,
camera/background changes, retained A geometry under a missing request, missing
textures/draws, an absent peer and acknowledgments cannot satisfy these joins.

The marker reuses the existing navigation fixture and its measured camera lease.
It holds the actual captured normal view; ordinary avatar scale and actual
geometry draws remain untouched. Original weak entity identity, actual tree/map
membership, Browser callbacks and immutable camera handback proof must drain.
Normal `TAKE IT OFF` input matches the original successful entity ID and actual
selected wearable URL digest. URL matching alone grants no deletion authority.

Versioned private journals precede input and source acquisition. Immutable source
blobs are addressed by SHA-256 and keep their original clocks. Partial GPU/PNG
acquisitions are retired before a fresh acquisition; original saved PNGs and
source blobs remain private audit artifacts. Cleanup restores both original
avatars, scale, preferences, bookmarks, anonymous auth and view, with separate
three-second native/host quiet windows. A new actor cannot acquire input authority
during cleanup. After runner-owned account revocation and fixture closure,
`finalize()` requires fresh independent restored sources and zero actual service
authority. Its immutable retirement intent freezes both roles. A lost host-file
retirement return resumes by exact CAS or already-observed absence; it does not
recreate deleted journals or retime historical proof.

Host verification executes all 15 common actions and baseline/cleanup checkpoints
through the public Appium facade, the existing multi-user method, two explicit
synthetic Phone/Qt/GPU producers, actual loopback HTTPS/OAuth/resource/People
requests, real PNG decoding and private files. It also checks missing/static/
replaced foundation sources, default-off registration, actor policy separation,
closed probe grammar, premature finalization and interrupted retirement resume.

The real Qt6 host check compiles the native source/input helpers and original
AvatarApp/Pal QML, including scale SAVE, ordinary wearable add/remove and the
original selected wearable model roles. Its context services/script messages are
explicit synthetic seams. Missing host image assets, Tablet styling globals and
profile strings are rendering limitations, not visual product acceptance.
Product translation units, an APK, Android runtime and physical two-Phone
execution remain untested by these checks. No device acceptance or global
completion count is asserted. Probe changes require the parent's central Emote
source-pin integration check; no pins are learned from target output.

The main targeted host selection passed 53 tests in 117.675 seconds. One later
current-ticket primary-POST consumption counterexample passed separately in
1.793 seconds; a real backend relationship cannot replace original consumption.
The same module selection now contains that additional test:

```sh
PYTHONPATH=tests/device:android/phone/tests/device:tests/device/adapters/android-phone \
  python3 -m unittest test_avatar_people_feature.AvatarPeopleFeatureTests \
    self_tests.test_phone_avatar_people_native \
    self_tests.test_phone_avatar_people_measurements test_avatar_people_pixels \
    self_tests.test_avatar_people_service.AvatarPeopleServiceTests -f
python3 android/phone/tests/phone-avatar-people-native-test.py \
  --build-dir build/avatar-people-retire-controls-review
```

The Qt6 check passed in the fresh `avatar-people-retire-controls-qt6-v5-20261022`
build directory. The existing Phone host regression manifest includes the public
composition module with its own 240-second aggregate budget. The whole regression
launcher was not executed; the modules above were selected explicitly.
