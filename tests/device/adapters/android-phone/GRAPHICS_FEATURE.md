# Android Phone Graphics feature v1, shared contract v16

The existing Phone Appium entrypoint implements `feature.graphics.act`,
`feature.graphics.observe` and `feature.graphics.cleanup`. This composes normal
scene, preference, background and restart inputs with independent original
observations and complete owned retirement. Host simulations establish adapter
and test logic only. Native C++/Java remains uncompiled and all devices untested.

## Explicit admission and private inputs

Enable `OVERTE_PHONE_FEATURE_GRAPHICS=1` for the verified Phone debug candidate
with the existing controlled launch/session configuration. Supply
`OVERTE_PHONE_FEATURE_FIXTURE_CONFIG` using the separate read-only
[adapter fixture credential](../../feature_journeys/ADAPTER_FIXTURE_ACCESS.md).
The optional `OVERTE_E2E_FEATURE_FIXTURE_URL` must match its exact configured URL.
The runner reader token is deliberately unavailable to the adapter. The fixture
must explicitly configure its actual Graphics origin and resource provider.
The adapter never registers, activates, closes or mutates the fixture run.

Supply a canonical private `OVERTE_DEVICE_ARTIFACT_DIR` and
`OVERTE_PHONE_GRAPHICS_IMAGE_POLICY` pointing to a private JSON file with exactly
`source`, `marker` and `subject`. Source is `world-render-target`; the rectangles
use the common `[left,top,right,bottom]` image policy format within 4096 by 4096.
The marker must cover at least 128 by 32 pixels and be disjoint from the feature
subject. Choose the subject to contain the actual distant fog board and mirror
surface sufficiently tightly to detect their effects. No policy carries desired
settings, colors, effect verdicts or response facts. Files and parents use the
existing 0600/0700, canonical, no-symlink/no-shared-link rules. Incomplete or
foreign configuration cannot advertise the complete triple.

The original artifact root and image policy are pinned in the version-1 run
owner and retirement records. Actor and global cleanup factories recover only
that original configuration, including when per-module artifact environment is
absent. A changed profile or fixture authority is refused before new input.

## Normal input and independent effects

Preparation durably records intent before normal Go To. It freezes actual
original scene, avatar feet/view/scale and preferences, then enters the seven-UUID
controlled scene. The original scene must be restorable using the existing
HTTP/HTTPS/file and first-person-look-at profile. The limited spatial inventory
is explicitly not a complete foreign-world inventory.

Actions use the active fixture ticket and closed v16 stimulus. Ordinary Settings,
resolution, Haze, Mirrors, close, background/resume and explicit restart retain
per-substep one-send intent. Repeated completed requests acknowledge their owned
transaction; uncertain or ignored input is never replayed. The explicit restart
alone recovers its original Stop/Launch proof and partial scene/preference CAS.
It preserves the original user state across the new process. Input ACKs supply
no observation facts.

Each role has separate fixture, native/UI, lifetime, original GPU-frame and PNG
histories. A first role/stage acquisition establishes its own actual active
scene/HTTP/load/Web authority before another new frame supplies public facts.
Measured viewport scale, recorded-view draw batches and actual target pixels
must agree. Haze and mirror comparisons use that role's own off/on originals,
projected target regions and independent pixel thresholds. A native preference
without executed drawing remains distinguishable; missing effects cannot pass.
Original PNGs and complete frame JSON are immutable private artifacts, referenced
by exact role/stage/capture filenames and SHA256. Missing, stale, replaced or
foreign originals cannot become a fresh result. Changed-ticket acquisition
retirement never republishes an earlier frame.

The separately launched `script_observer.py` accepts this exact private config:

```json
{
  "featureObserverVersion": 2,
  "area": "graphics",
  "target": "<private configured selector>",
  "candidateArguments": ["<complete reviewed candidate flag/value arguments>"],
  "fixtureUrl": "http://<owned fixture>/feature-fixture/v1",
  "actorToken": "<separate publisher credential>",
  "durationSeconds": 1800
}
```

The actor acquires its own sources; it never invokes primary Observe, copies
primary facts, changes product settings or launches/repairs a session. Both roles
independently prove old-PID ESRCH and new native/GPU/Web births after restart.
The Graphics worker continues past creation of the retirement plan until its own
actual restored-world quiet window completes. It is not launched by the adapter.

## Cleanup, bounds and interrupted recovery

Normal feature Cleanup first restores original preferences and closed UI inside
the still-active controlled scene. It requires fresh baseline/zero-owned-resource
frames over three seconds in both host and original clocks. Each retry starts a
new window and retains the old originals; the cleanup bound is 45 seconds and
64 frames. The common journey additionally checks its independent peer cleanup.

After the runner retires the fixture, general cleanup restores the original user
world and preferences before determining whether evidence can qualify. It
attempts this restoration even after an interrupted measurement; incomplete
sources still fail final retirement. The actor and primary each observe the
restored original pose, absent seven UUIDs, drained scene-load references,
inactive provider and absent native/Java document/creation/callback authority.
Each role needs its own three-second quiet window. Provider epochs and host
monotonic time must both advance. A final fresh read checks native preferences
and the actual closed tablet without creating another GPU capture.

Finalization is bounded to 60 seconds. Runtime windows use at most eight
attempts, 64 samples per window and 20 seconds per acquisition window; failed
windows and cursor floors remain owned. Source freshness is at most 1.5 seconds
including local elapsed age. Existing source/input bounds remain active: normal
inputs 30 seconds, image readiness at most 16 acquisitions in 20 seconds and
public original observation 30 seconds. The worker is bounded to 30..1800 seconds.

Exact component archives have durable SHA256 write intent before exclusive file
creation. Lost write responses recover only the same original header. A partial
metadata retirement never reruns feature input or navigation. Every retry proves
new actual absence, including another original three-second runtime window;
reappearing callbacks fail. Exact child journals retire before the root and
retirement plan; original diagnostic JSON/PNG files remain private evidence.
Changed or foreign files are retained and refused. General cleanup always
attempts base SDK teardown and reports unresolved Graphics ownership as failure.

The host counterexamples include ignored preference/drawing, conflicting input,
missing actor, live Java/callback remnants, changed policy/archive, lost archive
writes, partial/lost/ignored removals and interrupted measurement restoration.
They use explicit synthetic product boundaries and real private host files.
No acceptance policy, device evidence or build identity is promoted by them.
See [observer v2](GRAPHICS_OBSERVER.md), [lifetime v1](GRAPHICS_LIFETIME.md),
[scene v2](GRAPHICS_SCENE.md), [preferences v2](GRAPHICS_PREFERENCES.md) and
[restart v1](GRAPHICS_RESTART.md) for the exact lower-level evidence contracts.

The closing host selection passes 707 Android tests, including 25 complete
Graphics coordination cases and the actual fifteen-step common journey through
the registered entrypoint. Documentation and contract-registry validation pass.
The preceding shared no-build selection passed 1,162 tests with zero compiler
attempts; exactly three native-compiler voice checks were outside that selection.
These results establish test logic only and register no physical acceptance.
