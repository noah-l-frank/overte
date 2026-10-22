# Android Phone continuous integration

The active product branch is `android-phone`; the retired
`feature/android-phone-support` branch must not be used.

The central selective PR controller in `repository-checks.yml` selects shared
and branch-owned consumers and reports `source-policy` and `required-ci`.
`Enforce Android parent sync path` remains a separate topology result. These
are the live required names read on October 22, 2026; Actions was disabled at
that inspection. See the
[shared CI overview](https://github.com/noah-l-frank/overte/blob/main/docs/portal/testing/github-actions.md)
and [selective CI guide](https://github.com/noah-l-frank/overte/blob/main/docs/PR_CI.md)
for selection and acceptance. The workflows below are separate entry points;
local qualification does not establish a hosted run.

This personal hobby fork's isolated build runners and Proxmox Jenkins hardware
jobs belong to the maintainer. They are not contributor services or prerequisites
for local host and emulator checks; the workstation device lab is retired.

- `Android tests` provides selected device-free checks on relevant branch
  pushes, schedules, and manual runs; it has no standalone PR trigger.
- `Android Phone trusted build` is manual and accepts `android-phone` or an
  immutable Phone alpha tag on the isolated build runner.
- `Android Phone release candidate` produces an unsigned, store-neutral,
  locally inspectable candidate from an immutable tag.
- `Android Phone emulator acceptance` validates the exact tagged source through
  a separate x86_64 instrumentation graph; it cannot install the ARM64 candidate
  APK on that emulator.

Runner isolation, protected environments, artifact names, retention, and local
contract commands are detailed in
[`android/phone/docs/ANDROID_PHONE_CI_CD.md`](../../../android/phone/docs/ANDROID_PHONE_CI_CD.md)
and
[`android/phone/docs/ANDROID_PHONE_RELEASE_OPERATIONS.md`](../../../android/phone/docs/ANDROID_PHONE_RELEASE_OPERATIONS.md).
