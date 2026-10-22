# Original Pico avatar drive, feet and tracking v1

Lifecycle/input remains partial. This packet adds a passive primary-avatar
source and the three-dimensional displacement/stability calculations needed
by the existing journey. There is no complete feature capability, independent
peer qualification or original world-attempt counter in this source.

The native-only `MyAvatar::featureLifecycleDriveObservation()` exists only
under `OVERTE_E2E_FEATURE_TESTS` and requires actual HMD mode, its owner thread
and `--testScript`. It reads the actual avatar's `getDriveKey`, `getRawDriveKey`
and disabled-key mask for all twelve original enum slots. An exact native enum
order assertion prevents a changed order from borrowing v1 meanings. It also
reads original CharacterController readiness/state/seat/stuck/linear velocity,
actual feet/body/orientation/model scale/sensor-to-world transform, stored
ActionMotor/ScriptMotor/thrust state and original head/left/right sensor poses.
The actual ActionMotor enable flag and advanced-movement setting remain
separate from a nonzero drive key. A request, injection lease or OS-down receipt
cannot supply these values. The getter changes no input, drive key, setting,
controller, pose or motor.

Each actual MyAvatar owns its own passive serializer with a nonreused instance
and advancing source cursor. A replacement avatar cannot inherit that identity.
`LifecycleDriveObservation.h` checks runtime/thread boundaries, bounded finite
native values, actual unit quaternions and monotone native capture time before
emitting v1. `TestScriptingInterface.featureLifecycleDriveObservation` additionally
requires the existing private test-results directory, original active lifecycle
source, GUI/avatar ownership and one of at most 4096 unique native query IDs.
Its closed command is exactly `{schemaVersion:1,commandId,action:
"feature-lifecycle-drive-observe",runId}`. JS numeric version 1 is accepted;
booleans, strings, extra expected effects and paths are rejected.

The actual probe forwards the unchanged original native payload to
`feature-lifecycle-drive.json`; an absent/failed getter remains explicitly
unavailable. It neither substitutes probe/MyAvatar script properties nor writes
requested positions, input names, displacement or counter values. The guarded
Pico factory `_lifecycle_drive_source(target).capture(run)` uses that existing
private native channel and actual candidate/installation/process identity.
A single original query, five-second/51-read deadline, 262144-byte pre-decode
bound and final 1500 ms monotonic age bound apply. Acceptance and final guard
time count even when the device clock stops. Reconstruction via `restore`
retains the complete original native packet, instance/PID/run and source cursor.
Original JSON bytes and SHA-256 remain available as `last_raw/last_sha256`.

The v1 packet fields are exactly `lifecycleDriveVersion,commandId,runId,instance,
sequence,processId,capturedEpochMs,source`. The source fields are exactly
`sceneUrl,feetPosition,bodyPosition,orientation,modelScale,sensorToWorld,driveKeys,
rawDriveKeys,disabledDriveKeys,physics,motors,tracking`. Physics keeps numeric
original states Ground=0, Takeoff=1, InAir=2, Hover=3, Seated=4. Every original
tracking pose retains its actual `valid,position,rotation`, including unavailable
tracking. The reader rejects malformed/nonfinite/foreign data and inconsistent
disabled masks rather than treating them as neutral input or grounded movement.

`AvatarDisplacement` freezes original primary feet only from a grounded,
tracked, ready, nonmoving and neutral baseline. Current values require the
same original native avatar/process/run, world URL and model scale. The narrow
journey accepts only longitudinal ground-drive translation; unexpected other
native drive slots fail. Effective `heldInputs` reflects original unmasked
TranslateZ only while advanced movement and ActionMotor are actually enabled.
Disabled raw input stays visible in the original source. `positionDelta` is the
three actual current feet components minus the frozen actual feet components;
`worldDisplacement` is their Euclidean norm. A directional input request never
supplies either value. These are primary measurements and still need the
independent original peer/network position join, world pixels and original
consumed-gesture history required by the complete feature.

`AvatarReleaseWindow` tests the actual three-dimensional current point against
its stable-window anchor within 0.025 m, using three seconds of both original
native timestamps and host monotonic time. Movement along a constant-distance
arc resets the window. Any held input, invalid source, missing observation gap
above one second or backward/replayed source resets or rejects quiet. A released
frame cannot borrow a previous held frame's time. The window cannot be restored
by relabeling historical frames as fresh; a new host owner needs a new quiet
window. This primary-only predicate is not full resource release or peer proof.

Focused checks use an owned disk-backed `TMPDIR` and
`PYTHONDONTWRITEBYTECODE=1`:

```bash
python3 tests/device/self_tests/test_pico_lifecycle_drive.py -v
OVERTE_NATIVE_QT_MAJOR=5 OVERTE_QT5_HOST_ROOT=/prepared/qt5/root \
  OVERTE_HOST_GLM_INCLUDE=/prepared/glm/include \
  python3 tests/device/contracts/input/test_lifecycle_drive_observation.py
python3 android/vr/pico/tests/device/test_lifecycle_input.py -v
python3 tests/device/validate_contract_versions.py
python3 tests/check-documentation.py --all
git diff --check
```

The compiled Qt5/GLM check runs the actual passive serializer and command
validator with explicit native avatar/physics value boundaries, including
runtime denial without `--testScript`. It does not compile the complete MyAvatar,
TestScriptingInterface or client binding. Python checks use synthetic original
native replies; the Node check executes the unchanged original probe branch.
The owning Pico selection reuses actual adapter candidate guards with synthetic
native I/O. No physical Pico, controller, OpenXR, independent peer, actual motor
execution or complete Lifecycle result is claimed by these host checks.
