# Test Overte for Pico 4

## Device-free tests

From the repository root:

```bash
./android/vr/pico/tests/pico-device-free-test.sh
```

This checks shell, packaging, WebView, microphone, OpenXR lifecycle, fixture,
device-lock, and power-analysis contracts without ADB or a headset. The broader
hardware-independent suite is documented in
[`android/vr/pico/docs/PICO4_TESTING.md`](../../../android/vr/pico/docs/PICO4_TESTING.md).

## Physical headset

Build verification and device mutation are separate. The maintainer's hardware
runs use the prepared `overte-jenkins` wrapper with private Proxmox jobs and
verified candidate identity. This is personal infrastructure, not a shared
service. The workstation lab is retired; do not use local ADB automation as a
fallback. See the [operator boundary](https://github.com/noah-l-frank/overte/blob/main/docs/portal/jenkins/index.md).

The repository also retains a separate manual GitHub device-acceptance
implementation. Its existence does not establish an active runner or current
acceptance; [the CI guide](CI.md) explains that distinction.

A device-free pass cannot establish rendering, controller, audio, thermal,
power, lifecycle, or comfort behavior on a worn headset.

### Personal Alpha core journey

Run this baseline only on an authorized headset. Record the source revision,
APK digest, a non-secret device label, Pico OS version, start/end time, and the
result of every step. Keep account names, USB serials, tokens, and private world
addresses out of committed evidence.

1. Install and launch the selected APK using the documented deploy path.
2. Enter one representative world and confirm useful stereoscopic rendering.
3. Verify head and both-controller tracking, required buttons, pointing,
   selection, and one grab/release interaction.
4. Complete movement or teleport, open and operate the tablet, and enter text
   through the required keyboard path.
5. Verify audio playback and mute. Exercise microphone permission once allowed
   and once denied, confirming that denial fails safely.
6. Exercise pause/resume, headset removal/re-entry, application restart, and a
   clean exit.
7. Continue representative use until the total session reaches 30 minutes;
   record crashes, critical thermal behavior, and observed memory growth.

Stop at the first failure that prevents later steps, record that blocker, and
make it the next repair target. Passing this journey on one named device and
revision is Personal Alpha evidence, not broad Pico compatibility or release
acceptance.
