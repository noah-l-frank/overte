# Pico 4 continuous integration

The active development branch is `android-vr-pico`; the retired
`feature/pico4-support` branch must not be used.

This is a personal hobby fork. Hosted checks can run independently of the
maintainer's private build runners and Proxmox Jenkins laboratory; those are
not public services or setups that contributors are expected to reproduce.

- The central selective PR controller reports `source-policy` and `required-ci`,
  with the separate `Enforce Android parent sync path` topology result. The
  [selective CI guide](https://github.com/noah-l-frank/overte/blob/main/docs/PR_CI.md)
  owns selection and acceptance. These are the live required names read on
  October 22, 2026; Actions was disabled at that inspection. Retained legacy
  recipes and local qualification do not establish a hosted run.
- `Android VR integration tests` provides separate selected branch-push/manual
  platform checks; it is not a replacement for the required PR aggregate.
- `Pico 4 trusted build` is manual and accepts only `android-vr-pico` or an
  immutable preview tag on the isolated Android build runner.
- `Pico 4 release candidate` defines signing and draft-candidate verification
  from an immutable RC tag in a protected environment.
- `Pico 4 device acceptance` retains a manual, protected-runner implementation.
  Its presence does not establish an available runner. The maintainer's current
  hardware tests go through the private Proxmox Jenkins laboratory.

The retained native build/release workflows still download the legacy bundle;
that does not satisfy the current source-input consumer. Neither workflow
declares the required source bindings itself. See the detailed guide's
[trusted build prerequisites](../../../android/vr/pico/docs/pico4-ci-cd.md#trusted-pico-build)
and the [central platform coverage guide](https://github.com/noah-l-frank/overte/blob/main/docs/PR_CI_PLATFORM_COVERAGE.md)
before treating a configured workflow as a qualified current build lane. Pending
local native-build work must retain its own exact-source qualification evidence.

Workflow filenames, runner labels, artifacts, retention, and repository settings
are detailed in
[`android/vr/pico/docs/pico4-ci-cd.md`](../../../android/vr/pico/docs/pico4-ci-cd.md).
