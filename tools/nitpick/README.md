# Nitpick: inherited snapshot-testing tool

Nitpick is a standalone application for creating screenshot tests, comparing
snapshots with a canonical set, and collecting differences. Its source and UI
remain in this directory. It is separate from the fork's current
[project test runner](../../tests/PROJECT_TESTING.md) and
[physical-device harness](../../tests/device/README.md).

The inherited manual described High Fidelity QA downloads, AWS uploads,
TestRail integration, Python 3.7, and attached-device automation. Those services
and release procedures are not provided by this personal hobby fork. The full
manual is preserved as [historical documentation](https://github.com/noah-l-frank/overte/blob/b5f48d2a842a5cc1655ceb2f69a46bf3c4030429/tools/nitpick/README.md).

For source work, inspect this directory's CMake definitions alongside the
[current build guides](../../BUILD.md). Historical launcher, installer, cloud,
and device examples are not a current deployment recipe. The maintainer's
hardware tests use the [private Proxmox Jenkins laboratory](../../docs/portal/jenkins/index.md),
not workstation or Nitpick device automation. Local source builds and host
unit tests remain independent of that personal infrastructure.
