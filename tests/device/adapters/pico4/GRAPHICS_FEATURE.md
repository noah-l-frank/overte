# Pico Graphics feature binding v1

The bound Pico adapter implements the existing v16 `feature.graphics.act`,
`feature.graphics.observe` and `feature.graphics.cleanup` operations. The catalog
module uses `OverteSession.feature_operation`, the existing common `Journey`
engine and this public router. Source and host integration covers all fifteen
action phases, the measured original baseline, both cleanup checks and final
independent retirement. This is the third complete source-level area alongside
Scripts and Authentication; native compilation and all devices are unverified.

## Explicit configuration

The normal candidate/OpenXR configuration and installed-candidate checks remain
mandatory. Enable `OVERTE_PICO_NORMAL_SCRIPTS=1`, `OVERTE_ANDROID_E2E_DEBUG=1`,
`OVERTE_PICO_OPENXR_INPUT=1` and `OVERTE_PICO_FEATURE_GRAPHICS=1`. Keep the normal
owned `OVERTE_E2E_SCENE_URL` profile. Public feature advertisement defaults off.
The binary still requires the existing dedicated E2E build configuration;
source/host success does not establish that any installed binary has it.

`OVERTE_DEVICE_ARTIFACT_DIR` is an existing absolute, canonical private 0700
directory, shared with the runner and independent actor. Original files use
0600, exclusive names and the existing inode/hash/ownership checks. Missing or
unsafe directories fail; configuration does not create or repair them.

`OVERTE_PICO_FEATURE_FIXTURE_CONFIG` names the existing private adapter-only
access file (`fixtureAdapterAccessVersion: 1`, `fixtureUrl`, `adapterToken`).
`OVERTE_E2E_FEATURE_FIXTURE_URL` must agree. The adapter credential can read only
its existing run/phase/provider; it cannot activate a run, publish peer facts or
see peer facts. Do not provide `OVERTE_E2E_FEATURE_READER_TOKEN` to the adapter.

The runner image policy is `{"graphics":{"screen":{"source":
"world-render-target","profile":"pico-stereo-graphics-v2"}}}`. The existing
catalog module selects the explicit `pico-stereo-cues-v1` fixture profile from
that policy. A legacy provider is refused before normal input. The adapter and
actor use the fixed v2 policy; neither accepts requested photometry or facts.

## Inputs and original observations

Normal Home/controller rays, Go To/address/keyboard and Generic Graphics
controls provide all input. Resolution uses the existing immediate slider;
Haze/Mirror use the actual normal toggles. The restart-only Pico swapchain
setting is outside this generic profile. Admission requires an actual eligible
first-person, level tracked rig; normal navigation compensates its observed
physical offset/yaw. Unsupported view/tracking state fails without forcing it.

Every role reads its own original native/UI/scene packets and fresh GPU capture.
The PNG and separate native metadata bind both actual eyes, executing camera
uniforms/draw passes and successful same-frame OpenXR submission. Per-eye current
Haze/reflection codes, original HTTP deliveries and actual tablet composition
establish visible surface attribution. Requested resolution and measured frame
scale remain separate facts; an ignored renderer scale is reported as such.

See the [coordinator](GRAPHICS_FEATURE_OWNER.md), [observer](GRAPHICS_OBSERVER.md),
[normal restart](GRAPHICS_RESTART.md), [background](GRAPHICS_LIFECYCLE.md) and
[complete lifetime](GRAPHICS_LIFETIME.md) contracts. Their existing 1.5-second
source freshness, bounded input/read deadlines, five-second pure analysis,
three-second quiet windows and current candidate/ownership checks remain.

## Independent actor and retirement

The existing `feature_observer.py --config <private-file>` publisher reads a
version-2 configuration for Graphics. Version 1 remains readable for existing
Scripts/Authentication callers. This is a template; replace the placeholders:

```json
{
  "picoFeatureObserverVersion": 2,
  "area": "graphics",
  "target": "<owned-target>",
  "candidateArguments": ["<complete-original-candidate-arguments>"],
  "fixtureUrl": "http://<owned-fixture>/feature-fixture/v1",
  "actorToken": "<private-actor-token>",
  "artifactRoot": "/<same-private-artifact-directory>",
  "durationSeconds": 1800
}
```

The actor uses separate role/process journals and original acquisitions. It
cannot deliver normal input. Graphics opts into the existing publisher's
observation-during-retirement mode: creation of the parent retirement plan is
not an exit signal. It must still acquire its own final restored-world/resource
quiet window. The existing default publisher behavior for other features is
unchanged. Invalid originals remain fatal; only actual pending phase/source-lock
contention is retryable.

Runner cleanup restores original preferences, verifies the closed stereo
baseline and retires the provider. The adapter's ordinary final teardown then
uses its exact owned journals, actual world/avatar/framework restoration and
both roles' fresh UI/QML/XHR/reply/Web-renderer/scene/capture quiet evidence.
Uncertain inputs are not replayed. Final source continuations and originals are
durable before live metadata removal; unknown resources retain unresolved
journals. Internal cleanup may read an existing owner after public advertisement
was disabled, with the same actual candidate and private read authority.
Inspection never creates unused feature namespaces.

## Host verification limits

Selected no-build Pico source groups include configuration, public dispatch and
actor-protocol counterexamples. The full discovered host self-test
`python3 -m unittest self_tests.test_pico_graphics_common_engine` (from
`tests/device`) runs the common engine through the actual `OverteSession` and
Pico router, independent actor loop and final metadata retirement. It uses
synthetic package/GUI/OS/GPU/fixture transport boundaries and real private
original/receipt files. Synthetic package evidence is not a build receipt.

Counterexamples additionally cover ignored inputs/rendering, stale/foreign or
replayed originals, lost replies, process/candidate replacement, incomplete
renderer/callback/reply retirement and interrupted quiet windows. Host timings
qualify adapter logic only. No compiler, build, device, installation or service
is run for these checks, and no physical VR/rendering/timing qualification is
claimed. Missing capabilities in the other eleven areas still prevent a green
complete fourteen-area run.
