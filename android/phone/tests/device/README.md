# Phone result consumer: implementation, not acceptance

result_adapter.py consumes original SH-004 v001 (source
5c6354555a88fac2e089b033eb52ebe750171cd5, manifest
d92c7710551fe134029d2243cea84350a18000934acbd765bd1ef138b3cfa85b).
The published patch and byte-identical terminal_evidence.py prerequisite are
imported separately. Existing newer Phone catalog entries are preserved; each
Phone-required suite's exact module membership is checked for drift.

The result root holds one original Shared runner directory per named suite.
Emulator requires smoke, permission-recovery, tablet-e2e and text-input-smoke.
Core adds controlled domain, touch interaction, audio control/playback, network
recovery, loaded lifecycle and at least 30 minutes of stability. All required
modules must be present, complete and passing with the exact source/APK identity.
Actual registered adapter IDs are android-phone-adb or appium-android. Emulator
requires virtual Android; core requires physical Android. No target is selected,
device operation run, identity sidecar written or receipt retroactively created.

Example offline consumption (only after separately authorized execution):

    python3 android/phone/tests/device/result_adapter.py \
      --result-root RESULT_DIRECTORY --expected-source-sha SOURCE_SHA \
      --expected-artifact-sha256 APK_SHA256 \
      --expected-adapter android-phone-adb --milestone core

Successful output is PHONE_RESULTS_BOUND_NOT_ACCEPTED. This consumer validates
integrity and scope, not producer trust, installation truth or sensor observation.
PH-003 additionally verifies its packaging/deep-link AndroidJUnit plan through
emulator/phone_acceptance.py, whose CLI now requires these canonical results.
The independent AndroidJUnit files still lack a Shared execution-time identity
binding and cannot prove candidate equivalence merely by being provided together.

Pending: actual execution-time identity producer, AndroidJUnit identity binding,
exact candidate/ABI/API acceptance, actual module capabilities, physical device
label provenance, microphone/route evidence, screenshots and module/crash-log
privacy scans, SH-005/006/PX-17 and original node dependency acceptance.
Host fixture success is never a device or emulator PASS.

The existing installed-candidate test entry includes normal Go To/Places and
Snapshot binding cases. They execute the original SH009 verifier,
installed-APK checks, actual Phone Appium dispatcher, guarded native input flow
and the independent navigation journey. Only native ADB/W3C/probe/session/time
boundaries are synthetic; no external reference module or verifier stub is used.
The existing mandatory `phone-e2e-runtime-regressions.py` owner executes these
tests in both dependency-light and prepared-host modes. Candidate-free or
unconfigured navigation, changed installed bytes before/after input and changed
processes reject; original cleanup and identity cases remain enforced.

### Normal Snapshot extension

The Phone-owned Appium adapter advertises `snapshot.open`, `snapshot.capture`,
`snapshot.files` and `snapshot.close` only with `OVERTE_PHONE_NORMAL_SNAPSHOT=1`,
an original verified candidate, and the fixed physical Phone debug configuration.
This extends the shared [Snapshot journey](../../../../tests/device/SNAPSHOT_E2E.md);
the parent-only adapter does not provide these actions. The ordinary runner must
provide its private `OVERTE_DEVICE_ARTIFACT_DIR` and existing Appium target state.

Normal input uses the actual SNAP Home entry, pagination, text field, radio
popup choices and capture/cancel controls. Selection is checked through native
accessibility state, independent of translated captions. Original mode and
format are saved once and restored through those same controls. Owned input
intent survives partial entry and capture-driven tablet hiding. A foreign panel,
run prefix, installed APK, PID/start-time pair, process or Appium session cannot
be adopted. File transfer uses the shared original-file reader and its bounded
private `files/Snapshots` root; no image is manufactured by the adapter.

The Phone sidecar `phone-snapshot-session.json` is private and separate from the
shared Appium session schema. Failed close/restoration retains it. Generic
recovery can operate after candidate invalidation, but retires retry state only
after independently confirmed force-stop and successful Appium session removal.
This recovery confirms a lifecycle boundary; it does not claim preferences were
restored after losing the bound process.

The mandatory prepared-host owner additionally registers
`phone-snapshot-journey-test.py` and `phone-snapshot-ui-test.py`, each once. The
first executes the real Phone dispatcher, original SH009/installed-byte checks,
normal flow, actual file scripts and original independent image decoder. Only
native W3C/SDK/process/render/time boundaries are synthetic. It covers five
capture cases, ignored input, missing GIF, mismatched tickets, corrupt files,
partial cleanup and preference restoration. Pillow comes from the existing
`tests/requirements-host.txt` prerequisites.

The second has distinct Qt5 and Qt6 methods. It compiles the actual composed
`PhoneAccessibilityTree.cpp` and clicks the complete production Snapshot review
through that API. The hidden host uses real `QQuickRenderControl` layout polish;
no device or graphics capture runs. Tests require ordinary popup choices and
checked state on their first native frame, reject arbitrary siblings and another
window's popup, and reject a stale choice after closure. Qt5 can use the existing
`OVERTE_TEST_QT5_SYSROOT` SDK override. These native input tests provide no
installed application, GPU capture, system save/share or device acceptance.

Focused Snapshot host checks (no device):

    python3 -B android/phone/tests/device/test_installed_identity.py
    python3 -B android/phone/tests/phone-snapshot-journey-test.py
    python3 -B android/phone/tests/phone-snapshot-ui-test.py

Focused result-consumer test:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
      -s android/phone/tests/device -p test_result_adapter.py


The Phone prepared-host runtime gate also runs
`android/phone/tests/phone-voice-clock-test.py`. It retains the original
source-derived Android pause, input shutdown, mute, reset, lease and late-clock
regressions with its product-owned C++ fixture. The common
`tests/device/contracts/audio/test_voice_clock.py` keeps the current parent's portable/iOS
clock coverage, so synchronization runs both contracts instead of replacing
the Android lifecycle checks with another platform's fixture.
