# Pico 4 developer artifacts

The immediate goal is a verified APK that a developer can install and test. A
store publication decision is not required for this milestone.

Build the debug APK with `android/vr/pico/build.sh` from the repository root.
For maintainer hardware, use the private Proxmox Jenkins deployment and test
path in [TESTING.md](TESTING.md), with the exact APK and source identity.
For a signed candidate, the protected release-candidate workflow derives version
metadata from an immutable tag, verifies the APK and certificate, and creates a
draft GitHub release with provenance, SBOM, and checksums. It does not publish
the release.

Physical installation and acceptance remain separate from building or publishing a candidate. See
[`android/vr/pico/docs/PICO4_RELEASE_CHECKLIST.md`](../../../android/vr/pico/docs/PICO4_RELEASE_CHECKLIST.md)
and
[`android/vr/pico/docs/PICO4_DISTRIBUTION_READINESS.md`](../../../android/vr/pico/docs/PICO4_DISTRIBUTION_READINESS.md).
