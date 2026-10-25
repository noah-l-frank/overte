# Test Overte for Android phones

## Device-free host tests

```bash
cd android/phone
./tests/phone-static-regression-test.sh
```

The host gate uses source, unit, contract, JavaScript, Java, and mock-ADB checks.
It does not prove an APK build or physical runtime behavior.

The repository quick profile also runs the Phone default microphone selection
and editor focus teardown contracts registered in
[`tests/platform-profile.json`](../../../tests/platform-profile.json).
These compile small host fixtures and require a C++17 compiler, `pkg-config`,
and Qt 6 Core and Widgets development packages (`qt6-base-dev` on Ubuntu).
Run them from the repository root:

```bash
python3 tests/run-project-tests.py --suite phone-default-input --suite phone-editor-teardown
```

## Phone runtime host groups

The mandatory runtime contracts are declared in
[`phone-runtime-groups.json`](../../../android/phone/tests/phone-runtime-groups.json).
List the groups without executing a test:

```bash
python3 android/phone/tests/phone-e2e-runtime-regressions.py --list-groups
python3 android/phone/tests/phone-e2e-runtime-regressions.py --execute --list-groups
```

The default mode has 17 groups covering exactly the original 190 dependency-light
and common host files. `--execute` has 25 groups covering exactly the original
238 prepared-host and common files and requires their documented compiler, Qt, GLM, and other host tools.
`--extended` explicitly adds one group for the original expensive Emote composition; it is
not implied by either default mode. The pinned
[coverage baseline](../../../android/phone/tests/phone-runtime-coverage-baseline.json)
was captured from the original runner before grouping. Validation compares the
complete original file sets with the group union and rejects omissions,
duplicates, unknown paths, foreign paths, and unregistered additions before
execution.

Use `--group ID` with an identifier returned by `--list-groups` to run one group.
The default is four child workers; `--jobs 1` provides serial diagnosis. Group
budgets include the complete composition, while every file keeps its original
command arguments. Original file limits remain frozen as independent gold;
[`phone-runtime-timeout-calibration.json`](../../../android/phone/tests/phone-runtime-timeout-calibration.json)
contains only explicitly reviewed whole-file exceptions supported by complete
successful measurements and pinned provenance. All other file limits, and all
individual RPC, IPC, source freshness, checkpoint, lock, and quiet windows, are
unchanged. A partial group or successful prefix is not a complete runtime result. CPU time and elapsed wall time measure different things;
waiting and concurrent host work can increase elapsed time without a hang.

The project runner's compatibility selector
`--suite phone-e2e-runtime-regressions` expands to all default groups; its
`--list` output names the actual suites. See
[project testing](../../../tests/PROJECT_TESTING.md#reviewed-whole-file-host-calibration)
for measured limits, the uniform margin, and combined host execution. These checks never constitute an APK build
or physical-device acceptance. The scheduler and independent coverage tests
remain mandatory under the existing `device-jenkins` host suite through
[`test_phone_host_groups.py`](../../../tests/device/jenkins/test_phone_host_groups.py);
no extra platform-profile entry is required.

## Emulator

```bash
cd android/phone
./phone-emulator-test.sh all
```

This builds a separate x86_64 variant, boots the selected AVD, and runs AndroidX
instrumentation. See
[`android/phone/docs/EMULATOR_TESTS.md`](../../../android/phone/docs/EMULATOR_TESTS.md).

## Physical phone

```bash
cd android/phone
ANDROID_SERIAL=<serial> ./tests/phone-device-test.sh
```

The test validates the APK and target before installation, exercises bounded
lifecycle and deep-link behavior, and records only aggregate diagnostics. Test
at least one Adreno and one Mali device. Emulator evidence cannot replace
physical 4-KiB/16-KiB, graphics, audio, thermal, battery, cutout, or vendor
validation.

The wider test policy is in
[`android/common/docs/ANDROID_TESTING.md`](../../../android/common/docs/ANDROID_TESTING.md).

## Semantic tablet E2E

The checked-in Android Phone policy is
[`tests/device/policies/android-phone-flat-touch.json`](../../../tests/device/policies/android-phone-flat-touch.json).
It is evaluated independently from the Appium observation and requires
Tablet Home, Settings, General, Audio and Security while forbidding Controller,
HMD and VR render-resolution controls.

First audit the physical debug APK's UiAutomator2 tree as described in
[`tests/device/adapters/appium/README.md`](../../../tests/device/adapters/appium/README.md).
Enable `controls.tablet.semanticUi` in the protected target configuration only
when the semantic QML object names are exposed as actionable native IDs. Then
run:

```bash
python3 tests/device/run.py \
  --adapter-manifest tests/device/adapters/appium/android.json \
  --catalog tests/device/catalog.json --suite tablet-e2e \
  --tablet-policy tests/device/policies/android-phone-flat-touch.json \
  --output-dir /tmp/overte-android-phone-tablet-e2e --require-complete
```

The acceptance sequence keeps one process alive, observes stable ready screens,
uses real element clicks, returns through visible semantic navigation controls,
and verifies forbidden features only after readiness. Raw Accessibility XML and
screenshots are opt-in diagnostics; inspect and redact them before retention.
